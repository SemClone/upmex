"""Archive extraction utilities."""

import tarfile
import zipfile
import tempfile
import os
from typing import Dict, List, Optional, Callable
from pathlib import Path


def extract_from_tar(archive_path: str, 
                    target_patterns: Optional[List[str]] = None,
                    callback: Optional[Callable] = None) -> Dict[str, bytes]:
    """Extract files from tar archives (tar, tar.gz, tar.bz2, tgz).
    
    Args:
        archive_path: Path to the tar archive
        target_patterns: List of filename patterns to extract (None = all)
        callback: Optional callback function(member, content) for each file
        
    Returns:
        Dictionary mapping filenames to their content
    """
    extracted = {}
    
    try:
        with tarfile.open(archive_path, 'r:*') as tar:
            for member in tar.getmembers():
                if member.isfile():
                    # Check if we should extract this file
                    if target_patterns:
                        if not any(pattern in member.name for pattern in target_patterns):
                            continue
                    
                    # Extract file content
                    try:
                        file_obj = tar.extractfile(member)
                        if file_obj:
                            content = file_obj.read()
                            extracted[member.name] = content
                            
                            # Call callback if provided
                            if callback:
                                callback(member.name, content)
                    except Exception:
                        continue
    except Exception as e:
        raise ValueError(f"Failed to extract tar archive: {e}")
    
    return extracted


def extract_from_zip(archive_path: str,
                    target_patterns: Optional[List[str]] = None,
                    callback: Optional[Callable] = None) -> Dict[str, bytes]:
    """Extract files from zip archives.
    
    Args:
        archive_path: Path to the zip archive
        target_patterns: List of filename patterns to extract (None = all)
        callback: Optional callback function(filename, content) for each file
        
    Returns:
        Dictionary mapping filenames to their content
    """
    extracted = {}
    
    try:
        with zipfile.ZipFile(archive_path, 'r') as zip_file:
            for name in zip_file.namelist():
                # Check if we should extract this file
                if target_patterns:
                    if not any(pattern in name for pattern in target_patterns):
                        continue
                
                # Extract file content
                try:
                    content = zip_file.read(name)
                    extracted[name] = content
                    
                    # Call callback if provided
                    if callback:
                        callback(name, content)
                except Exception:
                    continue
    except Exception as e:
        raise ValueError(f"Failed to extract zip archive: {e}")
    
    return extracted


def extract_to_temp_dir(archive_path: str) -> str:
    """Extract archive to a temporary directory.
    
    Args:
        archive_path: Path to the archive
        
    Returns:
        Path to the temporary directory containing extracted files
    """
    temp_dir = tempfile.mkdtemp(prefix="upmex_")
    
    try:
        # Determine archive type and extract
        if archive_path.endswith(('.tar', '.tar.gz', '.tar.bz2', '.tgz', '.tar.xz')):
            with tarfile.open(archive_path, 'r:*') as tar:
                tar.extractall(temp_dir)
        elif archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_file:
                zip_file.extractall(temp_dir)
        else:
            # Try tar first, then zip
            try:
                with tarfile.open(archive_path, 'r:*') as tar:
                    tar.extractall(temp_dir)
            except:
                with zipfile.ZipFile(archive_path, 'r') as zip_file:
                    zip_file.extractall(temp_dir)
    except Exception as e:
        # Clean up temp dir on failure
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError(f"Failed to extract archive: {e}")
    
    return temp_dir


def find_file_in_archive(archive_path: str, 
                        filename_patterns: List[str],
                        return_first: bool = True) -> Optional[Dict[str, bytes]]:
    """Find specific files in an archive.
    
    Args:
        archive_path: Path to the archive
        filename_patterns: List of patterns to search for
        return_first: If True, return first match; otherwise return all matches
        
    Returns:
        Dictionary of filename to content, or None if not found
    """
    results = {}
    
    # Determine archive type
    is_tar = archive_path.endswith(('.tar', '.tar.gz', '.tar.bz2', '.tgz', '.tar.xz'))
    
    try:
        if is_tar:
            with tarfile.open(archive_path, 'r:*') as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        for pattern in filename_patterns:
                            if pattern in member.name or member.name.endswith(pattern):
                                file_obj = tar.extractfile(member)
                                if file_obj:
                                    results[member.name] = file_obj.read()
                                    if return_first:
                                        return results
        else:
            with zipfile.ZipFile(archive_path, 'r') as zip_file:
                for name in zip_file.namelist():
                    for pattern in filename_patterns:
                        if pattern in name or name.endswith(pattern):
                            results[name] = zip_file.read(name)
                            if return_first:
                                return results
    except:
        return None
    
    return results if results else None


def get_archive_file_list(archive_path: str) -> List[str]:
    """Get list of files in an archive.
    
    Args:
        archive_path: Path to the archive
        
    Returns:
        List of file paths in the archive
    """
    files = []
    
    try:
        # Try as tar archive
        if archive_path.endswith(('.tar', '.tar.gz', '.tar.bz2', '.tgz', '.tar.xz')):
            with tarfile.open(archive_path, 'r:*') as tar:
                files = [m.name for m in tar.getmembers() if m.isfile()]
        # Try as zip archive
        else:
            with zipfile.ZipFile(archive_path, 'r') as zip_file:
                files = zip_file.namelist()
    except:
        pass
    
    return files