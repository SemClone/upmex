"""
License detection using osslili CLI subprocess.
"""

import subprocess
import json
import tempfile
import os
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class OssliliSubprocessDetector:
    """License detector using osslili CLI."""
    
    def detect_from_file(self, file_path: str, content: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Detect licenses from a file using osslili CLI.
        
        Args:
            file_path: Path to the file (used for naming)
            content: Optional file content to analyze
            
        Returns:
            List of detected licenses with confidence scores
        """
        licenses = []
        
        if content is None:
            return licenses
            
        try:
            # Write content to temporary file for osslili to process
            # Use .txt suffix if file has no extension (e.g., LICENSE files)
            suffix = Path(file_path).suffix or '.txt'
            with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                # Run osslili CLI without similarity threshold for better tag detection
                result = subprocess.run(
                    ['osslili', '-f', 'evidence', tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout:
                    # Parse JSON output - skip non-JSON header lines
                    stdout_lines = result.stdout.splitlines()
                    json_start = -1
                    for i, line in enumerate(stdout_lines):
                        if line.strip().startswith('{'):
                            json_start = i
                            break
                    
                    if json_start >= 0:
                        json_content = '\n'.join(stdout_lines[json_start:])
                        data = json.loads(json_content)
                    else:
                        data = {}
                    
                    # Extract licenses from evidence format
                    # Handle both 'results' format (older) and 'scan_results' format (newer)
                    if 'scan_results' in data and data['scan_results']:
                        for scan_result in data['scan_results']:
                            if 'license_evidence' in scan_result:
                                for lic in scan_result['license_evidence']:
                                    # Map detected_license to spdx_id for consistency
                                    spdx_id = lic.get('detected_license', lic.get('spdx_id', 'Unknown'))
                                    # osslili reports the file it read, the
                                    # category it assigned and how it matched.
                                    # Overwriting "file" with the path we were
                                    # handed threw away the only way to check
                                    # the claim, and for a synthesised
                                    # document that path is a name we invented.
                                    license_info = {
                                        "name": lic.get('name', spdx_id),
                                        "spdx_id": spdx_id,
                                        "confidence": lic.get('confidence', 0.0),
                                        "confidence_level": self._get_confidence_level(
                                            lic.get('confidence', 0.0),
                                            lic.get('detection_method', ''),
                                            lic.get('match_type', ''),
                                        ),
                                        "source": f"osslili_{lic.get('detection_method', 'unknown')}",
                                        # The content was written to a temp
                                        # file for osslili, so its "file" is
                                        # that path. The name the caller asked
                                        # about is the real one.
                                        "file": file_path,
                                        "category": lic.get('category'),
                                        "match_type": lic.get('match_type'),
                                    }
                                    
                                    # Include high-confidence matches or tag detections
                                    detection_method = lic.get('detection_method', '')
                                    if (lic.get('confidence', 0) >= 0.95 or 
                                        detection_method in ['tag', 'spdx_identifier']):
                                        # Skip known false positive: Pixar
                                        if spdx_id == 'Pixar':
                                            continue
                                        licenses.append(license_info)
                    elif 'results' in data and data['results']:
                        # Fallback to old format
                        for result_item in data['results']:
                            if 'licenses' in result_item:
                                for lic in result_item['licenses']:
                                    license_info = {
                                        "name": lic.get('name', lic.get('spdx_id', 'Unknown')),
                                        "spdx_id": lic.get('spdx_id', 'Unknown'),
                                        "confidence": lic.get('confidence', 0.0),
                                        "confidence_level": self._get_confidence_level(
                                            lic.get('confidence', 0.0),
                                            lic.get('detection_method', ''),
                                            lic.get('match_type', ''),
                                        ),
                                        "source": f"osslili_{lic.get('detection_method', 'unknown')}",
                                        # The content was written to a temp
                                        # file for osslili, so its "file" is
                                        # that path. The name the caller asked
                                        # about is the real one.
                                        "file": file_path,
                                        "category": lic.get('category'),
                                        "match_type": lic.get('match_type'),
                                    }
                                    
                                    # Include high-confidence matches or tag detections
                                    detection_method = lic.get('detection_method', '')
                                    if (lic.get('confidence', 0) >= 0.95 or 
                                        detection_method in ['tag', 'spdx_identifier']):
                                        # Skip known false positive: Pixar
                                        if lic.get('spdx_id') == 'Pixar':
                                            continue
                                        licenses.append(license_info)
                        
            finally:
                # Clean up temp file
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.debug(f"Osslili subprocess detection failed for {file_path}: {e}")
            
        return licenses
    
    def detect_from_directory(self, dir_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect licenses and copyrights from a directory using osslili CLI.
        
        Args:
            dir_path: Path to the directory
            
        Returns:
            Dictionary with 'licenses' and 'copyrights' lists
        """
        licenses = []
        copyrights = []
        
        try:
            # Run osslili CLI on directory without similarity threshold for better tag detection
            result = subprocess.run(
                ['osslili', '-f', 'evidence', '--max-depth', '3', dir_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout:
                # Parse JSON output - skip non-JSON header lines
                stdout_lines = result.stdout.splitlines()
                json_start = -1
                for i, line in enumerate(stdout_lines):
                    if line.strip().startswith('{'):
                        json_start = i
                        break
                
                if json_start >= 0:
                    json_content = '\n'.join(stdout_lines[json_start:])
                    data = json.loads(json_content)
                else:
                    data = {}

                # Debug: Check what we got
                import sys
                if 'scan_results' in data and data['scan_results']:
                    for sr in data['scan_results']:
                        if 'copyright_evidence' in sr and sr['copyright_evidence']:
                            print(f"DEBUG: Found copyright evidence: {sr['copyright_evidence']}", file=sys.stderr)
                
                # Extract licenses from evidence format
                seen_licenses = set()
                # Handle both 'scan_results' format (newer) and 'results' format (older)
                if 'scan_results' in data and data['scan_results']:
                    for scan_result in data['scan_results']:
                        if 'license_evidence' in scan_result:
                            for lic in scan_result['license_evidence']:
                                # Map detected_license to spdx_id for consistency
                                spdx_id = lic.get('detected_license', lic.get('spdx_id', 'Unknown'))
                                key = (spdx_id, lic.get('file', 'unknown'))
                                if key in seen_licenses:
                                    continue
                                seen_licenses.add(key)
                                
                                license_info = {
                                    "name": lic.get('name', spdx_id),
                                    "spdx_id": spdx_id,
                                    "confidence": lic.get('confidence', 0.0),
                                    "confidence_level": self._get_confidence_level(
                                        lic.get('confidence', 0.0),
                                        lic.get('detection_method', ''),
                                        lic.get('match_type', ''),
                                    ),
                                    "source": f"osslili_{lic.get('detection_method', 'unknown')}",
                                    # Scanning a directory, so this really is
                                    # the file osslili read.
                                    "file": lic.get('file', 'unknown'),
                                    "category": lic.get('category'),
                                    "match_type": lic.get('match_type'),
                                }
                                
                                # Include high-confidence matches or tag detections
                                detection_method = lic.get('detection_method', '')
                                if (lic.get('confidence', 0) >= 0.95 or 
                                    detection_method in ['tag', 'spdx_identifier']):
                                    # Skip known false positive: Pixar
                                    if spdx_id == 'Pixar':
                                        continue
                                    licenses.append(license_info)
                elif 'results' in data and data['results']:
                    # Fallback to old format
                    for result_item in data['results']:
                        if 'licenses' in result_item:
                            for lic in result_item['licenses']:
                                # Create unique key to avoid duplicates
                                key = (lic.get('spdx_id'), lic.get('source_file'))
                                if key in seen_licenses:
                                    continue
                                seen_licenses.add(key)
                                
                                license_info = {
                                    "name": lic.get('name', lic.get('spdx_id', 'Unknown')),
                                    "spdx_id": lic.get('spdx_id', 'Unknown'),
                                    "confidence": lic.get('confidence', 0.0),
                                    "confidence_level": self._get_confidence_level(
                                        lic.get('confidence', 0.0),
                                        lic.get('detection_method', ''),
                                        lic.get('match_type', ''),
                                    ),
                                    "source": f"osslili_{lic.get('detection_method', 'unknown')}",
                                    "file": lic.get('source_file', 'unknown'),
                                    "category": lic.get('category'),
                                    "match_type": lic.get('match_type'),
                                }
                                
                                # Only include very high-confidence matches
                                # Filter known false positives
                                if lic.get('confidence', 0) >= 0.95:
                                    # Skip known false positive: Pixar (often confused with Apache-2.0)
                                    if lic.get('spdx_id') == 'Pixar':
                                        continue
                                    licenses.append(license_info)

                # Extract copyrights from scan_results - moved to correct indentation level
                # (This was incorrectly nested inside the 'elif results' block)

                # Now at the correct indentation level - outside of the elif block
                # Extract copyrights from scan_results
                seen_copyrights = set()
                if 'scan_results' in data and data['scan_results']:
                    print(f"DEBUG: Processing {len(data['scan_results'])} scan results for copyrights", file=sys.stderr)
                    for scan_result in data['scan_results']:
                        if 'copyright_evidence' in scan_result:
                            print(f"DEBUG: Found {len(scan_result['copyright_evidence'])} copyright items", file=sys.stderr)
                            for copyright_item in scan_result['copyright_evidence']:
                                statement = copyright_item.get('statement', '')
                                print(f"DEBUG: Processing copyright: statement='{statement}'", file=sys.stderr)
                                if statement and statement not in seen_copyrights:
                                    seen_copyrights.add(statement)
                                    copyright_info = {
                                        "statement": statement,
                                        "holder": copyright_item.get('holder', ''),
                                        "years": copyright_item.get('years', []),
                                        "file": copyright_item.get('file', 'unknown'),
                                        "confidence": copyright_item.get('confidence', 1.0)
                                    }
                                    copyrights.append(copyright_info)
                                    print(f"DEBUG: Added copyright: {copyright_info}", file=sys.stderr)

            # TODO: OSSlili v1.5.0 doesn't detect "Copyright (c)" format - FIXED in v1.5.1
            # Issue filed: https://github.com/oscarvalenzuelab/osslili/issues/32
        except Exception as e:
            logger.debug(f"Osslili subprocess directory detection failed for {dir_path}: {e}")
            
        return {"licenses": licenses, "copyrights": copyrights}

    # A match is exact when the file says which licence it is, not when a
    # similarity score is close to one. osslili reports which of those it did.
    EXACT_METHODS = frozenset({"tag", "spdx_identifier"})

    def _get_confidence_level(
        self,
        confidence: float,
        detection_method: str = "",
        match_type: str = "",
    ) -> str:
        """How far this is from certain.

        Exact means the text names the licence: an SPDX identifier or a
        licence tag. A similarity score does not become exact by being high,
        and calling 0.988 exact told a consumer that packaging's BSD-2-Clause
        had been read off a declaration when it had been matched against one.
        """
        if detection_method in self.EXACT_METHODS or match_type in self.EXACT_METHODS:
            return "exact"
        if confidence >= 0.95:
            return "high"
        elif confidence >= 0.85:
            return "medium"
        else:
            return "low"