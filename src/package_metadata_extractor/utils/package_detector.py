"""Package type detection utilities."""

import zipfile
import tarfile
from pathlib import Path
from typing import Optional
from ..core.models import PackageType


def detect_package_type(package_path: str) -> PackageType:
    """Detect the type of a package file.
    
    Args:
        package_path: Path to the package file
        
    Returns:
        Detected PackageType
    """
    path = Path(package_path)
    
    # Check by extension first
    if path.suffix == '.whl':
        return PackageType.PYTHON_WHEEL
    
    if path.suffix in ['.jar', '.war', '.ear']:
        # Check if it's a Maven package
        if _is_maven_package(package_path):
            return PackageType.MAVEN
        return PackageType.JAR
    
    # Check for Python sdist
    if path.name.endswith(('.tar.gz', '.tgz', '.tar.bz2', '.zip')):
        if _is_python_sdist(package_path):
            return PackageType.PYTHON_SDIST
        
        # Check for NPM package
        if _is_npm_package(package_path):
            return PackageType.NPM
    
    # Check for .tgz which is commonly NPM
    if path.suffix == '.tgz':
        if _is_npm_package(package_path):
            return PackageType.NPM
    
    return PackageType.UNKNOWN


def _is_maven_package(jar_path: str) -> bool:
    """Check if a JAR file is a Maven package."""
    try:
        with zipfile.ZipFile(jar_path, 'r') as zf:
            for name in zf.namelist():
                if name.startswith('META-INF/maven/') and name.endswith('/pom.xml'):
                    return True
    except:
        pass
    return False


def _is_python_sdist(archive_path: str) -> bool:
    """Check if an archive is a Python source distribution."""
    try:
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for name in zf.namelist():
                    if 'PKG-INFO' in name or 'setup.py' in name or 'pyproject.toml' in name:
                        return True
        else:
            with tarfile.open(archive_path, 'r:*') as tf:
                for member in tf.getmembers():
                    if 'PKG-INFO' in member.name or 'setup.py' in member.name or 'pyproject.toml' in member.name:
                        return True
    except:
        pass
    return False


def _is_npm_package(archive_path: str) -> bool:
    """Check if an archive is an NPM package."""
    try:
        with tarfile.open(archive_path, 'r:*') as tf:
            for member in tf.getmembers():
                if member.name.endswith('package.json'):
                    # Read and check if it looks like NPM package.json
                    content = tf.extractfile(member).read()
                    if b'"name"' in content or b'"version"' in content:
                        return True
    except:
        pass
    return False