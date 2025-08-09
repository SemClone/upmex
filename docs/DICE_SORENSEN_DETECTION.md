# Dice-Sørensen Coefficient License Detection

## Overview
This document describes the Dice-Sørensen coefficient implementation for fuzzy license matching in UPMEX (Issue #2).

## Algorithm

### Dice-Sørensen Coefficient
The Dice-Sørensen coefficient (also known as Sørensen-Dice index) measures the similarity between two sets:

```
DSC = 2 × |A ∩ B| / (|A| + |B|)
```

Where:
- A and B are sets of n-grams from two text samples
- The coefficient ranges from 0 (no similarity) to 1 (identical)

## Implementation

### 1. Core Module
- **Module**: `src/upmex/utils/dice_sorensen.py`
- **Classes**:
  - `DiceSorensenMatcher`: Low-level n-gram matching
  - `FuzzyLicenseMatcher`: High-level license detection

### 2. Features

#### N-gram Generation
- **Bigrams** (default): Two-word sequences for accurate matching
- **Unigrams**: Single words for shorter text or fallback
- **Configurable**: Support for any n-gram size

#### Text Normalization
- Convert to lowercase
- Remove punctuation and special characters
- Strip URLs and email addresses
- Normalize whitespace

#### License Snippet Database
Pre-computed n-grams for common licenses:
- MIT, Apache-2.0, GPL-3.0, GPL-2.0
- BSD-3-Clause, ISC, LGPL-3.0, MPL-2.0
- Extensible: Can add custom license snippets

### 3. Matching Strategies

#### Bigram Matching (Primary)
- Used for texts > 100 characters
- Higher accuracy for complete license texts
- Confidence boost for scores > 0.85

#### Unigram Matching (Fallback)
- Used for shorter texts or partial matches
- Lower confidence multiplier (0.9x)
- Better for keyword-based detection

### 4. Integration with License Detector

The Dice-Sørensen matcher is integrated into the main `LicenseDetector`:

```python
from upmex.utils.license_detector import LicenseDetector

# Enable fuzzy matching (default)
detector = LicenseDetector(enable_fuzzy=True)

# Detect with both regex and fuzzy
result = detector.detect_license_from_text(text)

# Use only Dice-Sørensen
result = detector.detect_with_dice_sorensen(text, threshold=0.6)
```

## Usage Examples

### Basic Usage
```python
from upmex.utils.dice_sorensen import DiceSorensenMatcher

matcher = DiceSorensenMatcher(n_gram_size=2)

# Match against known licenses
result = matcher.match_license(license_text, threshold=0.7)
if result:
    license_id, score = result
    print(f"Detected: {license_id} (score: {score:.2f})")

# Compare two texts
similarity = matcher.compare_texts(text1, text2)
print(f"Similarity: {similarity:.2%}")
```

### Advanced Usage
```python
from upmex.utils.dice_sorensen import FuzzyLicenseMatcher

fuzzy = FuzzyLicenseMatcher()

# Get best match with confidence
result = fuzzy.match(text, confidence_threshold=0.6)
if result:
    license_id, confidence, method = result
    
# Get multiple potential matches
matches = fuzzy.match_multiple(text, max_results=3)
for license_id, confidence, method in matches:
    print(f"{license_id}: {confidence:.2%} ({method})")
```

## Detection Flow

1. **Text Input** → Normalization → N-gram generation
2. **Primary Detection**: Regex patterns (Issue #1)
3. **Fuzzy Detection**: If no regex match and text > 100 chars
   - Try bigram matching (threshold: 0.7)
   - Fall back to unigram matching (threshold: 0.65)
4. **Confidence Calculation**: Based on match score and method
5. **Result**: LicenseInfo with SPDX ID, confidence, and method

## Performance Characteristics

### Strengths
- Handles partial and modified license texts
- Robust to minor variations and typos
- Language-agnostic (works on normalized text)
- Fast: Pre-computed n-grams for known licenses

### Limitations
- Requires minimum text length (> 100 chars for best results)
- May produce false positives for generic legal text
- Lower accuracy for heavily modified licenses

## Testing

### Unit Tests
- `tests/unit/test_dice_sorensen.py` (18 tests)
  - Coefficient calculation
  - N-gram generation
  - Text normalization
  - License matching

### Integration Tests
- `tests/integration/test_fuzzy_license_detection.py` (10 tests)
  - Partial license detection
  - Modified license text
  - Multiple license detection
  - Confidence scoring

## Configuration

In `config.py`:
```python
"license_detection": {
    "methods": ["regex", "dice_sorensen"],  # Both methods enabled
    "confidence_threshold": 0.85,
    "max_text_length": 100_000
}
```

## Future Enhancements

While Issue #2 is now complete, potential improvements include:
- Trigram support for longer texts
- Weighted n-grams based on license keywords
- Machine learning model training on n-gram features
- Custom similarity thresholds per license type