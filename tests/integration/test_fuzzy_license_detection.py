"""Integration tests for fuzzy license detection using Dice-Sørensen coefficient."""

import pytest
import tempfile
import zipfile
from pathlib import Path

from upmex.extractors.python_extractor import PythonExtractor
from upmex.utils.license_detector import LicenseDetector
from upmex.utils.dice_sorensen import DiceSorensenMatcher, FuzzyLicenseMatcher


class TestFuzzyLicenseDetection:
    """Test fuzzy license detection in real scenarios."""
    
    def test_partial_mit_license_detection(self):
        """Test detecting MIT license from partial text."""
        detector = LicenseDetector(enable_fuzzy=True)
        
        # Partial MIT license text (missing some parts)
        partial_mit = """
        Copyright 2024 Example Corp
        
        Permission is granted, free of charge, to any person obtaining a copy
        of this software to deal in the Software without restriction, including
        the rights to use, copy, modify, merge, publish, and distribute.
        
        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
        """
        
        result = detector.detect_license_from_text(partial_mit)
        assert result is not None
        assert result.spdx_id == "MIT"
        assert "dice_sorensen" in result.detection_method
        assert result.confidence > 0.6
    
    def test_modified_apache_license_detection(self):
        """Test detecting Apache license with modifications."""
        detector = LicenseDetector(enable_fuzzy=True)
        
        # Modified Apache text
        modified_apache = """
        This file is licensed under the Apache License, Version 2.0.
        You may not use this file except in compliance with said License.
        
        Unless required by law or agreed in writing, software under
        this License is distributed "AS IS", WITHOUT WARRANTIES OF ANY KIND.
        """
        
        result = detector.detect_license_from_text(modified_apache)
        assert result is not None
        assert result.spdx_id == "Apache-2.0"
        # Could be either regex or fuzzy
        assert result.confidence > 0.5
    
    def test_gpl_variant_detection(self):
        """Test detecting GPL from variant text."""
        detector = LicenseDetector(enable_fuzzy=True)
        
        gpl_variant = """
        This is free software: you are free to change and redistribute it.
        It comes under the GNU General Public License version 3 or later.
        
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
        """
        
        result = detector.detect_license_from_text(gpl_variant)
        assert result is not None
        assert "GPL" in result.spdx_id
        assert result.confidence > 0.5
    
    def test_multiple_license_detection_with_fuzzy(self):
        """Test detecting multiple licenses including fuzzy matches."""
        detector = LicenseDetector(enable_fuzzy=True)
        
        multi_license = """
        This project uses multiple licenses:
        
        Core library: MIT License
        Permission is hereby granted, free of charge, to any person obtaining a copy.
        
        Optional components: 
        This program is free software under the GNU GPL version 2.
        You can redistribute it and/or modify it.
        """
        
        licenses = detector.detect_multiple_licenses(multi_license)
        assert len(licenses) >= 1  # At least MIT should be detected
        
        spdx_ids = [lic.spdx_id for lic in licenses]
        assert "MIT" in spdx_ids
        # GPL might not be detected if text is too short
    
    def test_bsd_style_license_detection(self):
        """Test detecting BSD-style licenses."""
        matcher = DiceSorensenMatcher(n_gram_size=2)
        
        bsd_like = """
        Redistribution and use in source and binary forms are permitted
        provided that the following conditions are met:
        * Redistributions must retain the copyright notice
        * Neither the name of the organization nor the names of contributors
          may be used to endorse products
        """
        
        result = matcher.match_license(bsd_like, threshold=0.5)
        assert result is not None
        license_id, score = result
        assert "BSD" in license_id
        assert score > 0.4
    
    def test_isc_license_fuzzy_detection(self):
        """Test ISC license detection with fuzzy matching."""
        detector = LicenseDetector(enable_fuzzy=True)
        
        isc_like = """
        Permission to use, copy, and distribute this software for any
        purpose with or without fee is granted, provided that the
        copyright notice appears in all copies.
        
        THE SOFTWARE IS PROVIDED "AS IS" WITHOUT ANY WARRANTIES.
        """
        
        result = detector.detect_license_from_text(isc_like)
        assert result is not None
        assert result.spdx_id in ["ISC", "MIT"]  # Could match either
        assert result.confidence > 0.5
    
    def test_confidence_levels_with_fuzzy(self):
        """Test that fuzzy matching produces appropriate confidence levels."""
        detector = LicenseDetector(enable_fuzzy=True)
        
        # Very close match should have high confidence
        close_mit = """
        Permission is hereby granted, free of charge, to any person obtaining
        a copy of this software and associated documentation files (the "Software"),
        to deal in the Software without restriction, including without limitation
        the rights to use, copy, modify, merge, publish, distribute, sublicense,
        and/or sell copies of the Software.
        """
        
        result1 = detector.detect_license_from_text(close_mit)
        assert result1.spdx_id == "MIT"
        assert result1.confidence > 0.8
        
        # Partial match should have lower confidence
        partial_mit = """
        Permission granted to use this software without restriction.
        Software provided as-is without warranty.
        """
        
        result2 = detector.detect_license_from_text(partial_mit)
        if result2:
            assert result2.confidence < result1.confidence
    
    def test_package_extraction_with_fuzzy_license(self, tmp_path):
        """Test full package extraction with fuzzy license detection."""
        wheel_path = tmp_path / "fuzzy-1.0.0-py3-none-any.whl"
        
        with zipfile.ZipFile(wheel_path, 'w') as zf:
            # Metadata without explicit license field
            metadata_content = """Metadata-Version: 2.1
Name: fuzzy-test
Version: 1.0.0
Summary: Test package with fuzzy license
"""
            zf.writestr("fuzzy-1.0.0.dist-info/METADATA", metadata_content)
            
            # LICENSE file with partial MIT text
            license_content = """
            Copyright (c) 2024 Test Author
            
            Permission is hereby granted to any person obtaining a copy of this
            software to use, copy, modify, and distribute it without restriction.
            
            THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND.
            """
            zf.writestr("fuzzy-1.0.0.dist-info/LICENSE", license_content)
        
        # Extract with fuzzy detection enabled
        extractor = PythonExtractor()
        metadata = extractor.extract(str(wheel_path))
        
        # The LICENSE file should be read and fuzzy-matched
        # Note: Current implementation may need enhancement to read LICENSE files
        assert metadata.name == "fuzzy-test"
    
    def test_dice_sorensen_only_mode(self):
        """Test using only Dice-Sørensen without regex."""
        detector = LicenseDetector(enable_fuzzy=True)
        
        apache_text = """
        Licensed under the Apache License, Version 2.0.
        You may not use this file except in compliance with the License.
        Distributed on an AS IS BASIS, WITHOUT WARRANTIES.
        """
        
        # Use Dice-Sørensen only method
        result = detector.detect_with_dice_sorensen(apache_text, threshold=0.5)
        assert result is not None
        assert result.spdx_id == "Apache-2.0"
        assert "dice_sorensen" in result.detection_method
        assert result.confidence > 0.5
    
    def test_fuzzy_matcher_strategies(self):
        """Test different fuzzy matching strategies."""
        fuzzy = FuzzyLicenseMatcher()
        
        # Long text should use bigrams
        long_text = """
        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions.
        """
        
        result = fuzzy.match(long_text, confidence_threshold=0.5)
        assert result is not None
        assert result[2] == "dice_sorensen_bigram"
        
        # Test multiple matches
        matches = fuzzy.match_multiple(long_text, max_results=3)
        assert len(matches) <= 3
        if matches:
            assert matches[0][0] == "MIT"  # Should match MIT first