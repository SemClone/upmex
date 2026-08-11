"""Maven Central registry integration for coordinate and POM lookups."""

import xml.etree.ElementTree as ET
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

import requests

DEFAULT_SEARCH_URL = "https://search.maven.org/solrsearch/select"
DEFAULT_BASE_URL = "https://repo1.maven.org/maven2"

# Maven Central rate-limits the search index aggressively, so every lookup is a
# single attempt with no retry and results are cached for the process lifetime.
DEFAULT_TIMEOUT = 10
SEARCH_ROWS = 20


class LookupFailed(Exception):
    """A lookup did not complete, so its outcome must not be cached.

    Distinguishes a transport failure or a rate-limit response — which says
    nothing about the artifact and should be retried on a later run — from a
    definitive "no such hash", which is worth remembering.
    """


@lru_cache(maxsize=512)
def _search_by_sha1(sha1: str, search_url: str, timeout: int) -> Optional[Tuple[str, str, str, str, int]]:
    """Look up coordinates for a file SHA-1 in the Maven Central index.

    Returns:
        Tuple of (group_id, artifact_id, version, packaging, match_count), or None
        if the index holds no usable match. Immutable so the cached value cannot
        be mutated by a caller.

    Raises:
        LookupFailed: if the request did not complete, so nothing is cached
    """
    try:
        params = {'q': f'1:"{sha1}"', 'rows': SEARCH_ROWS, 'wt': 'json'}
        response = requests.get(search_url, params=params, timeout=timeout)
    except Exception as e:
        raise LookupFailed(f"search request failed: {e}") from e

    if response.status_code != 200:
        raise LookupFailed(f"search returned HTTP {response.status_code}")

    try:
        payload = response.json()
    except Exception as e:
        raise LookupFailed(f"search returned an unreadable body: {e}") from e

    if not isinstance(payload, dict) or not isinstance(payload.get('response'), dict):
        raise LookupFailed("search returned an unexpected body shape")

    payload = payload['response']
    docs = [doc for doc in (payload.get('docs') or []) if isinstance(doc, dict)]
    if not docs:
        return None

    # A hash can match several coordinates when an artifact is republished or
    # relocated. The index sorts by score then recency; prefer a jar among the
    # top matches and report the total so a consumer can see it was ambiguous.
    doc = next((d for d in docs if d.get('p') == 'jar'), docs[0])
    group_id = doc.get('g')
    artifact_id = doc.get('a')
    version = doc.get('v')
    if not all(isinstance(field, str) and field for field in (group_id, artifact_id, version)):
        return None

    packaging = doc.get('p')
    match_count = payload.get('numFound', len(docs))
    return (
        group_id,
        artifact_id,
        version,
        packaging if isinstance(packaging, str) else '',
        match_count if isinstance(match_count, int) else len(docs),
    )


@lru_cache(maxsize=512)
def _fetch_pom_bytes(group_id: str, artifact_id: str, version: str, base_url: str, timeout: int) -> Optional[bytes]:
    """Fetch the raw POM for a set of coordinates.

    Returns the undecoded body: Maven Central serves POMs without a charset, so
    requests would fall back to ISO-8859-1 and mangle any non-ASCII text. The XML
    declaration is authoritative, and only the parser can act on it.

    Returns:
        Raw POM bytes, or None if no POM is published at those coordinates

    Raises:
        LookupFailed: if the request did not complete, so nothing is cached
    """
    try:
        response = requests.get(
            _pom_url(group_id, artifact_id, version, base_url),
            timeout=timeout
        )
    except Exception as e:
        raise LookupFailed(f"POM request failed: {e}") from e

    if response.status_code == 200:
        return response.content
    if response.status_code == 404:
        return None

    raise LookupFailed(f"POM request returned HTTP {response.status_code}")


def _pom_url(group_id: str, artifact_id: str, version: str, base_url: str) -> str:
    """Build the Maven Central URL of a POM."""
    group_path = group_id.replace('.', '/')
    return f"{base_url}/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.pom"


def clear_caches() -> None:
    """Drop the in-process lookup caches. Intended for tests."""
    _search_by_sha1.cache_clear()
    _fetch_pom_bytes.cache_clear()


class MavenCentralAPI:
    """Client for Maven Central coordinate and POM lookups."""

    def __init__(self,
                 search_url: str = DEFAULT_SEARCH_URL,
                 base_url: str = DEFAULT_BASE_URL,
                 timeout: int = DEFAULT_TIMEOUT):
        """Initialize the Maven Central client.

        Args:
            search_url: Base URL of the Maven Central search index
            base_url: Base URL of the Maven Central artifact repository
            timeout: Per-request timeout in seconds
        """
        self.search_url = search_url
        self.base_url = base_url
        self.timeout = timeout

    def find_by_sha1(self, sha1: str) -> Optional[Dict[str, Any]]:
        """Resolve Maven coordinates from a file SHA-1.

        Args:
            sha1: Hex SHA-1 digest of the artifact

        Returns:
            Dictionary with group_id, artifact_id, version, packaging, match_count
            and search_url, or None if the hash is unknown or the lookup failed
        """
        if not sha1:
            return None

        try:
            result = _search_by_sha1(sha1.strip().lower(), self.search_url, self.timeout)
        except LookupFailed as e:
            print(f"Error searching Maven Central by hash: {e}")
            return None

        if not result:
            return None

        group_id, artifact_id, version, packaging, match_count = result
        return {
            'group_id': group_id,
            'artifact_id': artifact_id,
            'version': version,
            'packaging': packaging,
            'match_count': match_count,
            'search_url': self.search_url,
        }

    def fetch_pom(self, group_id: str, artifact_id: str, version: str) -> Optional[Tuple[Any, str, str]]:
        """Fetch and parse the POM for a set of coordinates.

        Args:
            group_id: Maven group ID
            artifact_id: Maven artifact ID
            version: Maven version

        Returns:
            Tuple of (parsed XML root, raw POM text, POM URL) or None. The root is
            returned alongside the text so a caller can follow <parent> itself.
        """
        if not (group_id and artifact_id and version):
            return None

        try:
            pom_bytes = _fetch_pom_bytes(group_id, artifact_id, version, self.base_url, self.timeout)
        except LookupFailed as e:
            print(f"Error fetching POM from Maven Central: {e}")
            return None

        if not pom_bytes:
            return None

        try:
            root = ET.fromstring(pom_bytes)
        except Exception as e:
            print(f"Error parsing POM from Maven Central: {e}")
            return None

        # Only the header comments are read as text, and those are ASCII patterns
        pom_text = pom_bytes.decode('utf-8', errors='replace')
        return (root, pom_text, self.pom_url(group_id, artifact_id, version))

    def pom_url(self, group_id: str, artifact_id: str, version: str) -> str:
        """Build the Maven Central URL of a POM.

        Args:
            group_id: Maven group ID
            artifact_id: Maven artifact ID
            version: Maven version

        Returns:
            Fully qualified POM URL
        """
        return _pom_url(group_id, artifact_id, version, self.base_url)
