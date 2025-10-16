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
@click.option('--api', type=click.Choice(['clearlydefined', 'ecosystems', 'all', 'none']), default='none', help='API enrichment')
@click.option('--online', is_flag=True, help='Enable online mode to fetch missing metadata (e.g., parent POMs)')
@click.pass_context
def extract(ctx, package_path, output, format, pretty, api, online):
    """Extract metadata from a package file.
    
    Examples:
        upmex extract package.whl
        upmex extract --format text package.tgz
        upmex extract --api clearlydefined package.jar
    """
    config = ctx.obj['config']
    verbose = ctx.obj['verbose']
    
    # Update config with CLI options
    
    try:
        # Create extractor with online mode
        extractor_config = config.to_dict()
        extractor_config['online_mode'] = online
        extractor = PackageExtractor(extractor_config)
        
        # Extract metadata
        if verbose:
            click.echo(f"Extracting metadata from: {package_path}")
            if online:
                click.echo("Online mode enabled - will fetch missing metadata")
        
        metadata = extractor.extract(package_path)
        
        # API enrichment (placeholder for future)
        if api != 'none':
            click.echo(f"API enrichment with {api} not yet implemented", err=True)
        
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
            {"type": "python_wheel", "extensions": [".whl"]},
            {"type": "python_sdist", "extensions": [".tar.gz", ".zip"]},
            {"type": "npm", "extensions": [".tgz"]},
            {"type": "maven", "extensions": [".jar"]},
            {"type": "jar", "extensions": [".jar", ".war", ".ear"]},
        ],
        "detection_methods": ["regex", "dice_sorensen"],
        "api_integrations": ["clearlydefined", "ecosystems"],
        "output_formats": ["json", "text"]
    }
    
    if output_json:
        click.echo(json.dumps(info_data, indent=2))
    else:
        click.echo(f"UPMEX - Universal Package Metadata Extractor v{__version__}")
        click.echo("\nSupported Package Types:")
        for pkg in info_data["supported_packages"]:
            click.echo(f"  - {pkg['type']}: {', '.join(pkg['extensions'])}")
        click.echo("\nLicense Detection Methods:")
        for method in info_data["detection_methods"]:
            click.echo(f"  - {method}")
        click.echo("\nOutput Formats:")
        click.echo(f"  {', '.join(info_data['output_formats'])}")


def main():
    """Main entry point for the CLI."""
    cli(obj={})


if __name__ == '__main__':
    main()