"""SPDX License Manager - Downloads and manages SPDX license texts."""

import os
import json
import hashlib
import requests
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import re

class SPDXLicenseManager:
    """Manages SPDX license texts and metadata."""
    
    SPDX_LICENSE_LIST_URL = "https://raw.githubusercontent.com/spdx/license-list-data/main/json/licenses.json"
    SPDX_LICENSE_TEXT_URL = "https://raw.githubusercontent.com/spdx/license-list-data/main/text/{}.txt"
    
    # License aliases mapping common variations to SPDX IDs
    LICENSE_ALIASES = {
        # GPL variations
        'GPL-3.0': ['GPL-3.0-only', 'GPL-3.0-or-later'],
        'GPL-2.0': ['GPL-2.0-only', 'GPL-2.0-or-later'],
        'GPLv3': ['GPL-3.0-only', 'GPL-3.0-or-later'],
        'GPLv2': ['GPL-2.0-only', 'GPL-2.0-or-later'],
        'GPL v3': ['GPL-3.0-only'],
        'GPL v2': ['GPL-2.0-only'],
        'GPL3': ['GPL-3.0-only'],
        'GPL2': ['GPL-2.0-only'],
        
        # LGPL variations
        'LGPL-3.0': ['LGPL-3.0-only', 'LGPL-3.0-or-later'],
        'LGPL-2.1': ['LGPL-2.1-only', 'LGPL-2.1-or-later'],
        'LGPLv3': ['LGPL-3.0-only'],
        'LGPLv2.1': ['LGPL-2.1-only'],
        
        # AGPL variations
        'AGPL-3.0': ['AGPL-3.0-only', 'AGPL-3.0-or-later'],
        'AGPLv3': ['AGPL-3.0-only'],
        
        # BSD variations
        'BSD': ['BSD-3-Clause', 'BSD-2-Clause'],
        'BSD-3': ['BSD-3-Clause'],
        'BSD-2': ['BSD-2-Clause'],
        'New BSD': ['BSD-3-Clause'],
        'Simplified BSD': ['BSD-2-Clause'],
        
        # Apache variations
        'Apache': ['Apache-2.0'],
        'Apache 2': ['Apache-2.0'],
        'Apache2': ['Apache-2.0'],
        'ASL 2.0': ['Apache-2.0'],
        
        # MIT variations
        'MIT/X11': ['MIT'],
        'Expat': ['MIT'],
        
        # Mozilla variations
        'MPL': ['MPL-2.0'],
        'MPL2': ['MPL-2.0'],
        
        # Eclipse variations
        'EPL': ['EPL-2.0'],
        'Eclipse': ['EPL-2.0'],
    }
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize SPDX license manager.
        
        Args:
            cache_dir: Directory to cache license data
        """
        if cache_dir is None:
            # Use package data directory
            self.cache_dir = Path(__file__).parent / "data"
        else:
            self.cache_dir = Path(cache_dir)
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.licenses_file = self.cache_dir / "spdx_licenses.json"
        self.texts_dir = self.cache_dir / "texts"
        self.hashes_file = self.cache_dir / "license_hashes.json"
        
        self.texts_dir.mkdir(exist_ok=True)
        
        self.licenses = {}
        self.license_texts = {}
        self.license_hashes = {}
        self.normalized_hashes = {}
    
    def download_license_list(self) -> bool:
        """Download the SPDX license list.
        
        Returns:
            True if successful
        """
        try:
            print("Downloading SPDX license list...")
            response = requests.get(self.SPDX_LICENSE_LIST_URL, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            self.licenses = {lic['licenseId']: lic for lic in data['licenses']}
            
            # Save to cache
            with open(self.licenses_file, 'w') as f:
                json.dump(self.licenses, f, indent=2)
            
            print(f"Downloaded {len(self.licenses)} licenses")
            return True
            
        except Exception as e:
            print(f"Error downloading license list: {e}")
            return False
    
    def download_license_text(self, license_id: str) -> Optional[str]:
        """Download text for a specific license.
        
        Args:
            license_id: SPDX license identifier
            
        Returns:
            License text or None
        """
        try:
            url = self.SPDX_LICENSE_TEXT_URL.format(license_id)
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            text = response.text
            
            # Save to cache
            text_file = self.texts_dir / f"{license_id}.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(text)
            
            return text
            
        except Exception as e:
            print(f"Error downloading {license_id}: {e}")
            return None
    
    def download_all_license_texts(self, limit: Optional[int] = None):
        """Download all license texts.
        
        Args:
            limit: Maximum number to download (for testing)
        """
        if not self.licenses:
            self.load_or_download()
        
        count = 0
        for license_id in self.licenses:
            if limit and count >= limit:
                break
            
            text_file = self.texts_dir / f"{license_id}.txt"
            if not text_file.exists():
                print(f"Downloading {license_id}...")
                self.download_license_text(license_id)
                count += 1
            else:
                # Load from cache
                with open(text_file, 'r', encoding='utf-8') as f:
                    self.license_texts[license_id] = f.read()
    
    def normalize_text(self, text: str) -> str:
        """Normalize license text for comparison.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        # Convert to lowercase
        text = text.lower()
        
        # Remove copyright lines and years
        text = re.sub(r'copyright.*?\d{4}.*?\n', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\(c\).*?\d{4}.*?\n', '', text, flags=re.IGNORECASE)
        text = re.sub(r'©.*?\d{4}.*?\n', '', text)
        
        # Remove URLs
        text = re.sub(r'https?://[^\s]+', '', text)
        
        # Remove email addresses
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', text)
        
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove all punctuation except periods and commas
        text = re.sub(r'[^\w\s.,]', '', text)
        
        # Remove template variables like <year>, <owner>, etc.
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove common variable placeholders
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\{.*?\}', '', text)
        
        return text.strip()
    
    def compute_fuzzy_hash(self, text: str) -> str:
        """Compute fuzzy hash for text using simple LSH.
        
        Args:
            text: Text to hash
            
        Returns:
            Fuzzy hash string
        """
        # Normalize the text first
        normalized = self.normalize_text(text)
        
        # Create shingles (3-grams of words)
        words = normalized.split()
        shingles = set()
        for i in range(len(words) - 2):
            shingle = ' '.join(words[i:i+3])
            shingles.add(shingle)
        
        # Create MinHash signature (simplified LSH)
        # Use multiple hash functions
        signature = []
        for seed in range(20):  # 20 hash functions
            min_hash = float('inf')
            for shingle in shingles:
                # Hash with seed
                h = hashlib.sha256((str(seed) + shingle).encode()).hexdigest()
                h_int = int(h[:8], 16)
                min_hash = min(min_hash, h_int)
            signature.append(min_hash)
        
        # Convert to hex string
        hash_str = ''.join(f'{h:08x}' for h in signature[:10])  # Use first 10 for compactness
        return f"lsh:{hash_str}"
    
    def compute_all_hashes(self):
        """Compute fuzzy hashes for all license texts."""
        print("Computing fuzzy hashes for all licenses...")
        
        for license_id, text in self.license_texts.items():
            # Regular hash of original text
            sha256 = hashlib.sha256(text.encode()).hexdigest()
            self.license_hashes[license_id] = sha256
            
            # Fuzzy hash of normalized text
            fuzzy_hash = self.compute_fuzzy_hash(text)
            self.normalized_hashes[license_id] = fuzzy_hash
        
        # Save hashes
        hashes_data = {
            'text_hashes': self.license_hashes,
            'fuzzy_hashes': self.normalized_hashes
        }
        
        with open(self.hashes_file, 'w') as f:
            json.dump(hashes_data, f, indent=2)
        
        print(f"Computed hashes for {len(self.license_hashes)} licenses")
    
    def load_or_download(self) -> bool:
        """Load licenses from cache or download if needed.
        
        Returns:
            True if licenses are available
        """
        # Try to load from cache first
        if self.licenses_file.exists():
            with open(self.licenses_file, 'r') as f:
                self.licenses = json.load(f)
            # Suppress verbose output - only print in initialization
            # print(f"Loaded {len(self.licenses)} licenses from cache")
            return True
        
        # Download if not cached
        return self.download_license_list()
    
    def load_texts(self):
        """Load all cached license texts."""
        for text_file in self.texts_dir.glob("*.txt"):
            license_id = text_file.stem
            with open(text_file, 'r', encoding='utf-8') as f:
                self.license_texts[license_id] = f.read()
    
    def load_hashes(self):
        """Load precomputed hashes."""
        if self.hashes_file.exists():
            with open(self.hashes_file, 'r') as f:
                data = json.load(f)
                self.license_hashes = data.get('text_hashes', {})
                self.normalized_hashes = data.get('fuzzy_hashes', {})
    
    def find_license_by_fuzzy_hash(self, text: str, threshold: float = 0.8) -> List[Tuple[str, float]]:
        """Find licenses matching text using fuzzy hash.
        
        Args:
            text: Text to match
            threshold: Minimum similarity threshold
            
        Returns:
            List of (license_id, similarity) tuples
        """
        if not self.normalized_hashes:
            self.load_hashes()
        
        # Compute fuzzy hash of input text
        input_hash = self.compute_fuzzy_hash(text)
        input_sig = input_hash.split(':')[1]
        
        matches = []
        for license_id, stored_hash in self.normalized_hashes.items():
            stored_sig = stored_hash.split(':')[1]
            
            # Compare signatures (simplified Jaccard similarity)
            # In real implementation, we'd compare the MinHash values
            similarity = self._compare_lsh_signatures(input_sig, stored_sig)
            
            if similarity >= threshold:
                matches.append((license_id, similarity))
        
        # Sort by similarity
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
    
    def _compare_lsh_signatures(self, sig1: str, sig2: str) -> float:
        """Compare two LSH signatures.
        
        Args:
            sig1: First signature
            sig2: Second signature
            
        Returns:
            Similarity score between 0 and 1
        """
        # Simple character-level similarity for hex strings
        # In production, would compare actual MinHash values
        if len(sig1) != len(sig2):
            return 0.0
        
        matching = sum(1 for a, b in zip(sig1, sig2) if a == b)
        return matching / len(sig1)
    
    def resolve_license_id(self, license_id: str) -> str:
        """Resolve license aliases to canonical SPDX ID.
        
        Args:
            license_id: License identifier (may be alias)
            
        Returns:
            Canonical SPDX ID
        """
        # First check if it's already a valid SPDX ID
        if license_id in self.licenses:
            return license_id
        
        # Check aliases
        for alias, spdx_ids in self.LICENSE_ALIASES.items():
            if license_id.upper() == alias.upper():
                # Return first canonical ID
                for spdx_id in spdx_ids:
                    if spdx_id in self.licenses:
                        return spdx_id
                # If none found in licenses, return first anyway
                return spdx_ids[0] if spdx_ids else license_id
        
        # Check if it's a variation that maps to an SPDX ID
        license_upper = license_id.upper()
        for spdx_id in self.licenses:
            if spdx_id.upper() == license_upper:
                return spdx_id
        
        return license_id
    
    def get_license_info(self, license_id: str) -> Optional[Dict]:
        """Get license metadata.
        
        Args:
            license_id: SPDX license identifier
            
        Returns:
            License metadata or None
        """
        return self.licenses.get(license_id)
    
    def get_license_text(self, license_id: str) -> Optional[str]:
        """Get license text.
        
        Args:
            license_id: SPDX license identifier
            
        Returns:
            License text or None
        """
        if license_id in self.license_texts:
            return self.license_texts[license_id]
        
        # Try to load from file
        text_file = self.texts_dir / f"{license_id}.txt"
        if text_file.exists():
            with open(text_file, 'r', encoding='utf-8') as f:
                text = f.read()
                self.license_texts[license_id] = text
                return text
        
        # Download if not available
        return self.download_license_text(license_id)


def initialize_spdx_data():
    """Initialize SPDX license data (run once during setup)."""
    manager = SPDXLicenseManager()
    
    # Download license list
    if not manager.load_or_download():
        print("Failed to get SPDX license list")
        return False
    
    # Download common license texts (top 50 most common)
    # Use the exact SPDX identifiers (some changed in newer versions)
    common_licenses = [
        'MIT', 'Apache-2.0', 'GPL-3.0-only', 'GPL-2.0-only', 'BSD-3-Clause', 'BSD-2-Clause',
        'ISC', 'LGPL-3.0-only', 'LGPL-2.1-only', 'MPL-2.0', 'AGPL-3.0-only', 'Unlicense',
        'CC0-1.0', 'EPL-2.0', 'GPL-3.0-or-later', 'GPL-2.0-or-later',
        'LGPL-3.0-or-later', 'LGPL-2.1-or-later', 'Artistic-2.0', 'BSL-1.0',
        'CC-BY-4.0', 'CC-BY-SA-4.0', 'WTFPL', 'PostgreSQL', 'Python-2.0',
        'PHP-3.01', 'Ruby', 'Zlib', 'OFL-1.1', 'AFL-3.0', 'MS-PL', 'EUPL-1.2',
        'CDDL-1.0', 'EPL-1.0', 'OSL-3.0', 'ECL-2.0', 'NCSA', 'Vim', 'UPL-1.0',
        'JSON', 'CECILL-2.1', 'CECILL-C', 'CECILL-B', 'MulanPSL-2.0', 'BlueOak-1.0.0'
    ]
    
    print(f"Downloading {len(common_licenses)} common license texts...")
    for license_id in common_licenses:
        if license_id in manager.licenses:
            text = manager.get_license_text(license_id)
            if text:
                manager.license_texts[license_id] = text
    
    # Compute all hashes
    manager.compute_all_hashes()
    
    print("SPDX data initialization complete")
    return True


if __name__ == "__main__":
    # Initialize SPDX data when run directly
    initialize_spdx_data()