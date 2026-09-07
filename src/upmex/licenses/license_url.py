"""Identify the licence a declared URL points at.

Package metadata often names its licence only as prose plus a URL:

    <license>
      <name>The Apache Software License, Version 2.0</name>
      <url>http://www.apache.org/licenses/LICENSE-2.0.txt</url>
    </license>

The prose is unclassifiable on its own -- no detector should be asked to tell
"The Apache Software License, Version 2.0" from a sentence that merely mentions
it -- so the URL is what carries the answer.

Reading the URL string was how upmex used to do this, by handing osslili
"License: <url>" and letting its tag patterns recognise the address. That put
the whole mechanism inside a dependency's pattern list, where it silently
disappeared in osslili 1.8.0 and took every URL-declared licence with it.

So the URL is resolved here instead, in two steps that do not depend on a
detector recognising an address at all:

1. A table of canonical licence URLs, consulted offline. These are addresses
   whose meaning is fixed -- ``.../licenses/LICENSE-2.0.txt`` is the Apache 2.0
   text and nothing else -- so no fetch can improve on the answer.
2. Failing that, and only when the caller allows network access, fetch what the
   URL serves and identify the retrieved text. This is the general case: it
   works for a URL nobody has tabulated, and it identifies the licence from its
   own text rather than from its address.
"""

import ipaddress
import logging
import re
import socket
from functools import lru_cache
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from requests.models import PreparedRequest

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

# Licence texts are tens of kilobytes. A cap keeps a URL that answers with
# something enormous from being read into memory, and anything this large is
# not a licence anyway.
MAX_LICENCE_BYTES = 1_000_000

# Only these reach the network. Package metadata is untrusted input, and a URL
# in it can name anything the host running upmex can reach: file:// would read
# local files and the exotic schemes requests supports are no better.
FETCHABLE_SCHEMES = ('http', 'https')

# Redirects are followed by hand so every hop is checked, not just the one the
# package named. A licence that has moved has moved once or twice; a chain
# longer than this is not leading anywhere useful.
MAX_REDIRECTS = 5

# Addresses whose meaning is fixed, matched on host plus path so a query string
# or a trailing slash does not defeat the lookup. Kept deliberately short: an
# entry here overrides reading the licence's own text, so it must be an address
# that can only ever mean one licence.
CANONICAL_LICENCE_URLS = {
    ('apache.org', '/licenses/license-2.0'): 'Apache-2.0',
    ('apache.org', '/licenses/license-2.0.txt'): 'Apache-2.0',
    ('apache.org', '/licenses/license-2.0.html'): 'Apache-2.0',
    ('opensource.org', '/licenses/apache-2.0'): 'Apache-2.0',
    ('opensource.org', '/licenses/bsd-2-clause'): 'BSD-2-Clause',
    ('opensource.org', '/licenses/bsd-3-clause'): 'BSD-3-Clause',
    ('opensource.org', '/licenses/isc'): 'ISC',
    ('opensource.org', '/licenses/mit'): 'MIT',
    ('opensource.org', '/license/mit'): 'MIT',
    ('eclipse.org', '/legal/epl-v10.html'): 'EPL-1.0',
    ('eclipse.org', '/legal/epl-2.0'): 'EPL-2.0',
    ('eclipse.org', '/org/documents/epl-v10.php'): 'EPL-1.0',
    ('gnu.org', '/licenses/gpl-2.0'): 'GPL-2.0-only',
    ('gnu.org', '/licenses/gpl-3.0'): 'GPL-3.0-only',
    ('gnu.org', '/licenses/lgpl-2.1'): 'LGPL-2.1-only',
    ('gnu.org', '/licenses/lgpl-3.0'): 'LGPL-3.0-only',
    ('mozilla.org', '/mpl/2.0'): 'MPL-2.0',
    ('unlicense.org', ''): 'Unlicense',
    ('creativecommons.org', '/publicdomain/zero/1.0'): 'CC0-1.0',
}

def _normalised_target(host, path):
    """Reduce a host and path to the form the table is keyed on."""
    host = (host or '').lower()
    if host.startswith('www.'):
        host = host[4:]

    path = (path or '').lower().rstrip('/')
    # Both spellings of the same document, so neither suffix is keyed on.
    for suffix in ('.txt', '.html', '.htm', '.php'):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break

    return host, path


# Normalised the same way a looked-up URL is, so a row written with a suffix
# is still reachable. Written out rather than normalised by hand because two
# rows were keyed on a path the lookup could never produce, which made EPL-1.0
# unrecognisable from either of its addresses.
_CANONICAL_BY_NORMALISED = {
    _normalised_target(host, path): spdx_id
    for (host, path), spdx_id in CANONICAL_LICENCE_URLS.items()
}


# Only evidence of this kind is allowed to name the licence a URL declares.
#
# A fetched page is not always the licence: gnu.org's LGPL-2.1 page quotes the
# GPL-2.0 text at length, so a keyword or regex match over it reports
# GPL-2.0-only with more confidence than the LGPL-2.1 the URL actually names.
# Reporting the wrong licence is worse than reporting none, so a fetch has to
# produce evidence about the document as a whole -- its hash, an SPDX tag it
# carries, or its text matching a known licence closely -- and never a phrase
# spotted somewhere inside it.
# Derived from the content itself, so they stand on their own.
STRONG_MATCH_TYPES = ('exact_hash', 'tag', 'spdx_identifier')

# Whether a document *is* a licence, which needs a score to go with it.
# license_file belongs here rather than above: it is partly a judgement about
# the filename, and the filename is one this module invented for a fetched
# body, so on its own it says only that upmex called the file LICENSE. The real
# Apache text matches at 1.0 and the MIT text at 0.997, while gnu.org's
# LGPL-2.1 page -- a licence wrapped in a web page -- reaches only 0.6.
SCORED_MATCH_TYPES = ('license_file', 'text_similarity')
STRONG_TEXT_CONFIDENCE = 0.95


class _TextExtractor(HTMLParser):
    """Collect the text of an HTML document, dropping script and style."""

    SKIPPED = ('script', 'style', 'head', 'nav', 'footer')

    # Tags that end a line when a browser renders them. Without this the text
    # of "<p>the Apache</p><p>License</p>" comes out as "the ApacheLicense",
    # welding the last word of every block to the first of the next -- which
    # is a licence that no longer matches the licence it is.
    BREAKING = (
        'p', 'br', 'div', 'li', 'ul', 'ol', 'tr', 'td', 'th', 'table',
        'section', 'article', 'header', 'blockquote', 'pre', 'hr',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    )

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts = []
        self._skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIPPED:
            self._skipping += 1
        elif tag in self.BREAKING:
            self._parts.append('\n')

    def handle_startendtag(self, tag, attrs):
        if tag in self.BREAKING:
            self._parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self.SKIPPED and self._skipping:
            self._skipping -= 1
        elif tag in self.BREAKING:
            self._parts.append('\n')

    def handle_data(self, data):
        if not self._skipping:
            self._parts.append(data)

    def text(self):
        return ''.join(self._parts)


def looks_like_html(body: str) -> bool:
    """Is this body markup rather than the licence itself?"""
    head = body.lstrip()[:512].lower()
    return head.startswith('<!doctype html') or head.startswith('<html') or '<body' in head


def html_to_text(body: str) -> str:
    """Reduce an HTML page to the text a reader would see.

    A licence served as a web page is the licence with markup around it. Handing
    the markup to a detector buries the text among tags and attributes, which
    costs a text-similarity match the confidence it needs.
    """
    parser = _TextExtractor()
    try:
        parser.feed(body)
        parser.close()
    except Exception as error:
        logger.debug("Could not parse HTML licence page: %s", error)
        return body

    text = parser.text()
    # Markup indents generously; collapse it so the text reads as prose.
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    return text.strip()


def canonical_spdx_id(url: str) -> Optional[str]:
    """The licence a canonical URL names, without fetching anything.

    Returns:
        An SPDX identifier, or None if this is not an address whose meaning is
        fixed
    """
    if not url:
        return None

    # Normalised the way a fetch would normalise it, so this table cannot be
    # matched by an authority that reads as a tabulated host here and as a
    # different one everywhere else. Nothing is fetched; the point is that one
    # spelling of a URL has one meaning.
    normalised = _as_requests_would_send_it(url)
    if not normalised:
        return None

    try:
        parsed = urlparse(normalised)
    except ValueError:
        return None

    # A licence is served over the web. ftp://apache.org/licenses/LICENSE-2.0
    # is not the address this table is about, and reading it as one would let a
    # package name any scheme it liked and still be believed.
    if (parsed.scheme or '').lower() not in FETCHABLE_SCHEMES:
        return None

    host, path = _normalised_target(parsed.hostname, parsed.path)
    if not host:
        return None

    return _CANONICAL_BY_NORMALISED.get((host, path))


def raw_text_url(url: str) -> str:
    """Rewrite an address that serves a licence as a page to one that serves it as text.

    A POM pointing at a file on GitHub names the blob viewer, which is an
    application around the file rather than the file. Asking for the raw form
    returns the licence itself, which identifies by hash instead of by whatever
    survives the surrounding page.
    """
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url

    host = (parsed.hostname or '').lower()
    path = parsed.path or ''

    if host in ('github.com', 'www.github.com') and '/blob/' in path:
        return urlunparse((
            parsed.scheme or 'https',
            'raw.githubusercontent.com',
            path.replace('/blob/', '/', 1),
            '', '', '',
        ))

    if host in ('gitlab.com', 'www.gitlab.com') and '/blob/' in path:
        return urlunparse((
            parsed.scheme or 'https',
            parsed.netloc,
            path.replace('/blob/', '/raw/', 1),
            '', '', '',
        ))

    return url


def _resolves_to_a_public_address(host: str) -> bool:
    """Does this host name somewhere on the public internet?

    A licence URL comes out of package metadata, so it names whatever the
    package's author wanted it to. Left alone, that is a request the machine
    running upmex can be made to send anywhere it can reach: a cloud instance's
    metadata service, a service bound to localhost, a host inside the network.
    Nothing is read back out -- a metadata document is not a licence and
    produces no evidence -- but the request itself is the problem.

    Note the residual gap: the address is checked here and resolved again by
    the request, so a name that answers differently between the two calls is
    not caught. Closing that means pinning the connection to the address that
    was checked, which is a larger change than this is worth; a package that
    can win that race gains a blind request and nothing more.
    """
    if not host:
        return False

    try:
        addresses = socket.getaddrinfo(host, None)
    except OSError as error:
        logger.debug("Licence URL host %s did not resolve: %s", host, error)
        return False

    for info in addresses:
        try:
            address = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        # is_global rather than a list of the ranges to refuse: enumerating
        # them missed carrier-grade NAT, which is neither private nor reserved
        # and is not the public internet either.
        if not address.is_global:
            logger.debug("Refusing licence URL host %s at %s", host, address)
            return False

    return bool(addresses)


def _as_requests_would_send_it(url: str) -> Optional[str]:
    """The URL requests will actually request, or None if it cannot build one.

    urlparse and requests do not always read an authority the same way:
    ``http://169.254.169.254\\@example.com/`` is host example.com to urlparse
    and host 169.254.169.254 to requests, because requests normalises the
    backslash first. Checking one and fetching the other is how a check like
    this gets walked past, so the check is applied to what will be sent.
    """
    try:
        prepared = PreparedRequest()
        prepared.prepare_url(url.strip(), None)
    except Exception as error:
        logger.debug("Licence URL %s could not be prepared: %s", url, error)
        return None
    return prepared.url


def _may_be_fetched(url: str) -> bool:
    """Is this an address a licence may be fetched from?"""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if (parsed.scheme or '').lower() not in FETCHABLE_SCHEMES:
        logger.debug("Refusing to fetch licence URL with scheme %r", parsed.scheme)
        return False

    return _resolves_to_a_public_address(parsed.hostname or '')


@lru_cache(maxsize=256)
def fetch_license_text(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """Retrieve what a licence URL serves, as text.

    Cached for the process lifetime: one URL is declared by many packages in a
    scan, and its content does not change between them.

    Returns:
        The licence text, or None if nothing usable came back. A failure is
        cached too -- a licence URL that is dead or is not a licence stays that
        way for the run, and retrying it once per package would be slower for
        the same answer.
    """
    if not url:
        return None

    target = _as_requests_would_send_it(url)
    if not target:
        return None
    target = raw_text_url(target)
    response = None

    for _ in range(MAX_REDIRECTS + 1):
        # Normalised first, then checked, then sent as checked. Checked every
        # hop rather than once at the start: requests follows redirects on its
        # own, which would let a URL that passes this check hand the request
        # straight to one that would not.
        target = _as_requests_would_send_it(target)
        if not target or not _may_be_fetched(target):
            return None

        try:
            response = requests.get(
                target,
                timeout=timeout,
                headers={'Accept': 'text/plain, text/html;q=0.9, */*;q=0.1'},
                stream=True,
                allow_redirects=False,
            )
        except Exception as error:
            logger.debug("Licence URL %s could not be fetched: %s", url, error)
            return None

        if not response.is_redirect:
            break

        location = response.headers.get('Location') or ''
        response.close()
        if not location:
            logger.debug("Licence URL %s redirected without a location", url)
            return None
        # Relative, so resolved against the hop it came from.
        target = urljoin(target, location)
    else:
        logger.debug("Licence URL %s redirected more than %d times", url, MAX_REDIRECTS)
        if response is not None:
            response.close()
        return None

    oversized = False
    try:
        if response.status_code != 200:
            logger.debug("Licence URL %s answered HTTP %s", url, response.status_code)
            return None

        # Read in chunks and stop at the cap, rather than trusting
        # Content-Length, which a server may understate or omit. Chunked
        # because the cap has to hold after decompression: a small gzip body
        # can expand into a very large one, and asking for the whole thing and
        # measuring it afterwards is measuring memory already spent.
        # iter_content decodes as it goes -- it streams the raw response with
        # decode_content set -- so the running total is of the licence as it
        # will be read, and there is no decode_content argument to pass here.
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_LICENCE_BYTES:
                oversized = True
                break
            chunks.append(chunk)
        body = b'' if oversized else b''.join(chunks)
    except Exception as error:
        logger.debug("Licence URL %s could not be read: %s", url, error)
        return None
    finally:
        response.close()

    if oversized:
        logger.debug("Licence URL %s served more than %d bytes", url, MAX_LICENCE_BYTES)
        return None
    if not body:
        return None

    encoding = response.encoding or 'utf-8'
    try:
        text = body.decode(encoding, errors='replace')
    except LookupError:
        text = body.decode('utf-8', errors='replace')

    if looks_like_html(text):
        text = html_to_text(text)

    return text or None


def is_strong_evidence(match_type: Optional[str], confidence: float) -> bool:
    """Is this evidence about the document as a whole, rather than a phrase in it?

    See STRONG_MATCH_TYPES for why anything weaker is refused.
    """
    if match_type in STRONG_MATCH_TYPES:
        return True
    return match_type in SCORED_MATCH_TYPES and confidence >= STRONG_TEXT_CONFIDENCE


def licence_filename(url: str) -> str:
    """A filename for the fetched body, so a detector reads it as a licence file.

    osslili weighs evidence partly by what the file is called: the same text in
    LICENSE is the licence, and in README.md is a document mentioning one. What
    a URL serves was asked for as a licence, so it is named like one.
    """
    return 'LICENSE'
