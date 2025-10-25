"""Command-line interface for UPMEX."""

# Suppress urllib3 SSL warning on macOS with LibreSSL - must be before any imports
import warnings
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

# Additional suppression methods
try:
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    pass

import sys
import json
import click
from pathlib import Path
from typing import Optional
import logging

from upmex import __version__
from upmex.core.extractor import PackageExtractor
from upmex.core.models import PackageType
from upmex.config import Config
from upmex.utils.package_detector import detect_package_type
from upmex.utils.output_formatter import OutputFormatter

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="upmex")
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--quiet', '-q', is_flag=True, help='Suppress all output except results')
@click.pass_context
def cli(ctx, config, verbose, quiet):
    """UPMEX - Universal Package Metadata Extractor.
    
    Extract metadata and license information from various package formats.
    """
    ctx.ensure_object(dict)
    
    # Load configuration
    if config:
        ctx.obj['config'] = Config(config)
    else:
        ctx.obj['config'] = Config()
    
    # Set logging level
    if quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet


@cli.command()
@click.argument('package_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', '-f', type=click.Choice(['json', 'text']), default='json', help='Output format')
@click.option('--pretty', '-p', is_flag=True, help='Pretty print output')
@click.option('--api', type=click.Choice(['clearlydefined', 'ecosystems', 'purldb', 'vulnerablecode', 'all', 'none']), default='none', help='API enrichment')
@click.option('--registry', is_flag=True, help='Enable registry mode to fetch missing metadata from package registries')
@click.pass_context
def extract(ctx, package_path, output, format, pretty, api, registry):
    """Extract metadata from a package file.
    
    Examples:
        upmex extract package.whl
        upmex extract --format text package.tgz
        upmex extract --registry package.jar
        upmex extract --api clearlydefined package.jar
        upmex extract --api purldb package.whl
        upmex extract --api vulnerablecode package.jar
        upmex extract --registry --api all package.jar
    """
    config = ctx.obj['config']
    verbose = ctx.obj['verbose']
    
    # Update config with CLI options
    
    try:
        # Create extractor with registry mode
        extractor_config = config.to_dict()
        extractor_config['registry_mode'] = registry
        extractor = PackageExtractor(extractor_config)
        
        # Extract metadata
        if verbose:
            click.echo(f"Extracting metadata from: {package_path}")
            if registry:
                click.echo("Registry mode enabled - will fetch missing metadata")
        
        metadata = extractor.extract(package_path)

        # API enrichment with third-party services (ClearlyDefined, Ecosystems)
        if api != 'none':
            # API enrichment only when --api is specified (with or without --registry)
            if verbose:
                if registry:
                    click.echo("Using both registry and third-party API enrichment")
                else:
                    click.echo("Using third-party API enrichment only")
            try:
                from .api.clearlydefined import ClearlyDefinedAPI
                from .api.ecosystems import EcosystemsAPI
                from .api.purldb import PurlDBAPI
                from .api.vulnerablecode import VulnerableCodeAPI
                from upmex.core.models import NO_ASSERTION

                if api in ['clearlydefined', 'all']:
                    if verbose:
                        click.echo("Enriching with ClearlyDefined API...")

                        cd_api = ClearlyDefinedAPI()

                        # Parse namespace from name for Maven packages
                        namespace = None
                        name = metadata.name
                        if ':' in metadata.name:
                            # Maven format: groupId:artifactId
                            parts = metadata.name.split(':')
                            if len(parts) >= 2:
                                namespace = parts[0]
                                name = parts[1]

                        cd_data = cd_api.get_definition(
                            package_type=metadata.package_type,
                            namespace=namespace,
                            name=name,
                            version=metadata.version
                        )

                        if cd_data:
                            applied_fields = []

                            # Enrich licensing information
                            cd_license = cd_api.extract_license_info(cd_data)
                            if cd_license:
                                from upmex.core.models import LicenseInfo, LicenseConfidenceLevel
                                license_obj = LicenseInfo(
                                    spdx_id=cd_license['spdx_id'],
                                    confidence=cd_license['confidence'],
                                    confidence_level=LicenseConfidenceLevel.EXACT if cd_license['confidence'] >= 0.95 else LicenseConfidenceLevel.HIGH,
                                    detection_method='ClearlyDefined API',
                                    file_path='clearlydefined_api'
                                )
                                metadata.licenses.append(license_obj)
                                metadata.provenance['licenses_clearlydefined'] = f"clearlydefined:{cd_api.base_url}"
                                applied_fields.append('licenses')

                            # Enrich other metadata if available
                            if cd_data.get('described', {}).get('projectWebsite') and (not metadata.homepage or metadata.homepage == NO_ASSERTION):
                                metadata.homepage = cd_data['described']['projectWebsite']
                                metadata.provenance['homepage'] = f"clearlydefined:{cd_api.base_url}"
                                applied_fields.append('homepage')

                            # Track API enrichment
                            if applied_fields:
                                metadata.add_enrichment(
                                    source="clearlydefined",
                                    source_type="api",
                                    data=cd_data,
                                    applied_fields=applied_fields
                                )

                            if verbose:
                                click.echo(f"✓ ClearlyDefined enrichment completed")
                        elif verbose:
                            click.echo("○ No ClearlyDefined data available")

                if api in ['ecosystems', 'all']:
                    if verbose:
                        click.echo("Enriching with Ecosystems API...")

                    eco_api = EcosystemsAPI()
                    eco_info = eco_api.get_package_info(metadata.package_type, metadata.name, metadata.version)

                    if eco_info:
                        applied_fields = []
                        eco_metadata = eco_api.extract_metadata(eco_info)

                        # Fill in missing fields
                        if not metadata.description and eco_metadata.get('description'):
                            metadata.description = eco_metadata['description']
                            metadata.provenance['description'] = 'ecosystems_api'
                            applied_fields.append('description')

                        if metadata.repository == NO_ASSERTION and eco_metadata.get('repository'):
                            metadata.repository = eco_metadata['repository']
                            metadata.provenance['repository'] = 'ecosystems_api'
                            applied_fields.append('repository')

                        if not metadata.keywords and eco_metadata.get('keywords'):
                            metadata.keywords = eco_metadata['keywords']
                            metadata.provenance['keywords'] = 'ecosystems_api'
                            applied_fields.append('keywords')

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
                                applied_fields.append('maintainers')

                        # Add license info if missing
                        if not metadata.licenses and eco_metadata.get('licenses'):
                            from upmex.core.models import LicenseInfo
                            licenses = eco_metadata['licenses']
                            if isinstance(licenses, str):
                                licenses = [licenses]

                            for license_str in licenses:
                                # Use the same license detection as in extractors
                                from upmex.extractors.base import BaseExtractor
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
                                    applied_fields.append('licenses')

                        # Track API enrichment
                        if applied_fields:
                            metadata.add_enrichment(
                                source="ecosystems",
                                source_type="api",
                                data=eco_info,
                                applied_fields=applied_fields
                            )

                        if verbose:
                            click.echo(f"✓ Ecosystems enrichment completed")
                    elif verbose:
                        click.echo("○ No Ecosystems data available")

                if api in ['purldb', 'all']:
                    if verbose:
                        click.echo("Enriching with PurlDB API...")

                    purldb_api = PurlDBAPI()
                    purldb_info = purldb_api.get_package_info(metadata.package_type, metadata.name, metadata.version)

                    if purldb_info:
                        applied_fields = []
                        purldb_metadata = purldb_api.extract_metadata(purldb_info)

                        # Fill in missing fields
                        if not metadata.description and purldb_metadata.get('description'):
                            metadata.description = purldb_metadata['description']
                            metadata.provenance['description'] = 'purldb_api'
                            applied_fields.append('description')

                        if (not metadata.homepage or metadata.homepage == NO_ASSERTION) and purldb_metadata.get('homepage'):
                            metadata.homepage = purldb_metadata['homepage']
                            metadata.provenance['homepage'] = 'purldb_api'
                            applied_fields.append('homepage')

                        if metadata.repository == NO_ASSERTION and purldb_metadata.get('repository'):
                            metadata.repository = purldb_metadata['repository']
                            metadata.provenance['repository'] = 'purldb_api'
                            applied_fields.append('repository')

                        if not metadata.keywords and purldb_metadata.get('keywords'):
                            metadata.keywords = purldb_metadata['keywords']
                            metadata.provenance['keywords'] = 'purldb_api'
                            applied_fields.append('keywords')

                        # Add maintainers if missing
                        if not metadata.maintainers and purldb_metadata.get('maintainers'):
                            metadata.maintainers = purldb_metadata['maintainers']
                            metadata.provenance['maintainers'] = 'purldb_api'
                            applied_fields.append('maintainers')

                        # Add authors if missing
                        if not metadata.authors and purldb_metadata.get('authors'):
                            metadata.authors = purldb_metadata['authors']
                            metadata.provenance['authors'] = 'purldb_api'
                            applied_fields.append('authors')

                        # Add license info if missing (using license_expression)
                        if not metadata.licenses and purldb_metadata.get('license_expression'):
                            from upmex.extractors.base import BaseExtractor
                            temp_extractor = type('TempExtractor', (BaseExtractor,), {
                                'extract': lambda self, path: None,
                                'can_extract': lambda self, path: False
                            })()

                            license_infos = temp_extractor.detect_licenses_from_text(
                                purldb_metadata['license_expression'],
                                filename='purldb_api'
                            )
                            if license_infos:
                                metadata.licenses.extend(license_infos)
                                applied_fields.append('licenses')

                        # Track API enrichment
                        if applied_fields:
                            metadata.add_enrichment(
                                source="purldb",
                                source_type="api",
                                data=purldb_info,
                                applied_fields=applied_fields
                            )

                        if verbose:
                            click.echo(f"✓ PurlDB enrichment completed")
                    elif verbose:
                        click.echo("○ No PurlDB data available")

                if api in ['vulnerablecode', 'all']:
                    if verbose:
                        click.echo("Enriching with VulnerableCode API...")

                    # Get API key from config or environment
                    vulnerablecode_api_key = config.get('vulnerablecode_api_key') or None
                    vulnerablecode_api = VulnerableCodeAPI(api_key=vulnerablecode_api_key)
                    vuln_data = vulnerablecode_api.get_vulnerabilities(metadata.package_type, metadata.name, metadata.version)

                    if vuln_data:
                        vulnerabilities = vulnerablecode_api.extract_vulnerabilities(vuln_data)

                        if vulnerabilities['total_count'] > 0:
                            metadata.vulnerabilities = vulnerabilities

                            # Track as enrichment
                            metadata.add_enrichment(
                                source="vulnerablecode",
                                source_type="api",
                                data=vuln_data,
                                applied_fields=["vulnerabilities"]
                            )

                            if verbose:
                                total = vulnerabilities['total_count']
                                vulnerable = len(vulnerabilities['vulnerable_packages'])
                                click.echo(f"✓ VulnerableCode found {total} entries, {vulnerable} vulnerable")
                        else:
                            if verbose:
                                click.echo("✓ VulnerableCode found no vulnerabilities")
                    elif verbose:
                        click.echo("○ No VulnerableCode data available")

            except ImportError as e:
                click.echo(f"Warning: API enrichment dependencies not available: {e}", err=True)
            except Exception as e:
                click.echo(f"Warning: API enrichment failed: {e}", err=True)
        
        # Format output
        formatter = OutputFormatter(pretty=pretty)
        output_text = formatter.format(metadata, format)
        
        # Write output
        if output:
            Path(output).write_text(output_text)
            if not ctx.obj['quiet']:
                click.echo(f"Output written to: {output}")
        else:
            click.echo(output_text)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('package_path', type=click.Path(exists=True))
@click.option('--verbose', '-v', is_flag=True, help='Show detection confidence')
@click.pass_context
def detect(ctx, package_path, verbose):
    """Detect the type of a package file.
    
    Examples:
        upmex detect package.whl
        upmex detect -v unknown.tar.gz
    """
    try:
        package_type = detect_package_type(package_path)
        
        if verbose:
            path = Path(package_path)
            click.echo(f"File: {path.name}")
            click.echo(f"Size: {path.stat().st_size:,} bytes")
            click.echo(f"Type: {package_type.value}")
        else:
            click.echo(package_type.value)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('package_path', type=click.Path(exists=True))
@click.pass_context
def license(ctx, package_path):
    """Extract only license information from a package.
    
    Examples:
        upmex license package.whl
        upmex license -c package.tar.gz
    """
    config = ctx.obj['config']
    
    try:
        # Create extractor
        extractor = PackageExtractor(config.to_dict())
        
        # Extract metadata
        metadata = extractor.extract(package_path)
        
        if not metadata.licenses:
            click.echo("No license information found")
            return
        
        # Display license information
        for license_info in metadata.licenses:
            if license_info.spdx_id:
                click.echo(f"License: {license_info.spdx_id}")
            elif license_info.name:
                click.echo(f"License: {license_info.name}")
            else:
                click.echo("License: Unknown")
            
            # Always show confidence info if available (OSLiLi provides it)
            if hasattr(license_info, 'confidence') and license_info.confidence:
                click.echo(f"  Confidence: {license_info.confidence:.2%}")
            if hasattr(license_info, 'confidence_level') and license_info.confidence_level:
                click.echo(f"  Level: {license_info.confidence_level.value}")
            if hasattr(license_info, 'detection_method') and license_info.detection_method:
                click.echo(f"  Method: {license_info.detection_method}")
            if hasattr(license_info, 'file_path') and license_info.file_path:
                click.echo(f"  Source: {license_info.file_path}")
                    
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
@click.pass_context
def info(ctx, output_json):
    """Show information about UPMEX.
    
    Examples:
        upmex info
        upmex info --json
    """
    info_data = {
        "version": __version__,
        "supported_packages": [
            {"type": "python_wheel", "extensions": [".whl"], "description": "Python wheel packages"},
            {"type": "python_sdist", "extensions": [".tar.gz", ".zip"], "description": "Python source distributions"},
            {"type": "npm", "extensions": [".tgz"], "description": "Node.js packages"},
            {"type": "maven", "extensions": [".jar"], "description": "Maven artifacts"},
            {"type": "jar", "extensions": [".jar", ".war", ".ear"], "description": "Java archives"},
            {"type": "gradle", "extensions": [".jar"], "description": "Gradle artifacts"},
            {"type": "cocoapods", "extensions": [".podspec"], "description": "iOS/macOS CocoaPods"},
            {"type": "conda", "extensions": [".tar.bz2", ".conda"], "description": "Conda packages"},
            {"type": "conan", "extensions": [".tar.gz"], "description": "C/C++ Conan packages"},
            {"type": "perl", "extensions": [".tar.gz"], "description": "Perl CPAN modules"},
            {"type": "ruby_gem", "extensions": [".gem"], "description": "Ruby gems"},
            {"type": "rust_crate", "extensions": [".crate"], "description": "Rust crates"},
            {"type": "go_module", "extensions": [".zip"], "description": "Go modules"},
            {"type": "nuget", "extensions": [".nupkg"], "description": ".NET NuGet packages"},
            {"type": "rpm", "extensions": [".rpm"], "description": "RPM packages"},
            {"type": "deb", "extensions": [".deb"], "description": "Debian packages"},
        ],
        "registry_integrations": {
            "implemented": ["maven_central"],
            "note": "Direct package registry API calls for metadata enrichment"
        },
        "api_integrations": {
            "implemented": ["clearlydefined", "ecosystems", "purldb", "vulnerablecode"],
            "note": "Third-party API services for metadata enrichment and vulnerability scanning"
        },
        "output_formats": ["json", "text"],
        "license_detection": "OSLiLi (Open Source License Identifier)",
        "enrichment_modes": {
            "registry": "Fetches missing data from package registries (currently: Maven Central only)",
            "api": "Uses third-party APIs for enrichment and vulnerability scanning (ClearlyDefined, Ecosystems, PurlDB, VulnerableCode)",
            "combined": "Uses both registry and API enrichment when available"
        }
    }
    
    if output_json:
        click.echo(json.dumps(info_data, indent=2))
    else:
        click.echo(f"UPMEX - Universal Package Metadata Extractor v{__version__}")

        click.echo("\nSupported Package Types:")
        for pkg in info_data["supported_packages"]:
            exts = ', '.join(pkg['extensions'])
            click.echo(f"  - {pkg['type']:<15} {exts:<20} {pkg['description']}")

        click.echo("\nRegistry Integrations:")
        click.echo(f"  {info_data['registry_integrations']['note']}")
        for registry in info_data["registry_integrations"]["implemented"]:
            click.echo(f"  ✓ {registry}")

        click.echo("\nThird-party API Integrations:")
        click.echo(f"  {info_data['api_integrations']['note']}")
        for api in info_data["api_integrations"]["implemented"]:
            click.echo(f"  ✓ {api}")

        click.echo(f"\nLicense Detection: {info_data['license_detection']}")

        click.echo("\nEnrichment Modes:")
        for mode, description in info_data["enrichment_modes"].items():
            click.echo(f"  - {mode}: {description}")

        click.echo("\nOutput Formats:")
        click.echo(f"  {', '.join(info_data['output_formats'])}")


def main():
    """Main entry point for the CLI."""
    cli(obj={})


if __name__ == '__main__':
    main()