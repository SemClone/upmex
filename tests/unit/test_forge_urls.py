"""A homepage becomes the repository only when it points at a forge."""

import pytest

from upmex.extractors.ruby_extractor import points_at_a_forge


class TestAForgeUrlIsRecognised:

    @pytest.mark.parametrize("url", [
        "https://github.com/rails/rails",
        "http://github.com/rails/rails",
        "https://www.github.com/rails/rails",
        "https://GitHub.com/rails/rails",
        "https://gitlab.com/group/project",
        "https://github.com/rails/rails/",
        "https://github.com/rails/rails?tab=readme",
    ])
    def test_it_is(self, url):
        assert points_at_a_forge(url)


class TestAnythingElseIsNot:
    """Substring matching read every one of these as a forge, because the URL
    text contained the host somewhere other than the authority."""

    @pytest.mark.parametrize("url", [
        # A host that merely ends with a forge host.
        "https://evil-github.com.example.net/rails/rails",
        "https://notgithub.com/rails/rails",
        "https://github.com.evil.net/rails/rails",
        # The forge host in a path or a query, on another host entirely.
        "https://example.com/github.com/rails",
        "https://example.com/?u=https://github.com/rails",
        # userinfo, which reads as the forge if the authority is split on '@'
        # or on ':' rather than parsed.
        "https://github.com@evil.net/rails",
        "https://github.com:x@evil.net/rails",
        # A subdomain is a different service, not the forge.
        "https://gist.github.com/someone/1234",
        "https://raw.githubusercontent.com/rails/rails/main/README.md",
    ])
    def test_it_is_not(self, url):
        assert not points_at_a_forge(url)

    @pytest.mark.parametrize("url", ["", None, "not a url", "://broken"])
    def test_nothing_usable_is_not(self, url):
        assert not points_at_a_forge(url)
