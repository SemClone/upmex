# Baseline License Detection Summary

Generated: 2025-09-02

## Current Implementation Issues Observed

1. **False Positives**: Apache-2.0 licenses incorrectly detected as ECL-2.0
2. **MIT False Positives**: MIT licenses incorrectly detected as JSON and Imlib2
3. **Fuzzy matching issues**: Dice-Sørensen similarity producing incorrect matches

## Package License Detection Results

| Package | Detected Licenses | Issues |
|---------|------------------|--------|
| cobra-v1.8.1.zip | Apache-2.0, ECL-2.0 (false) | ECL-2.0 is false positive |
| express-4.21.2.tgz | MIT, JSON (false), Imlib2 (false) | JSON and Imlib2 are false positives |
| gin-v1.10.0.zip | MIT, JSON (false), Imlib2 (false) | JSON and Imlib2 are false positives |
| gson-2.10.1.jar | Apache-2.0 | Correct |
| guava-33.4.0-jre.jar | Apache-2.0, ECL-2.0 (false) | ECL-2.0 is false positive |
| Newtonsoft.Json.13.0.3.nupkg | MIT | Correct |
| rails-7.1.5.gem | MIT | Correct |
| requests-2.32.3-py3-none-any.whl | Apache-2.0, ECL-2.0 (false) | ECL-2.0 is false positive |
| serde-1.0.210.crate | MIT | Correct |
| Serilog.3.1.1.nupkg | Apache-2.0 | Correct |
| tokio-1.41.0.crate | MIT | Correct |

## Detection Methods Used

- **regex_pattern**: Basic pattern matching from metadata
- **fuzzy_hash_lsh**: LSH-based fuzzy matching (producing false positives)
- **dice_sorensen**: Text similarity (producing false positives)

## Expected Improvements with oslili

- Eliminate false positives (ECL-2.0, JSON, Imlib2)
- More accurate license text matching
- Standardized SPDX identifier mapping
- Better handling of license variations