"""Tests for the ways a NuGet package can declare its licence.

A .nuspec can state its licence as an SPDX expression, as a file shipped inside
the package, or as a URL. Each is a separate path, and a package that declares a
licence upmex cannot classify must not come back looking unlicensed.
"""

import zipfile

import pytest

from upmex.core.extractor import PackageExtractor
from upmex.extractors.nuget_extractor import NuGetExtractor

MIT_TEXT = """MIT License

Copyright (c) 2024 Example

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
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT."""


def make_nupkg(path, license_xml='', extra_files=None):
    """Build a .nupkg whose .nuspec differs only in its licence declaration."""
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr("package.nuspec", f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
  <metadata>
    <id>Example.Package</id>
    <version>1.0.0</version>
    <authors>Example</authors>
    <description>A package</description>
    {license_xml}
  </metadata>
</package>""")
        for name, content in (extra_files or {}).items():
            zf.writestr(name, content)
    return str(path)


def licenses_of(path):
    return [(lic.spdx_id, lic.detection_method) for lic in
            PackageExtractor().extract(path).licenses]


class TestLicenseExpression:
    """<license type="expression"> holds an SPDX expression."""

    def test_recognised_identifier(self, tmp_path):
        path = make_nupkg(tmp_path / "p.nupkg", '<license type="expression">MIT</license>')

        assert licenses_of(path) == [("MIT", "osslili_tag")]

    @pytest.mark.parametrize('expression', [
        'MIT OR Apache-2.0',
        'GPL-2.0-only WITH Classpath-exception-2.0',
        'Apache-2.0 AND MIT',
    ])
    def test_compound_expression_is_kept_whole(self, tmp_path, expression):
        """Reporting one arm of a compound expression would change its meaning."""
        path = make_nupkg(tmp_path / "p.nupkg", f'<license type="expression">{expression}</license>')

        assert licenses_of(path) == [(expression, "declared")]

    def test_unclassifiable_expression_is_kept(self, tmp_path):
        """A LicenseRef is a valid declaration that is not detectable as text."""
        path = make_nupkg(tmp_path / "p.nupkg",
                          '<license type="expression">LicenseRef-Proprietary</license>')

        assert licenses_of(path) == [("LicenseRef-Proprietary", "declared")]

    def test_empty_expression(self, tmp_path):
        path = make_nupkg(tmp_path / "p.nupkg", '<license type="expression"></license>')

        assert licenses_of(path) == []


class TestLicenseFile:
    """<license type="file"> names a file shipped inside the package."""

    def test_file_is_read(self, tmp_path):
        path = make_nupkg(tmp_path / "p.nupkg",
                          '<license type="file">LICENSE.txt</license>',
                          {"LICENSE.txt": MIT_TEXT})

        assert [spdx for spdx, _ in licenses_of(path)] == ["MIT"]

    def test_windows_separator_and_nested_path(self, tmp_path):
        path = make_nupkg(tmp_path / "p.nupkg",
                          '<license type="file">docs\\LICENSE.md</license>',
                          {"docs/LICENSE.md": MIT_TEXT})

        assert [spdx for spdx, _ in licenses_of(path)] == ["MIT"]

    def test_declared_file_is_recorded_even_when_missing(self, tmp_path):
        path = make_nupkg(tmp_path / "p.nupkg", '<license type="file">GONE.txt</license>')
        metadata = PackageExtractor().extract(path)

        assert metadata.licenses == []
        assert metadata.raw_metadata['license_file'] == "GONE.txt"


class TestLicenseUrl:
    """Older packages declare only a licenseUrl."""

    @pytest.mark.parametrize('url', [
        'https://licenses.nuget.org/MIT',
        'https://opensource.org/licenses/MIT',
    ])
    def test_identifier_is_recovered(self, tmp_path, url):
        path = make_nupkg(tmp_path / "p.nupkg", f'<licenseUrl>{url}</licenseUrl>')

        assert [spdx for spdx, _ in licenses_of(path)] == ["MIT"]

    def test_unreadable_url_is_still_recorded(self, tmp_path):
        path = make_nupkg(tmp_path / "p.nupkg",
                          '<licenseUrl>https://example.com/eula</licenseUrl>')
        metadata = PackageExtractor().extract(path)

        assert metadata.licenses == []
        assert metadata.raw_metadata['license_url'] == "https://example.com/eula"

    @pytest.mark.parametrize('url,expected', [
        ('https://licenses.nuget.org/MIT', 'MIT'),
        ('https://licenses.nuget.org/Apache-2.0/', 'Apache-2.0'),
        ('http://opensource.org/licenses/BSD-3-Clause', 'BSD-3-Clause'),
        ('https://example.com/license', None),
        ('https://licenses.nuget.org/', None),
    ])
    def test_url_parsing(self, url, expected):
        assert NuGetExtractor()._license_id_from_url(url) == expected


class TestUndeclaredLicense:
    """A package may ship a licence file without pointing at it."""

    def test_archive_is_scanned_as_a_last_resort(self, tmp_path):
        path = make_nupkg(tmp_path / "p.nupkg", '', {"LICENSE.txt": MIT_TEXT})

        assert [spdx for spdx, _ in licenses_of(path)] == ["MIT"]

    def test_no_licence_anywhere(self, tmp_path):
        """Absence is a valid answer and must not raise."""
        path = make_nupkg(tmp_path / "p.nupkg")
        metadata = PackageExtractor().extract(path)

        assert metadata.licenses == []
        assert metadata.name == "Example.Package"


class TestRealPackages:
    """The published packages kept in test-packages/ still extract."""

    @pytest.mark.parametrize('filename,expected_name,expected_license', [
        ('Newtonsoft.Json.13.0.3.nupkg', 'Newtonsoft.Json', 'MIT'),
        ('Serilog.3.1.1.nupkg', 'Serilog', 'Apache-2.0'),
    ])
    def test_extraction(self, filename, expected_name, expected_license):
        from pathlib import Path

        package = Path('test-packages') / filename
        if not package.exists():
            pytest.skip(f"{filename} is not available")

        metadata = PackageExtractor().extract(str(package))

        assert metadata.name == expected_name
        assert expected_license in [lic.spdx_id for lic in metadata.licenses]
        assert metadata.purl == f"pkg:nuget/{expected_name}@{metadata.version}"
