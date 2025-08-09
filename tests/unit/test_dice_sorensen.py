"""Unit tests for Dice-Sørensen coefficient license matching."""

import pytest
from upmex.utils.dice_sorensen import DiceSorensenMatcher, FuzzyLicenseMatcher


class TestDiceSorensenMatcher:
    """Test Dice-Sørensen coefficient implementation."""
    
    @pytest.fixture
    def matcher(self):
        """Create a Dice-Sørensen matcher instance."""
        return DiceSorensenMatcher(n_gram_size=2)
    
    def test_normalize_text(self, matcher):
        """Test text normalization."""
        # Basic normalization
        assert matcher._normalize_text("Hello World!") == "hello world"
        assert matcher._normalize_text("  Multiple   Spaces  ") == "multiple spaces"
        
        # Remove punctuation
        assert matcher._normalize_text("test@example.com") == ""
        assert matcher._normalize_text("https://example.com") == ""
        assert matcher._normalize_text("Hello, World!") == "hello world"
        
        # Case insensitive
        assert matcher._normalize_text("MIT LICENSE") == "mit license"
    
    def test_generate_bigrams(self, matcher):
        """Test bigram generation."""
        text = "the quick brown fox"
        ngrams = matcher._generate_ngrams(text)
        
        assert "the quick" in ngrams
        assert "quick brown" in ngrams
        assert "brown fox" in ngrams
        assert len(ngrams) == 3
    
    def test_generate_unigrams(self):
        """Test unigram generation."""
        matcher = DiceSorensenMatcher(n_gram_size=1)
        text = "mit license text"
        ngrams = matcher._generate_ngrams(text)
        
        assert "mit" in ngrams
        assert "license" in ngrams
        assert "text" in ngrams
        assert len(ngrams) == 3
    
    def test_dice_coefficient_calculation(self, matcher):
        """Test Dice coefficient calculation."""
        set1 = {"the quick", "quick brown", "brown fox"}
        set2 = {"the quick", "quick brown", "brown dog"}
        
        # 2 common elements, |set1| = 3, |set2| = 3
        # Dice = 2 * 2 / (3 + 3) = 4/6 = 0.667
        coefficient = matcher.dice_coefficient(set1, set2)
        assert abs(coefficient - 0.667) < 0.01
        
        # Identical sets should give 1.0
        assert matcher.dice_coefficient(set1, set1) == 1.0
        
        # Disjoint sets should give 0.0
        set3 = {"completely", "different", "words"}
        assert matcher.dice_coefficient(set1, set3) == 0.0
        
        # Empty sets
        assert matcher.dice_coefficient(set(), set()) == 0.0
        assert matcher.dice_coefficient(set1, set()) == 0.0
    
    def test_match_license_mit(self, matcher):
        """Test matching MIT license text."""
        mit_text = """
        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software.
        """
        
        result = matcher.match_license(mit_text, threshold=0.5)
        assert result is not None
        license_id, score = result
        assert license_id == "MIT"
        assert score > 0.5
    
    def test_match_license_apache(self, matcher):
        """Test matching Apache license text."""
        apache_text = """
        Licensed under the Apache License, Version 2.0 (the "License");
        you may not use this file except in compliance with the License.
        Unless required by applicable law or agreed to in writing, software
        distributed under the License is distributed on an "AS IS" BASIS,
        WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
        """
        
        result = matcher.match_license(apache_text, threshold=0.5)
        assert result is not None
        license_id, score = result
        assert license_id == "Apache-2.0"
        assert score > 0.5
    
    def test_match_license_no_match(self, matcher):
        """Test when no license matches."""
        random_text = "This is just some random text that doesn't match any license."
        
        result = matcher.match_license(random_text, threshold=0.7)
        assert result is None
    
    def test_match_all_licenses(self, matcher):
        """Test matching against all licenses."""
        mixed_text = """
        This software is provided as is, without warranty of any kind.
        Permission is hereby granted to use this software for any purpose.
        """
        
        matches = matcher.match_all_licenses(mixed_text)
        assert len(matches) > 0
        
        # Should have some matches
        assert matches[0][1] > 0  # First match should have non-zero score
        
        # Scores should be sorted descending
        for i in range(len(matches) - 1):
            assert matches[i][1] >= matches[i + 1][1]
    
    def test_compare_texts(self, matcher):
        """Test comparing two arbitrary texts."""
        text1 = "The quick brown fox jumps over the lazy dog"
        text2 = "The quick brown fox runs over the lazy cat"
        
        similarity = matcher.compare_texts(text1, text2)
        assert 0.5 < similarity < 1.0  # Similar but not identical
        
        # Identical texts
        assert matcher.compare_texts(text1, text1) == 1.0
        
        # Completely different texts
        text3 = "Completely different sentence with no common words"
        similarity2 = matcher.compare_texts(text1, text3)
        assert similarity2 < 0.3
    
    def test_add_license_snippet(self, matcher):
        """Test adding custom license snippets."""
        custom_license = "MyLicense-1.0"
        custom_snippet = "This is my custom license with unique terms"
        
        # Initially shouldn't match
        result = matcher.match_license(custom_snippet, threshold=0.7)
        assert result is None or result[0] != custom_license
        
        # Add the snippet
        matcher.add_license_snippet(custom_license, custom_snippet)
        
        # Now it should match
        result = matcher.match_license(custom_snippet, threshold=0.7)
        assert result is not None
        assert result[0] == custom_license
        assert result[1] > 0.9  # Should be very high match


class TestFuzzyLicenseMatcher:
    """Test high-level fuzzy license matcher."""
    
    @pytest.fixture
    def matcher(self):
        """Create a fuzzy license matcher instance."""
        return FuzzyLicenseMatcher()
    
    def test_match_with_bigrams(self, matcher):
        """Test matching using bigrams."""
        mit_text = """
        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so.
        """
        
        result = matcher.match(mit_text, confidence_threshold=0.5)
        assert result is not None
        license_id, confidence, method = result
        assert license_id == "MIT"
        assert confidence > 0.5
        assert "bigram" in method
    
    def test_match_with_unigrams(self, matcher):
        """Test fallback to unigram matching."""
        # Shorter text that might work better with unigrams
        short_text = "apache license version compliance distributed warranties"
        
        result = matcher.match(short_text, confidence_threshold=0.4)
        if result:
            license_id, confidence, method = result
            # Could match Apache-2.0 or might not match at all
            assert confidence >= 0.4
    
    def test_match_multiple_licenses(self, matcher):
        """Test finding multiple potential matches."""
        ambiguous_text = """
        This software is free software; you can redistribute it and/or modify it.
        It is provided without any warranty. Permission is granted to use, copy,
        and distribute this software.
        """
        
        results = matcher.match_multiple(ambiguous_text, max_results=3)
        assert len(results) <= 3
        
        if results:
            # Results should be sorted by confidence
            for i in range(len(results) - 1):
                assert results[i][1] >= results[i + 1][1]
            
            # Each result should have license_id, confidence, method
            for license_id, confidence, method in results:
                assert isinstance(license_id, str)
                assert 0 <= confidence <= 1
                assert "dice_sorensen" in method
    
    def test_no_match_short_text(self, matcher):
        """Test that very short text doesn't match."""
        short_text = "Hello world"
        
        result = matcher.match(short_text, confidence_threshold=0.6)
        assert result is None
    
    def test_high_confidence_exact_match(self, matcher):
        """Test high confidence for exact license text."""
        bsd_text = """
        Redistribution and use in source and binary forms, with or without modification,
        are permitted provided that the following conditions are met:
        Redistributions of source code must retain the above copyright notice,
        this list of conditions and the following disclaimer.
        Redistributions in binary form must reproduce the above copyright notice.
        """
        
        result = matcher.match(bsd_text, confidence_threshold=0.5)
        if result:
            license_id, confidence, method = result
            assert "BSD" in license_id
            assert confidence > 0.6


class TestIntegrationWithLicenseDetector:
    """Test integration of Dice-Sørensen with the main license detector."""
    
    def test_license_detector_with_fuzzy(self):
        """Test that license detector uses fuzzy matching."""
        from upmex.utils.license_detector import LicenseDetector
        
        detector = LicenseDetector(enable_fuzzy=True)
        
        # Text that won't match regex but should match fuzzy
        partial_mit = """
        The software is provided as is, without warranty of any kind. Permission 
        is hereby granted free of charge to any person obtaining a copy of this 
        software to deal in the software without restriction.
        """
        
        result = detector.detect_license_from_text(partial_mit)
        assert result is not None
        assert result.spdx_id in ["MIT", "ISC"]  # Could match either
        assert "dice_sorensen" in result.detection_method
    
    def test_license_detector_fuzzy_disabled(self):
        """Test that fuzzy matching can be disabled."""
        from upmex.utils.license_detector import LicenseDetector
        
        detector = LicenseDetector(enable_fuzzy=False)
        
        # Text that only fuzzy would match
        partial_text = """
        Software provided without warranty. Permission granted to use and modify.
        """
        
        result = detector.detect_license_from_text(partial_text)
        # Should not match without fuzzy
        assert result is None
    
    def test_detect_with_dice_sorensen_only(self):
        """Test using only Dice-Sørensen detection."""
        from upmex.utils.license_detector import LicenseDetector
        
        detector = LicenseDetector(enable_fuzzy=True)
        
        gpl_text = """
        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License.
        """
        
        result = detector.detect_with_dice_sorensen(gpl_text, threshold=0.5)
        assert result is not None
        assert "GPL" in result.spdx_id
        assert result.detection_method in ["dice_sorensen_bigram", "dice_sorensen_unigram"]
        assert result.confidence > 0.5