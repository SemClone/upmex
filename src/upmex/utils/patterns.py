"""Shared patterns for license file detection."""

import re
from typing import List, Pattern

# Common license file name patterns (case-insensitive)
LICENSE_FILE_NAMES = [
    'LICENSE',
    'LICENSE.txt',
    'LICENSE.md',
    'LICENSE.rst',
    'LICENCE',
    'LICENCE.txt',
    'LICENCE.md',
    'COPYING',
    'COPYING.txt',
    'COPYING.LESSER',
    'COPYRIGHT',
    'COPYRIGHT.txt',
    'NOTICE',
    'NOTICE.txt',
    'LEGAL',
    'LEGAL.txt',
    'MIT-LICENSE',
    'MIT-LICENSE.txt',
    'APACHE-LICENSE',
    'BSD-LICENSE',
    'GPL-LICENSE',
]

# Regex patterns for matching license files
LICENSE_FILE_PATTERNS_REGEX = [
    re.compile(r'^LICENSE(?:\.\w+)?$', re.IGNORECASE),
    re.compile(r'^LICENCE(?:\.\w+)?$', re.IGNORECASE),
    re.compile(r'^COPYING(?:\.\w+)?$', re.IGNORECASE),
    re.compile(r'^COPYRIGHT(?:\.\w+)?$', re.IGNORECASE),
    re.compile(r'^NOTICE(?:\.\w+)?$', re.IGNORECASE),
    re.compile(r'^LEGAL(?:\.\w+)?$', re.IGNORECASE),
    re.compile(r'^MIT-LICENSE(?:\.\w+)?$', re.IGNORECASE),
    re.compile(r'^APACHE-LICENSE(?:\.\w+)?$', re.IGNORECASE),
    re.compile(r'^BSD-LICENSE(?:\.\w+)?$', re.IGNORECASE),
    re.compile(r'^GPL-LICENSE(?:\.\w+)?$', re.IGNORECASE),
]


def is_license_file(filename: str) -> bool:
    """Check if a filename indicates a license file.
    
    Args:
        filename: Name of the file to check
        
    Returns:
        True if the filename matches a license file pattern
    """
    for pattern in LICENSE_FILE_PATTERNS_REGEX:
        if pattern.match(filename):
            return True
    return False


def get_license_file_patterns() -> List[str]:
    """Get list of license file name patterns for searching.
    
    Returns:
        List of license file name patterns
    """
    return LICENSE_FILE_NAMES


def get_license_file_regex_patterns() -> List[Pattern]:
    """Get compiled regex patterns for license file matching.
    
    Returns:
        List of compiled regex patterns
    """
    return LICENSE_FILE_PATTERNS_REGEX