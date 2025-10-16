"""
License detection using oslili CLI subprocess.
"""

import subprocess
import json
import tempfile
import os
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class OsliliSubprocessDetector:
    """License detector using oslili CLI."""
    
    def detect_from_file(self, file_path: str, content: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Detect licenses from a file using oslili CLI.
        
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
            # Write content to temporary file for oslili to process
            # Use .txt suffix if file has no extension (e.g., LICENSE files)
            suffix = Path(file_path).suffix or '.txt'
            with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                # Run oslili CLI without similarity threshold for better tag detection
                result = subprocess.run(
                    ['oslili', '-f', 'evidence', tmp_path],
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
                                    license_info = {
                                        "name": lic.get('name', spdx_id),
                                        "spdx_id": spdx_id,
                                        "confidence": lic.get('confidence', 0.0),
                                        "confidence_level": self._get_confidence_level(lic.get('confidence', 0.0)),
                                        "source": f"oslili_{lic.get('detection_method', 'unknown')}",
                                        "file": file_path,
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
                                        "confidence_level": self._get_confidence_level(lic.get('confidence', 0.0)),
                                        "source": f"oslili_{lic.get('detection_method', 'unknown')}",
                                        "file": file_path,
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
            logger.debug(f"Oslili subprocess detection failed for {file_path}: {e}")
            
        return licenses
    
    def detect_from_directory(self, dir_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect licenses and copyrights from a directory using oslili CLI.
        
        Args:
            dir_path: Path to the directory
            
        Returns:
            Dictionary with 'licenses' and 'copyrights' lists
        """
        licenses = []
        copyrights = []
        
        try:
            # Run oslili CLI on directory without similarity threshold for better tag detection
            result = subprocess.run(
                ['oslili', '-f', 'evidence', '--max-depth', '3', dir_path],
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
                                    "confidence_level": get_confidence_level_string(lic.get('confidence', 0.0)),
                                    "source": f"oslili_{lic.get('detection_method', 'unknown')}",
                                    "file": lic.get('file', 'unknown'),
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
                                    "confidence_level": get_confidence_level_string(lic.get('confidence', 0.0)),
                                    "source": f"oslili_{lic.get('detection_method', 'unknown')}",
                                    "file": lic.get('source_file', 'unknown'),
                                }
                                
                                # Only include very high-confidence matches
                                # Filter known false positives
                                if lic.get('confidence', 0) >= 0.95:
                                    # Skip known false positive: Pixar (often confused with Apache-2.0)
                                    if lic.get('spdx_id') == 'Pixar':
                                        continue
                                    licenses.append(license_info)
                
                # Extract copyrights from scan_results
                seen_copyrights = set()
                if 'scan_results' in data and data['scan_results']:
                    for scan_result in data['scan_results']:
                        if 'copyright_evidence' in scan_result:
                            for copyright_item in scan_result['copyright_evidence']:
                                statement = copyright_item.get('statement', '')
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
                    
        except Exception as e:
            logger.debug(f"Oslili subprocess directory detection failed for {dir_path}: {e}")
            
        return {"licenses": licenses, "copyrights": copyrights}

    def _get_confidence_level(self, confidence: float) -> str:
        """Convert numeric confidence to level string."""
        if confidence >= 0.95:
            return "exact"
        elif confidence >= 0.85:
            return "high"
        elif confidence >= 0.70:
            return "medium"
        else:
            return "low"