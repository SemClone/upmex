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
            with tempfile.NamedTemporaryFile(mode='w', suffix=Path(file_path).suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                # Run oslili CLI
                result = subprocess.run(
                    ['oslili', '-f', 'evidence', '--similarity-threshold', '0.95', tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout:
                    # Parse JSON output
                    data = json.loads(result.stdout)
                    
                    # Extract licenses from evidence format
                    if 'results' in data and data['results']:
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
                                    
                                    # Only include very high-confidence matches
                                    if lic.get('confidence', 0) >= 0.95:
                                        licenses.append(license_info)
                        
            finally:
                # Clean up temp file
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.debug(f"Oslili subprocess detection failed for {file_path}: {e}")
            
        return licenses
    
    def detect_from_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """
        Detect licenses from a directory using oslili CLI.
        
        Args:
            dir_path: Path to the directory
            
        Returns:
            List of detected licenses with confidence scores
        """
        licenses = []
        
        try:
            # Run oslili CLI on directory
            result = subprocess.run(
                ['oslili', '-f', 'evidence', '--similarity-threshold', '0.95', 
                 '--max-depth', '3', dir_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout:
                # Parse JSON output
                data = json.loads(result.stdout)
                
                # Extract licenses from evidence format
                seen_licenses = set()
                if 'results' in data and data['results']:
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
                                    "confidence_level": self._get_confidence_level(lic.get('confidence', 0.0)),
                                    "source": f"oslili_{lic.get('detection_method', 'unknown')}",
                                    "file": lic.get('source_file', 'unknown'),
                                }
                                
                                # Only include high-confidence matches
                                if lic.get('confidence', 0) >= 0.8:
                                    licenses.append(license_info)
                    
        except Exception as e:
            logger.debug(f"Oslili subprocess directory detection failed for {dir_path}: {e}")
            
        return licenses
    
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