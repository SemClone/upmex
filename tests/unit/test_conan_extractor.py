"""Tests for the Conan extractor.

The AST walk over conanfile.py is version sensitive: it used ast.Str, which was
removed in Python 3.12, and nothing exercised it, so extraction raised on every
Conan package on current Python.
"""

import io
import tarfile
from pathlib import Path

import pytest

from upmex.core.extractor import PackageExtractor
from upmex.core.models import PackageType
from upmex.extractors.conan_extractor import ConanExtractor

CONANFILE = '''from conan import ConanFile

class FmtConan(ConanFile):
    name = "fmt"
    version = "10.2.1"
    license = "MIT"
    author = "Example Author"
    url = "https://github.com/fmtlib/fmt"
    homepage = "https://fmt.dev"
    description = "A formatting library"
    topics = ("formatting", "logging", "cpp")
'''


def make_conan_tgz(path, conanfile=CONANFILE):
    """Build a Conan package archive holding a conanfile.py."""
    with tarfile.open(path, 'w:gz') as tar:
        data = conanfile.encode('utf-8')
        info = tarfile.TarInfo(name='conanfile.py')
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return str(path)


class TestConanExtraction:

    def test_conanfile_py_is_parsed(self, tmp_path):
        """Regression guard: this raised AttributeError on Python 3.12 and later."""
        metadata = PackageExtractor().extract(make_conan_tgz(tmp_path / "fmt.tgz"))

        assert metadata.package_type == PackageType.CONAN
        assert metadata.name == "fmt"
        assert metadata.version == "10.2.1"
        assert [lic.spdx_id for lic in metadata.licenses] == ["MIT"]
        assert metadata.homepage == "https://fmt.dev"
        assert metadata.repository == "https://github.com/fmtlib/fmt"
        assert "formatting" in metadata.keywords

    def test_string_values_survive_the_ast_walk(self, tmp_path):
        """String literals parse as ast.Constant on every supported version."""
        extractor = ConanExtractor()
        import ast

        tree = ast.parse(CONANFILE)
        values = extractor._extract_from_ast(tree, CONANFILE)

        assert values['name'] == "fmt"
        assert values['license'] == "MIT"
        assert values['topics'] == ("formatting", "logging", "cpp")

    def test_extraction_does_not_raise_on_a_real_package(self):
        package = Path('test-packages/fmt-10.2.1.tgz')
        if not package.exists():
            pytest.skip("fmt-10.2.1.tgz is not available")

        metadata = PackageExtractor().extract(str(package))

        assert metadata.name == "fmt"
        assert metadata.version == "10.2.1"
