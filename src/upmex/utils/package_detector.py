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
    
    # Check for Gradle build files
    if path.name in ['build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts']:
        return PackageType.GRADLE
    
    # Check for CocoaPods podspec files
    if path.suffix == '.podspec' or path.name.endswith('.podspec.json'):
        return PackageType.COCOAPODS
    
    # Check for Conan files
    if path.name in ['conanfile.py', 'conanfile.txt']:
        return PackageType.CONAN
    
    # Check for Conda packages
    if path.suffix == '.conda':
        return PackageType.CONDA
    
    # Check by extension first
    if path.suffix == '.whl':
        return PackageType.PYTHON_WHEEL
    
    if path.suffix == '.gem':
        return PackageType.RUBY_GEM
    
    if path.suffix == '.crate':
        return PackageType.RUST_CRATE
    
    if path.suffix == '.mod' or path.name == 'go.mod':
        return PackageType.GO_MODULE
    
    if path.suffix == '.nupkg':
        return PackageType.NUGET
    
    if path.suffix == '.rpm':
        return PackageType.RPM
    
    if path.suffix == '.deb':
        return PackageType.DEB
    
    if path.suffix in ['.jar', '.war', '.ear']:
        # Check if it's a Maven package
        if _is_maven_package(package_path):
            return PackageType.MAVEN
        return PackageType.JAR
    
    # Check for archive formats
    if path.name.endswith('.zip'):
        # Check for Go module (zip with go.mod)
        if _is_go_module(package_path):
            return PackageType.GO_MODULE
        
        if _is_python_sdist(package_path):
            return PackageType.PYTHON_SDIST
    
    # Check for Python sdist or Conda packages
    if path.name.endswith(('.tar.gz', '.tgz', '.tar.bz2')):
        # Check for Conda package (.tar.bz2 with info/index.json)
        if path.name.endswith('.tar.bz2') and _is_conda_package(package_path):
            return PackageType.CONDA
        
        # Check for Rust crate (tar.gz with Cargo.toml)
        if _is_rust_crate(package_path):
            return PackageType.RUST_CRATE
        
        # Check for Ruby gem (can be .tar format)
        if _is_ruby_gem(package_path):
            return PackageType.RUBY_GEM
        
        # Check for Perl package (tar.gz with META.json or META.yml)
        if _is_perl_package(package_path):
            return PackageType.PERL
        
        # Check for Conan package (tar.gz with conanfile.py or conaninfo.txt)
        if _is_conan_package(package_path):
            return PackageType.CONAN
        
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


def _is_ruby_gem(archive_path: str) -> bool:
    """Check if an archive is a Ruby gem."""
    try:
        with tarfile.open(archive_path, 'r:*') as tf:
            members = tf.getnames()
            # Ruby gems contain metadata.gz and data.tar.gz
            if 'metadata.gz' in members and 'data.tar.gz' in members:
                return True
    except:
        pass
    return False


def _is_rust_crate(archive_path: str) -> bool:
    """Check if an archive is a Rust crate."""
    try:
        with tarfile.open(archive_path, 'r:gz') as tf:
            for member in tf.getmembers():
                # Rust crates contain Cargo.toml
                if 'Cargo.toml' in member.name:
                    return True
    except:
        pass
    return False


def _is_go_module(archive_path: str) -> bool:
    """Check if an archive is a Go module."""
    import zipfile
    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            for name in zf.namelist():
                # Go modules contain go.mod
                if name.endswith('go.mod'):
                    return True
    except:
        pass
    return False


def _is_conda_package(archive_path: str) -> bool:
    """Check if a .tar.bz2 file is a Conda package."""
    try:
        with tarfile.open(archive_path, 'r:bz2') as tar:
            # Conda packages contain info/index.json
            for member in tar.getmembers():
                if member.name == 'info/index.json':
                    return True
    except:
        pass
    return False


def _is_perl_package(archive_path: str) -> bool:
    """Check if an archive is a Perl/CPAN package."""
    try:
        with tarfile.open(archive_path, 'r:*') as tf:
            for member in tf.getmembers():
                # Perl packages contain META.json or META.yml
                if 'META.json' in member.name or 'META.yml' in member.name:
                    return True
                # Also check for MYMETA files
                if 'MYMETA.json' in member.name or 'MYMETA.yml' in member.name:
                    return True
    except:
        pass
    return False


def _is_conan_package(archive_path: str) -> bool:
    """Check if an archive is a Conan C/C++ package."""
    try:
        with tarfile.open(archive_path, 'r:*') as tf:
            for member in tf.getmembers():
                # Conan packages contain conanfile.py, conanfile.txt, or conaninfo.txt
                if any(name in member.name for name in ['conanfile.py', 'conanfile.txt', 'conaninfo.txt', 'conanmanifest.txt']):
                    return True
    except:
        pass
    return False