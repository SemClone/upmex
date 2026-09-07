"""A declared licence URL is resolved by what it names, or by what it serves."""

import ipaddress
import zipfile

import pytest

from upmex.extractors.java_extractor import JavaExtractor
from upmex.licenses import license_url


# The licence in full, because that is what a licence URL serves and what a
# detector needs to identify it as a whole document. A fragment matches only by
# phrase, which this deliberately refuses.
MIT_LICENCE = """MIT License

Copyright (c) 2026 Example Corp

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def pom_declaring(name, url):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <groupId>com.example</groupId>
    <artifactId>declared</artifactId>
    <version>1.0.0</version>
    <licenses>
        <license>
            <name>{name}</name>
            <url>{url}</url>
        </license>
    </licenses>
</project>"""


def jar_with(tmp_path, pom):
    jar_path = tmp_path / "declared.jar"
    with zipfile.ZipFile(jar_path, 'w') as zf:
        zf.writestr("META-INF/maven/com.example/declared/pom.xml", pom)
    return str(jar_path)


@pytest.fixture(autouse=True)
def _no_cached_fetches():
    """The fetch cache outlives one test, and these hand it different bodies."""
    license_url.fetch_license_text.cache_clear()
    yield
    license_url.fetch_license_text.cache_clear()


# Where the hosts in these tests resolve to. Stubbed rather than looked up so
# the suite does not need DNS, and so a host is refused for the reason the test
# is about rather than because resolution failed.
RESOLVES_TO = {
    'example.com': '93.184.216.34',
    'example.org': '93.184.216.34',
    'raw.githubusercontent.com': '185.199.108.133',
}


@pytest.fixture(autouse=True)
def _no_dns(monkeypatch):
    def getaddrinfo(host, port=None, *args, **kwargs):
        # The port is carried through: this stands in for real resolution, and
        # a connection built from a sockaddr with port 0 goes nowhere.
        resolved_port = port if isinstance(port, int) else 0
        if host in RESOLVES_TO:
            return [(2, 1, 6, '', (RESOLVES_TO[host], resolved_port))]
        # A literal address needs no lookup, and the internal targets these
        # tests use are all literals.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise OSError(f"{host} is not stubbed; tests must not use DNS")
        return [(2, 1, 6, '', (host, resolved_port))]

    monkeypatch.setattr(license_url.socket, 'getaddrinfo', getaddrinfo)


class TestCanonicalUrls:
    """An address whose meaning is fixed is read without asking the network."""

    @pytest.mark.parametrize("url,expected", [
        ("http://www.apache.org/licenses/LICENSE-2.0.txt", "Apache-2.0"),
        ("https://apache.org/licenses/LICENSE-2.0", "Apache-2.0"),
        ("http://www.apache.org/licenses/LICENSE-2.0.html", "Apache-2.0"),
        ("https://opensource.org/licenses/MIT", "MIT"),
        ("https://opensource.org/licenses/mit/", "MIT"),
        ("https://www.eclipse.org/legal/epl-2.0/", "EPL-2.0"),
        ("http://www.gnu.org/licenses/lgpl-2.1.html", "LGPL-2.1-only"),
        ("https://www.mozilla.org/MPL/2.0/", "MPL-2.0"),
    ])
    def test_it_names_the_licence(self, url, expected):
        assert license_url.canonical_spdx_id(url) == expected

    @pytest.mark.parametrize("url", [
        "",
        "https://example.com/my-own-licence.txt",
        "https://github.com/square/okhttp/blob/master/LICENSE.txt",
        "not a url at all",
    ])
    def test_it_declines_anything_else(self, url):
        assert license_url.canonical_spdx_id(url) is None

    @pytest.mark.parametrize("url", [
        # A host that merely ends with a tabulated one.
        "https://apache.org.evil.com/licenses/LICENSE-2.0",
        "https://notapache.org/licenses/LICENSE-2.0",
        # userinfo, which reads as the tabulated host if the authority is
        # split on the colon rather than parsed.
        "https://apache.org:x@evil.com/licenses/LICENSE-2.0",
        "https://apache.org@evil.com/licenses/LICENSE-2.0",
        # The tabulated address as a query string rather than the target.
        "https://evil.com/?x=apache.org/licenses/LICENSE-2.0",
        # A tabulated path under an untabulated host.
        "https://evil.com/licenses/LICENSE-2.0",
        # A backslash, which urlparse and requests read differently: this is
        # host apache.org to one and evil.com to the other.
        "https://evil.com\\@apache.org/licenses/LICENSE-2.0",
        # A licence is served over the web, so no other scheme is tabulated.
        "ftp://apache.org/licenses/LICENSE-2.0",
        "file:///licenses/LICENSE-2.0",
    ])
    def test_a_host_that_only_looks_tabulated_is_refused(self, url):
        assert license_url.canonical_spdx_id(url) is None

    def test_every_tabulated_address_is_reachable(self):
        """Rows are keyed on the normalised form, and a row written with a
        suffix the lookup strips would otherwise never match. Two were."""
        unreachable = [
            f"https://{host}{path}"
            for host, path in license_url.CANONICAL_LICENCE_URLS
            if license_url.canonical_spdx_id(f"https://{host}{path}") is None
        ]
        assert unreachable == []

    def test_the_lgpl_page_is_not_read_as_the_gpl(self):
        """The LGPL-2.1 page quotes the GPL-2.0 at length.

        Detecting over its text reports GPL-2.0-only more confidently than the
        licence the URL actually names, which is why the address wins here.
        """
        assert license_url.canonical_spdx_id(
            "https://www.gnu.org/licenses/lgpl-2.1.html") == "LGPL-2.1-only"


class TestRawTextUrls:
    """A file is asked for as a file, not as the page that displays it."""

    def test_a_github_blob_becomes_raw(self):
        assert license_url.raw_text_url(
            "https://github.com/square/okhttp/blob/master/LICENSE.txt"
        ) == "https://raw.githubusercontent.com/square/okhttp/master/LICENSE.txt"

    def test_a_gitlab_blob_becomes_raw(self):
        assert license_url.raw_text_url(
            "https://gitlab.com/group/proj/blob/main/LICENSE"
        ) == "https://gitlab.com/group/proj/raw/main/LICENSE"

    def test_anything_else_is_left_alone(self):
        for url in ("https://example.com/LICENSE.txt",
                    "https://github.com/square/okhttp"):
            assert license_url.raw_text_url(url) == url


class TestHtmlPages:
    """A licence served as a page is the licence with markup around it."""

    def test_markup_is_reduced_to_its_text(self):
        text = license_url.html_to_text(
            "<html><head><title>x</title>"
            "<style>p{color:red}</style></head>"
            "<body><p>Apache License</p><p>Version 2.0</p></body></html>"
        )
        assert "Apache License" in text
        assert "Version 2.0" in text
        assert "color:red" not in text

    def test_blocks_do_not_weld_their_words_together(self):
        """Without a break at a block boundary the last word of one runs into
        the first of the next, and a licence stops matching the licence it
        is."""
        text = license_url.html_to_text("<p>the Apache</p><p>License</p>")
        assert "ApacheLicense" not in text
        assert "the Apache" in text and "License" in text

    @pytest.mark.parametrize("markup,joined", [
        ("<li>one</li><li>two</li>", "onetwo"),
        ("<div>one</div><div>two</div>", "onetwo"),
        ("one<br/>two", "onetwo"),
        ("<td>one</td><td>two</td>", "onetwo"),
        ("<h2>one</h2><p>two</p>", "onetwo"),
    ])
    def test_every_block_boundary_breaks(self, markup, joined):
        assert joined not in license_url.html_to_text(markup)

    def test_a_plain_licence_is_recognised_as_not_markup(self):
        assert not license_url.looks_like_html(MIT_LICENCE)

    def test_a_page_is_recognised_as_markup(self):
        assert license_url.looks_like_html("<!DOCTYPE html><html><body>hi</body></html>")


class TestOnlyStrongEvidenceNamesALicence:
    """A phrase spotted inside a document does not say what the document is."""

    @pytest.mark.parametrize("match_type,confidence", [
        ("exact_hash", 1.0),
        ("tag", 1.0),
        ("spdx_identifier", 1.0),
        # Scored, and scoring well: the real Apache text reaches 1.0 and the
        # real MIT text 0.997.
        ("license_file", 0.997),
        ("text_similarity", 0.99),
    ])
    def test_evidence_about_the_whole_document_counts(self, match_type, confidence):
        assert license_url.is_strong_evidence(match_type, confidence)

    @pytest.mark.parametrize("match_type,confidence", [
        ("keyword", 0.9),
        ("regex", 0.6),
        ("documentation", 1.0),
        ("text_similarity", 0.8),
        (None, 1.0),
        # This module names every fetched body LICENSE, so license_file on its
        # own says only that. gnu.org's LGPL-2.1 page -- a licence wrapped in a
        # web page -- scores exactly this.
        ("license_file", 0.6),
    ])
    def test_a_phrase_inside_it_does_not(self, match_type, confidence):
        assert not license_url.is_strong_evidence(match_type, confidence)


class TestFetchIsGuarded:
    """Package metadata is untrusted, and a URL in it can name anything."""

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "ftp://example.com/LICENSE",
        "gopher://example.com/LICENSE",
        "",
    ])
    def test_only_http_reaches_the_network(self, url, monkeypatch):
        def fail(*args, **kwargs):
            raise AssertionError(f"{url} should not have been fetched")

        monkeypatch.setattr(license_url.requests, 'get', fail)
        assert license_url.fetch_license_text(url) is None

    def test_a_body_over_the_cap_is_refused(self, monkeypatch):
        monkeypatch.setattr(
            license_url.requests, 'get',
            _responding(b'x' * (license_url.MAX_LICENCE_BYTES + 1)))
        assert license_url.fetch_license_text("https://example.com/LICENSE") is None

    def test_the_cap_holds_after_decompression(self, monkeypatch):
        """A small compressed body can expand into a very large one. The read
        stops at the cap rather than asking for the whole thing and measuring
        it afterwards, which would be measuring memory already spent."""
        decompressed = b'A' * (50 * license_url.MAX_LICENCE_BYTES)

        class _Bomb(_FakeResponse):
            def iter_content(self, chunk_size=1, decode_unicode=False):
                # Stands in for the decoder: hands back decoded chunks for as
                # long as it is asked, so a caller that does not stop does not
                # finish.
                delivered = 0
                while delivered < len(decompressed):
                    yield decompressed[delivered:delivered + chunk_size]
                    delivered += chunk_size

        read = []

        def get(*args, **kwargs):
            response = _Bomb(b'', 200)
            read.append(response)
            return response

        monkeypatch.setattr(license_url.requests, 'get', get)
        assert license_url.fetch_license_text("https://example.com/LICENSE") is None

    def test_a_non_200_is_not_read(self, monkeypatch):
        monkeypatch.setattr(
            license_url.requests, 'get', _responding(b'nope', status=404))
        assert license_url.fetch_license_text("https://example.com/LICENSE") is None

    def test_a_transport_failure_is_not_raised_at_the_caller(self, monkeypatch):
        def boom(*args, **kwargs):
            raise OSError("connection reset")

        monkeypatch.setattr(license_url.requests, 'get', boom)
        assert license_url.fetch_license_text("https://example.com/LICENSE") is None

    @pytest.mark.parametrize("address", [
        "10.0.0.1", "127.0.0.1", "169.254.169.254", "0.0.0.0",
        # Carrier-grade NAT, which is neither private nor reserved and is not
        # the public internet either.
        "100.64.0.1",
        "::1", "fd00::1",
        # IPv4 loopback written as IPv6.
        "::ffff:127.0.0.1",
    ])
    def test_an_address_off_the_public_internet_is_refused(self, address):
        assert not license_url._resolves_to_a_public_address(address)

    def test_a_public_address_is_allowed(self):
        assert license_url._resolves_to_a_public_address("93.184.216.34")

    def test_a_backslash_authority_is_read_as_requests_will_send_it(self, monkeypatch):
        """urlparse reads this as example.com; requests sends it to the
        metadata address. Checking one and fetching the other is how a check
        like this gets walked past."""
        def fail(*args, **kwargs):
            raise AssertionError("should not have been fetched")

        monkeypatch.setattr(license_url.requests, 'get', fail)
        assert license_url.fetch_license_text(
            "http://169.254.169.254\\@example.com/latest/meta-data/") is None

    def test_a_redirect_to_an_internal_address_is_refused(self, monkeypatch):
        """requests follows redirects itself, so a URL that passes the check
        could otherwise hand the request to one that would not."""
        monkeypatch.setattr(
            license_url.requests, 'get',
            _redirecting({
                "https://example.com/LICENSE": "http://169.254.169.254/latest/meta-data/",
            }))
        assert license_url.fetch_license_text("https://example.com/LICENSE") is None

    def test_a_redirect_to_localhost_is_refused(self, monkeypatch):
        monkeypatch.setattr(
            license_url.requests, 'get',
            _redirecting({
                "https://example.com/LICENSE": "http://127.0.0.1:8080/admin",
            }))
        assert license_url.fetch_license_text("https://example.com/LICENSE") is None

    def test_a_redirect_to_a_public_address_is_followed(self, monkeypatch):
        monkeypatch.setattr(
            license_url.requests, 'get',
            _redirecting({"https://example.com/LICENSE": "https://example.org/LICENSE.txt"},
                         bodies={"https://example.org/LICENSE.txt": MIT_LICENCE.encode()}))
        assert "Permission is hereby granted" in license_url.fetch_license_text(
            "https://example.com/LICENSE")

    def test_a_redirect_loop_gives_up(self, monkeypatch):
        monkeypatch.setattr(
            license_url.requests, 'get',
            _redirecting({
                "https://example.com/LICENSE": "https://example.com/LICENSE",
            }))
        assert license_url.fetch_license_text("https://example.com/LICENSE") is None

    def test_a_page_is_returned_as_text(self, monkeypatch):
        monkeypatch.setattr(
            license_url.requests, 'get',
            _responding(b"<!DOCTYPE html><html><body><p>Apache License</p></body></html>"))
        text = license_url.fetch_license_text("https://example.com/LICENSE")
        assert "Apache License" in text
        assert "<p>" not in text


class TestAgainstARealServer:
    """Driven through real requests over a real socket, with only the address
    check stubbed.

    Everything else here hands fetch_license_text a fake response object, and a
    fake answers whatever it is asked. That hid a call to iter_content with a
    decode_content argument requests does not accept: the fake took it, the
    real one raised TypeError, the broad except swallowed that, and every
    fetch in production returned None while the suite stayed green.
    """

    @pytest.fixture
    def serving(self, monkeypatch):
        import http.server
        import socketserver
        import threading

        state = {'body': b'', 'headers': []}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                for name, value in state['headers']:
                    self.send_header(name, value)
                self.send_header('Content-Length', str(len(state['body'])))
                self.end_headers()
                try:
                    self.wfile.write(state['body'])
                except OSError:
                    # The client stopped reading at the cap, which is the point.
                    pass

            def log_message(self, *args):
                pass

        server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()

        # The server is on loopback, which the address check refuses by design.
        # That check has its own tests; this one is about the read path.
        monkeypatch.setattr(
            license_url, '_resolves_to_a_public_address', lambda host: True)

        def serve(body, headers=()):
            state['body'] = body
            state['headers'] = list(headers)
            return f"http://127.0.0.1:{server.server_address[1]}/LICENSE"

        yield serve
        server.shutdown()

    def test_a_licence_is_fetched_and_returned(self, serving):
        url = serving(MIT_LICENCE.encode())
        text = license_url.fetch_license_text(url)
        assert text is not None, "the real read path returned nothing"
        assert "Permission is hereby granted" in text

    def test_a_gzipped_licence_is_decoded(self, serving):
        import gzip
        url = serving(gzip.compress(MIT_LICENCE.encode()),
                      [('Content-Encoding', 'gzip')])
        text = license_url.fetch_license_text(url)
        assert text is not None
        assert "Permission is hereby granted" in text

    def test_a_compressed_bomb_is_refused_without_being_materialised(self, serving):
        """A small compressed body that expands past the cap. Memory is
        measured because returning None is not on its own proof the cap
        worked -- a raised exception returns None too."""
        import gzip
        import tracemalloc

        payload = b'A' * (200 * license_url.MAX_LICENCE_BYTES)
        url = serving(gzip.compress(payload), [('Content-Encoding', 'gzip')])

        tracemalloc.start()
        try:
            assert license_url.fetch_license_text(url) is None
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert peak < 10 * license_url.MAX_LICENCE_BYTES, (
            f"peaked at {peak:,} bytes decoding a {len(payload):,} byte body"
        )

    def test_an_html_page_is_reduced_to_its_text(self, serving):
        url = serving(b"<!DOCTYPE html><html><body><p>Apache License</p>"
                      b"<p>Version 2.0</p></body></html>")
        text = license_url.fetch_license_text(url)
        assert "Apache License" in text
        assert "<p>" not in text


class TestDeclaredUrlsInAPom:
    """What the extractor does with the two paths, end to end."""

    def test_a_canonical_url_resolves_without_the_network(self, tmp_path, monkeypatch):
        def fail(*args, **kwargs):
            raise AssertionError("a canonical URL should not be fetched")

        monkeypatch.setattr(license_url.requests, 'get', fail)

        metadata = JavaExtractor().extract(jar_with(tmp_path, pom_declaring(
            "The Apache Software License, Version 2.0",
            "http://www.apache.org/licenses/LICENSE-2.0.txt",
        )))

        assert [lic.spdx_id for lic in metadata.licenses] == ["Apache-2.0"]

    def test_an_unknown_url_is_not_fetched_outside_registry_mode(self, tmp_path, monkeypatch):
        def fail(*args, **kwargs):
            raise AssertionError("registry_mode is off; nothing should be fetched")

        monkeypatch.setattr(license_url.requests, 'get', fail)

        metadata = JavaExtractor().extract(jar_with(tmp_path, pom_declaring(
            "Weird Corp Licence 1.0", "https://example.com/our-licence.txt",
        )))

        # Unclassifiable, so the declaration is kept as the POM wrote it.
        assert [lic.spdx_id for lic in metadata.licenses] == ["Weird Corp Licence 1.0"]

    def test_an_unknown_url_is_identified_by_what_it_serves(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            license_url.requests, 'get',
            _serving({"https://example.com/our-licence.txt": MIT_LICENCE.encode()}))

        metadata = JavaExtractor(registry_mode=True).extract(jar_with(
            tmp_path,
            pom_declaring("Weird Corp Licence 1.0", "https://example.com/our-licence.txt"),
        ))

        assert [lic.spdx_id for lic in metadata.licenses] == ["MIT"]

    def test_a_dead_url_leaves_the_declaration_as_written(self, tmp_path, monkeypatch):
        monkeypatch.setattr(license_url.requests, 'get', _serving({}))

        metadata = JavaExtractor(registry_mode=True).extract(jar_with(
            tmp_path,
            pom_declaring("Weird Corp Licence 1.0", "https://example.com/gone.txt"),
        ))

        assert [lic.spdx_id for lic in metadata.licenses] == ["Weird Corp Licence 1.0"]


class _FakeResponse:
    is_redirect = False

    def __init__(self, body, status):
        self.status_code = status
        self.encoding = 'utf-8'
        self._body = body

    # Signature kept identical to requests.Response.iter_content; a fake that
    # accepts more than the real one hides calls the real one would refuse.
    def iter_content(self, chunk_size=1, decode_unicode=False):
        for start in range(0, len(self._body), chunk_size):
            yield self._body[start:start + chunk_size]

    def json(self):
        return {}

    def close(self):
        pass


def _responding(body, status=200):
    """Answer every request the same way."""
    def get(*args, **kwargs):
        return _FakeResponse(body, status)
    return get


def _redirecting(redirects, bodies=None):
    """Answer the named URLs with a redirect, and the rest from bodies."""
    bodies = bodies or {}

    def get(url, *args, **kwargs):
        if url in redirects:
            return _FakeRedirect(redirects[url])
        if url in bodies:
            return _FakeResponse(bodies[url], 200)
        return _FakeResponse(b'', 404)
    return get


class _FakeRedirect:
    is_redirect = True

    def __init__(self, location):
        self.status_code = 302
        self.encoding = 'utf-8'
        self.headers = {'Location': location}

    def iter_content(self, chunk_size=1, decode_unicode=False):
        return iter(())

    def close(self):
        pass


def _serving(bodies):
    """Answer only the URLs named, and 404 everything else.

    Registry mode reaches other APIs through the same requests.get, and a
    licence body handed to those would be answering a question nobody asked.
    """
    def get(url, *args, **kwargs):
        if url in bodies:
            return _FakeResponse(bodies[url], 200)
        return _FakeResponse(b'', 404)
    return get
