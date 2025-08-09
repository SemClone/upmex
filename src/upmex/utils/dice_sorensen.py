"""Dice-Sørensen coefficient implementation for fuzzy license matching."""

import re
from typing import Set, List, Tuple, Optional
from collections import Counter


class DiceSorensenMatcher:
    """Implements Dice-Sørensen coefficient for license text similarity matching."""
    
    # Common license text snippets for matching
    LICENSE_SNIPPETS = {
        'MIT': [
            'permission is hereby granted free of charge to any person obtaining a copy',
            'of this software and associated documentation files',
            'to deal in the software without restriction',
            'including without limitation the rights to use copy modify merge publish',
            'distribute sublicense and or sell copies of the software',
            'the software is provided as is without warranty of any kind'
        ],
        'Apache-2.0': [
            'licensed under the apache license version 2.0',
            'you may not use this file except in compliance with the license',
            'you may obtain a copy of the license at',
            'unless required by applicable law or agreed to in writing',
            'distributed under the license is distributed on an as is basis',
            'without warranties or conditions of any kind either express or implied'
        ],
        'GPL-3.0': [
            'this program is free software you can redistribute it and or modify',
            'it under the terms of the gnu general public license',
            'as published by the free software foundation either version 3',
            'this program is distributed in the hope that it will be useful',
            'but without any warranty without even the implied warranty',
            'merchantability or fitness for a particular purpose'
        ],
        'BSD-3-Clause': [
            'redistribution and use in source and binary forms with or without modification',
            'are permitted provided that the following conditions are met',
            'redistributions of source code must retain the above copyright notice',
            'this list of conditions and the following disclaimer',
            'redistributions in binary form must reproduce the above copyright notice',
            'neither the name of the copyright holder nor the names of its contributors'
        ],
        'ISC': [
            'permission to use copy modify and or distribute this software',
            'for any purpose with or without fee is hereby granted',
            'provided that the above copyright notice and this permission notice',
            'appear in all copies',
            'the software is provided as is and the author disclaims all warranties'
        ],
        'GPL-2.0': [
            'this program is free software you can redistribute it and or modify',
            'it under the terms of the gnu general public license',
            'as published by the free software foundation either version 2',
            'or at your option any later version'
        ],
        'LGPL-3.0': [
            'this library is free software you can redistribute it and or modify',
            'it under the terms of the gnu lesser general public license',
            'as published by the free software foundation either version 3'
        ],
        'MPL-2.0': [
            'this source code form is subject to the terms of the mozilla public license',
            'if a copy of the mpl was not distributed with this file',
            'you can obtain one at'
        ]
    }
    
    def __init__(self, n_gram_size: int = 2):
        """Initialize the Dice-Sørensen matcher.
        
        Args:
            n_gram_size: Size of n-grams to use (default 2 for bigrams)
        """
        self.n_gram_size = n_gram_size
        self._prepare_license_ngrams()
    
    def _prepare_license_ngrams(self):
        """Pre-compute n-grams for known license texts."""
        self.license_ngrams = {}
        for license_id, snippets in self.LICENSE_SNIPPETS.items():
            all_ngrams = set()
            for snippet in snippets:
                normalized = self._normalize_text(snippet)
                ngrams = self._generate_ngrams(normalized)
                all_ngrams.update(ngrams)
            self.license_ngrams[license_id] = all_ngrams
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text (lowercase, no punctuation, single spaces)
        """
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove URLs and email addresses
        text = re.sub(r'https?://[^\s]+', '', text)
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', text)
        
        # Remove punctuation but keep spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
    
    def _generate_ngrams(self, text: str) -> Set[str]:
        """Generate n-grams from text.
        
        Args:
            text: Text to generate n-grams from
            
        Returns:
            Set of n-grams
        """
        if not text:
            return set()
        
        words = text.split()
        
        if self.n_gram_size == 1:
            # Unigrams (individual words)
            return set(words)
        elif self.n_gram_size == 2:
            # Bigrams (word pairs)
            return set(f"{words[i]} {words[i+1]}" 
                      for i in range(len(words) - 1))
        else:
            # General n-grams
            return set(' '.join(words[i:i+self.n_gram_size]) 
                      for i in range(len(words) - self.n_gram_size + 1))
    
    def dice_coefficient(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate Dice-Sørensen coefficient between two sets.
        
        The Dice coefficient is: 2 * |X ∩ Y| / (|X| + |Y|)
        
        Args:
            set1: First set of n-grams
            set2: Second set of n-grams
            
        Returns:
            Dice coefficient between 0 and 1
        """
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        total = len(set1) + len(set2)
        
        if total == 0:
            return 0.0
        
        return (2.0 * intersection) / total
    
    def match_license(self, text: str, threshold: float = 0.7) -> Optional[Tuple[str, float]]:
        """Match text against known licenses using Dice-Sørensen coefficient.
        
        Args:
            text: Text to match
            threshold: Minimum coefficient to consider a match (default 0.7)
            
        Returns:
            Tuple of (license_id, coefficient) or None if no match
        """
        if not text:
            return None
        
        normalized = self._normalize_text(text)
        text_ngrams = self._generate_ngrams(normalized)
        
        if not text_ngrams:
            return None
        
        best_match = None
        best_score = 0.0
        
        for license_id, license_ngrams in self.license_ngrams.items():
            score = self.dice_coefficient(text_ngrams, license_ngrams)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = license_id
        
        if best_match:
            return (best_match, best_score)
        
        return None
    
    def match_all_licenses(self, text: str) -> List[Tuple[str, float]]:
        """Match text against all known licenses and return scores.
        
        Args:
            text: Text to match
            
        Returns:
            List of (license_id, coefficient) tuples sorted by score
        """
        if not text:
            return []
        
        normalized = self._normalize_text(text)
        text_ngrams = self._generate_ngrams(normalized)
        
        if not text_ngrams:
            return []
        
        matches = []
        for license_id, license_ngrams in self.license_ngrams.items():
            score = self.dice_coefficient(text_ngrams, license_ngrams)
            if score > 0:
                matches.append((license_id, score))
        
        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
    
    def compare_texts(self, text1: str, text2: str) -> float:
        """Compare two arbitrary texts using Dice-Sørensen coefficient.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Dice coefficient between 0 and 1
        """
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        ngrams1 = self._generate_ngrams(norm1)
        ngrams2 = self._generate_ngrams(norm2)
        
        return self.dice_coefficient(ngrams1, ngrams2)
    
    def add_license_snippet(self, license_id: str, snippet: str):
        """Add a new license snippet for matching.
        
        Args:
            license_id: SPDX license identifier
            snippet: License text snippet to add
        """
        if license_id not in self.LICENSE_SNIPPETS:
            self.LICENSE_SNIPPETS[license_id] = []
        
        self.LICENSE_SNIPPETS[license_id].append(snippet)
        
        # Update n-grams
        normalized = self._normalize_text(snippet)
        ngrams = self._generate_ngrams(normalized)
        
        if license_id not in self.license_ngrams:
            self.license_ngrams[license_id] = set()
        
        self.license_ngrams[license_id].update(ngrams)
    
    def get_snippet_similarity(self, text: str, license_id: str) -> List[Tuple[str, float]]:
        """Get similarity scores for each snippet of a specific license.
        
        Args:
            text: Text to compare
            license_id: License to compare against
            
        Returns:
            List of (snippet, score) tuples
        """
        if license_id not in self.LICENSE_SNIPPETS:
            return []
        
        normalized = self._normalize_text(text)
        text_ngrams = self._generate_ngrams(normalized)
        
        results = []
        for snippet in self.LICENSE_SNIPPETS[license_id]:
            snippet_norm = self._normalize_text(snippet)
            snippet_ngrams = self._generate_ngrams(snippet_norm)
            score = self.dice_coefficient(text_ngrams, snippet_ngrams)
            results.append((snippet[:50] + "...", score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results


class FuzzyLicenseMatcher:
    """High-level fuzzy license matcher using Dice-Sørensen coefficient."""
    
    def __init__(self):
        """Initialize the fuzzy matcher."""
        self.bigram_matcher = DiceSorensenMatcher(n_gram_size=2)
        self.unigram_matcher = DiceSorensenMatcher(n_gram_size=1)
    
    def match(self, text: str, confidence_threshold: float = 0.6) -> Optional[Tuple[str, float, str]]:
        """Match text to a license using multiple strategies.
        
        Args:
            text: Text to match
            confidence_threshold: Minimum confidence for a match
            
        Returns:
            Tuple of (license_id, confidence, method) or None
        """
        if not text or len(text) < 50:
            return None
        
        # Try bigram matching first (more accurate for longer texts)
        bigram_result = self.bigram_matcher.match_license(text, threshold=0.7)
        if bigram_result:
            license_id, score = bigram_result
            # Boost confidence for very high scores
            confidence = min(1.0, score * 1.1) if score > 0.85 else score
            if confidence >= confidence_threshold:
                return (license_id, confidence, 'dice_sorensen_bigram')
        
        # Try unigram matching for shorter or partial matches
        unigram_result = self.unigram_matcher.match_license(text, threshold=0.65)
        if unigram_result:
            license_id, score = unigram_result
            # Slightly lower confidence for unigram matches
            confidence = score * 0.9
            if confidence >= confidence_threshold:
                return (license_id, confidence, 'dice_sorensen_unigram')
        
        return None
    
    def match_multiple(self, text: str, max_results: int = 3) -> List[Tuple[str, float, str]]:
        """Find multiple potential license matches.
        
        Args:
            text: Text to match
            max_results: Maximum number of results to return
            
        Returns:
            List of (license_id, confidence, method) tuples
        """
        if not text:
            return []
        
        results = []
        
        # Get bigram matches
        bigram_matches = self.bigram_matcher.match_all_licenses(text)
        for license_id, score in bigram_matches[:max_results]:
            if score > 0.5:
                confidence = min(1.0, score * 1.1) if score > 0.85 else score
                results.append((license_id, confidence, 'dice_sorensen_bigram'))
        
        # If we don't have enough good matches, try unigrams
        if len(results) < max_results:
            unigram_matches = self.unigram_matcher.match_all_licenses(text)
            for license_id, score in unigram_matches:
                if score > 0.5:
                    # Check if we already have this license
                    if not any(r[0] == license_id for r in results):
                        confidence = score * 0.9
                        results.append((license_id, confidence, 'dice_sorensen_unigram'))
                        if len(results) >= max_results:
                            break
        
        # Sort by confidence
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]