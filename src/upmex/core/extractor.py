"""Main package extractor orchestrator."""

import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from .models import PackageMetadata, PackageType, NO_ASSERTION
from ..extractors.python_extractor import PythonExtractor
from ..extractors.npm_extractor import NpmExtractor
from ..extractors.java_extractor import JavaExtractor
from ..extractors.gradle_extractor import GradleExtractor
from ..extractors.cocoapods_extractor import CocoaPodsExtractor
from ..extractors.conda_extractor import CondaExtractor
from ..extractors.conan_extractor import ConanExtractor
from ..extractors.perl_extractor import PerlExtractor
from ..extractors.ruby_extractor import RubyExtractor
from ..extractors.rust_extractor import RustExtractor
from ..extractors.go_extractor import GoExtractor
from ..extractors.nuget_extractor import NuGetExtractor
from ..extractors.rpm_extractor import RpmExtractor
from ..extractors.deb_extractor import DebianExtractor
from ..utils.package_detector import detect_package_type
from ..api.clearlydefined import ClearlyDefinedAPI
from ..api.ecosystems import EcosystemsAPI


class PackageExtractor:
    """Main class for extracting package metadata."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the package extractor.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.online_mode = self.config.get('online_mode', False)
        
        # Initialize extractors with online mode
        self.extractors = {
            PackageType.PYTHON_WHEEL: PythonExtractor(online_mode=self.online_mode),
            PackageType.PYTHON_SDIST: PythonExtractor(online_mode=self.online_mode),
            PackageType.NPM: NpmExtractor(online_mode=self.online_mode),
            PackageType.MAVEN: JavaExtractor(online_mode=self.online_mode),
            PackageType.JAR: JavaExtractor(online_mode=self.online_mode),
            PackageType.GRADLE: GradleExtractor(online_mode=self.online_mode),
            PackageType.COCOAPODS: CocoaPodsExtractor(online_mode=self.online_mode),
            PackageType.CONDA: CondaExtractor(online_mode=self.online_mode),
            PackageType.CONAN: ConanExtractor(),
            PackageType.PERL: PerlExtractor(),
            PackageType.RUBY_GEM: RubyExtractor(online_mode=self.online_mode),
            PackageType.RUST_CRATE: RustExtractor(online_mode=self.online_mode),
            PackageType.GO_MODULE: GoExtractor(online_mode=self.online_mode),
            PackageType.NUGET: NuGetExtractor(online_mode=self.online_mode),
            PackageType.RPM: RpmExtractor(online_mode=self.online_mode),
            PackageType.DEB: DebianExtractor(online_mode=self.online_mode),
        }
    
    def extract(self, package_path: str) -> PackageMetadata:
        """Extract metadata from a package file.
        
        Args:
            package_path: Path to the package file
            
        Returns:
            PackageMetadata object containing extracted information
        """
        path = Path(package_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Package file not found: {package_path}")
        
        # Detect package type
        package_type = detect_package_type(package_path)
        
        # Get file metadata
        file_size = path.stat().st_size
        file_hash = self._calculate_hash(package_path, algorithm="sha1")
        file_hash_md5 = self._calculate_hash(package_path, algorithm="md5")
        
        # Extract metadata using appropriate extractor
        if package_type in self.extractors:
            extractor = self.extractors[package_type]
            metadata = extractor.extract(package_path)
        else:
            # Fallback to basic metadata
            metadata = PackageMetadata(
                name=path.stem,
                package_type=package_type
            )
        
        # Add file metadata
        metadata.file_size = file_size
        metadata.file_hash = file_hash
        metadata.file_hash_md5 = file_hash_md5
        metadata.fuzzy_hash = self._calculate_fuzzy_hash(package_path)
        metadata.package_type = package_type
        
        # Generate PURL (Package URL)
        metadata.purl = self._generate_purl(metadata)
        
        # Normalize description
        if metadata.description:
            metadata.description = self._normalize_text(metadata.description)
        
        # Enrich with APIs if online mode is enabled
        if self.online_mode:
            self._enrich_with_apis(metadata)
        return metadata
    
    def _enrich_with_apis(self, metadata: PackageMetadata) -> None:
        """Enrich metadata using external APIs.
        
        Args:
            metadata: Package metadata to enrich
        """
        try:
            # Extract namespace and name for API calls
            namespace = None
            name = metadata.name
            
            # Handle namespaced packages
            if metadata.package_type in [PackageType.MAVEN, PackageType.JAR]:
                # Maven format: groupId:artifactId
                if ':' in name:
                    parts = name.split(':', 1)
                    namespace = parts[0]
                    name = parts[1]
            elif metadata.package_type == PackageType.NPM:
                # NPM scoped packages: @scope/package
                if name.startswith('@') and '/' in name:
                    parts = name.split('/', 1)
                    namespace = parts[0][1:]  # Remove @
                    name = parts[1]
            
            # Try ClearlyDefined
            cd_api = ClearlyDefinedAPI(api_key=self.config.get('clearlydefined_api_key'))
            cd_def = cd_api.get_definition(metadata.package_type, namespace, name, metadata.version)
            if cd_def:
                # Extract license info
                license_info = cd_api.extract_license_info(cd_def)
                if license_info and not metadata.licenses:
                    from .models import LicenseInfo
                    metadata.licenses.append(LicenseInfo(
                        spdx_id=license_info['spdx_id'],
                        confidence=license_info['confidence'],
                        detection_method='ClearlyDefined API'
                    ))
            
            # Try Ecosyste.ms
            eco_api = EcosystemsAPI(api_key=self.config.get('ecosystems_api_key'))
            eco_info = eco_api.get_package_info(metadata.package_type, metadata.name, metadata.version)
            if eco_info:
                eco_metadata = eco_api.extract_metadata(eco_info)
                
                # Fill in missing fields
                if not metadata.description and eco_metadata.get('description'):
                    metadata.description = eco_metadata['description']
                    metadata.provenance['description'] = 'ecosystems_api'
                
                if metadata.repository == NO_ASSERTION and eco_metadata.get('repository'):
                    metadata.repository = eco_metadata['repository']
                    metadata.provenance['repository'] = 'ecosystems_api'
                
                if not metadata.keywords and eco_metadata.get('keywords'):
                    metadata.keywords = eco_metadata['keywords']
                    metadata.provenance['keywords'] = 'ecosystems_api'
                
                # Add maintainers if missing
                if not metadata.maintainers and eco_metadata.get('maintainers'):
                    maintainers = eco_metadata['maintainers']
                    # Format maintainers properly
                    formatted_maintainers = []
                    for m in maintainers:
                        if isinstance(m, dict):
                            # Extract relevant fields from Ecosyste.ms format
                            maintainer = {}
                            # Try different fields for name
                            if m.get('name'):
                                maintainer['name'] = m['name']
                            elif m.get('login'):
                                maintainer['name'] = m['login']
                            elif m.get('uuid'):
                                maintainer['name'] = m['uuid']
                            
                            if m.get('email'):
                                maintainer['email'] = m['email']
                            
                            # Add additional fields if present
                            if 'uuid' in m:
                                maintainer['id'] = m['uuid']
                            
                            if maintainer.get('name') or maintainer.get('email'):
                                formatted_maintainers.append(maintainer)
                        elif isinstance(m, str):
                            formatted_maintainers.append({'name': m, 'email': NO_ASSERTION})
                    
                    if formatted_maintainers:
                        metadata.maintainers = formatted_maintainers
                        metadata.provenance['maintainers'] = 'ecosystems_api'
                
                # Add license info if missing
                if not metadata.licenses and eco_metadata.get('licenses'):
                    from .models import LicenseInfo
                    licenses = eco_metadata['licenses']
                    if isinstance(licenses, str):
                        licenses = [licenses]
                    
                    for license_str in licenses:
                        # Use the same license detection as in extractors
                        from ..extractors.base import BaseExtractor
                        temp_extractor = type('TempExtractor', (BaseExtractor,), {
                            'extract': lambda self, path: None,
                            'can_extract': lambda self, path: False
                        })()
                        
                        license_infos = temp_extractor.detect_licenses_from_text(
                            license_str,
                            filename='ecosystems_api'
                        )
                        if license_infos:
                            metadata.licenses.extend(license_infos)
                
        except Exception as e:
            print(f"Error enriching with APIs: {e}")
    
    def _calculate_hash(self, file_path: str, algorithm: str = "sha256") -> str:
        """Calculate file hash.
        
        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use
            
        Returns:
            Hex digest of the file hash
        """
        hash_func = hashlib.new(algorithm)
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    
    def _calculate_fuzzy_hash(self, file_path: str) -> Optional[str]:
        """Calculate TLSH or LSH fuzzy hash for similarity detection.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Fuzzy hash string or None
        """
        try:
            # Try TLSH first (preferred)
            import tlsh
            with open(file_path, 'rb') as f:
                data = f.read()
            hash_value = tlsh.hash(data)
            if hash_value and hash_value != 'TNULL':
                return f"tlsh:{hash_value}"
        except (ImportError, Exception):
            pass
        
        try:
            # Try ssdeep as second option
            import ssdeep
            return f"ssdeep:{ssdeep.hash_from_file(file_path)}"
        except ImportError:
            pass
        
        # Fallback to a simple LSH implementation
        try:
            import hashlib
            # Create a simple LSH using MinHash approach
            with open(file_path, 'rb') as f:
                # Read file in chunks and create partial hashes
                chunks = []
                chunk_size = 4096
                for i in range(20):  # First 20 chunks for better coverage
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    # Use different hash functions for LSH
                    h1 = hashlib.sha1(chunk).hexdigest()[:6]
                    h2 = hashlib.md5(chunk).hexdigest()[:6]
                    chunks.append(f"{h1}{h2}")
                
                if chunks:
                    # Create a simple LSH signature
                    return f"lsh:{'-'.join(chunks[:10])}"  # Limit to 10 for readability
        except Exception:
            pass
        
        return None
    
    def _generate_purl(self, metadata: PackageMetadata) -> Optional[str]:
        """Generate Package URL (PURL) for the package.
        
        Args:
            metadata: Package metadata
            
        Returns:
            PURL string or None
        """
        if not metadata.name:
            return None
        
        # Map package type to PURL type
        purl_type_map = {
            PackageType.PYTHON_WHEEL: "pypi",
            PackageType.PYTHON_SDIST: "pypi",
            PackageType.NPM: "npm",
            PackageType.MAVEN: "maven",
            PackageType.JAR: "maven",
            PackageType.GRADLE: "maven",
            PackageType.COCOAPODS: "cocoapods",
            PackageType.CONDA: "conda",
            PackageType.CONAN: "conan",
            PackageType.PERL: "cpan",
            PackageType.RUBY_GEM: "gem",
            PackageType.RUST_CRATE: "cargo",
            PackageType.GO_MODULE: "golang",
            PackageType.NUGET: "nuget"
        }
        
        purl_type = purl_type_map.get(metadata.package_type)
        if not purl_type:
            return None
        
        # Build PURL
        purl = f"pkg:{purl_type}/"
        
        # Handle namespace for Maven packages
        if metadata.package_type in [PackageType.MAVEN, PackageType.JAR, PackageType.GRADLE]:
            if ':' in metadata.name:
                parts = metadata.name.split(':', 1)
                namespace = parts[0].replace('.', '/')
                name = parts[1]
                purl += f"{namespace}/{name}"
            else:
                purl += metadata.name
        # Handle scoped NPM packages
        elif metadata.package_type == PackageType.NPM and metadata.name.startswith('@'):
            if '/' in metadata.name:
                parts = metadata.name.split('/', 1)
                namespace = parts[0][1:]  # Remove @
                name = parts[1]
                purl += f"{namespace}/{name}"
            else:
                purl += metadata.name
        else:
            purl += metadata.name
        
        # Add version if available
        if metadata.version:
            purl += f"@{metadata.version}"
        
        return purl
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text by removing extra whitespace and newlines.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        import re
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        # Strip leading and trailing whitespace
        text = text.strip()
        return text