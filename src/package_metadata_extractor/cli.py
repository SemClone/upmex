"""Command-line interface for package metadata extractor."""

import sys
import json
import click
from pathlib import Path
from typing import Optional, List
import logging

from package_metadata_extractor import __version__
from package_metadata_extractor.core.extractor import PackageExtractor
from package_metadata_extractor.core.models import PackageType
from package_metadata_extractor.config import Config
from package_metadata_extractor.utils.package_detector import detect_package_type
from package_metadata_extractor.utils.output_formatter import OutputFormatter

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="package-metadata-extractor")
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--quiet', '-q', is_flag=True, help='Suppress all output except results')
@click.pass_context
def cli(ctx, config, verbose, quiet):
    """Package Metadata Extractor - Extract metadata from various package formats."""
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
@click.option('--format', '-f', type=click.Choice(['json', 'yaml', 'text']), default='json', help='Output format')
@click.option('--pretty', '-p', is_flag=True, help='Pretty print output')
@click.option('--api', type=click.Choice(['clearlydefined', 'ecosystems', 'all', 'none']), default='none', help='API enrichment')
@click.option('--no-cache', is_flag=True, help='Disable caching')
@click.pass_context
def extract(ctx, package_path, output, format, pretty, api, no_cache):
    """Extract metadata from a package file.
    
    Examples:
        package-metadata-extractor extract package.whl
        package-metadata-extractor extract --format yaml package.tgz
        package-metadata-extractor extract --api clearlydefined package.jar
    """
    config = ctx.obj['config']
    verbose = ctx.obj['verbose']
    
    # Update config with CLI options
    if no_cache:
        config.set('extraction.cache_enabled', False)
    
    try:
        # Create extractor
        extractor = PackageExtractor(config.to_dict())
        
        # Extract metadata
        if verbose:
            click.echo(f"Extracting metadata from: {package_path}")
        
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
        package-metadata-extractor detect package.whl
        package-metadata-extractor detect -v unknown.tar.gz
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
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), default='results.json', help='Output file path')
@click.option('--format', '-f', type=click.Choice(['json', 'jsonl', 'csv']), default='json', help='Output format')
@click.option('--parallel', '-p', is_flag=True, help='Process packages in parallel')
@click.option('--continue-on-error', is_flag=True, help='Continue processing on errors')
@click.option('--progress', is_flag=True, help='Show progress bar')
@click.pass_context
def batch(ctx, input_file, output, format, parallel, continue_on_error, progress):
    """Process multiple packages from a list file.
    
    The input file should contain one package path per line.
    
    Examples:
        package-metadata-extractor batch packages.txt
        package-metadata-extractor batch --format jsonl --progress packages.txt
    """
    config = ctx.obj['config']
    
    try:
        # Read package list
        package_paths = Path(input_file).read_text().strip().split('\n')
        package_paths = [p.strip() for p in package_paths if p.strip()]
        
        if not package_paths:
            click.echo("No packages found in input file", err=True)
            sys.exit(1)
        
        click.echo(f"Processing {len(package_paths)} packages...")
        
        # Create extractor
        extractor = PackageExtractor(config.to_dict())
        results = []
        errors = []
        
        # Process packages
        def process_package(package_path):
            """Process a single package."""
            try:
                if not Path(package_path).exists():
                    raise FileNotFoundError(f"Package not found: {package_path}")
                
                metadata = extractor.extract(package_path)
                results.append(metadata.to_dict())
                
            except Exception as e:
                error_info = {"package": package_path, "error": str(e)}
                errors.append(error_info)
                
                if not continue_on_error:
                    click.echo(f"\nError processing {package_path}: {e}", err=True)
                    raise
        
        if progress:
            with click.progressbar(package_paths, show_pos=True, show_percent=True) as bar:
                for package_path in bar:
                    try:
                        process_package(package_path)
                    except:
                        sys.exit(1)
        else:
            for package_path in package_paths:
                try:
                    process_package(package_path)
                except:
                    sys.exit(1)
        
        # Format and write output
        formatter = OutputFormatter()
        
        if format == 'json':
            output_data = {
                "packages": results,
                "errors": errors,
                "summary": {
                    "total": len(package_paths),
                    "successful": len(results),
                    "failed": len(errors)
                }
            }
            output_text = formatter.format_dict(output_data, 'json')
        elif format == 'jsonl':
            # JSON Lines format - one JSON object per line
            lines = []
            for result in results:
                lines.append(json.dumps(result))
            output_text = '\n'.join(lines)
        else:  # csv
            output_text = formatter.to_csv(results)
        
        # Write output
        Path(output).write_text(output_text)
        
        # Print summary
        click.echo(f"\nProcessed: {len(results)} successful, {len(errors)} failed")
        click.echo(f"Output written to: {output}")
        
        if errors and not continue_on_error:
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('package_path', type=click.Path(exists=True))
@click.option('--confidence', '-c', is_flag=True, help='Show confidence scores')
@click.option('--all-methods', is_flag=True, help='Use all detection methods')
@click.pass_context
def license(ctx, package_path, confidence, all_methods):
    """Extract only license information from a package.
    
    Examples:
        package-metadata-extractor license package.whl
        package-metadata-extractor license -c package.tar.gz
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
            
            if confidence:
                click.echo(f"  Confidence: {license_info.confidence:.2%}")
                click.echo(f"  Level: {license_info.confidence_level.value}")
                if license_info.detection_method:
                    click.echo(f"  Method: {license_info.detection_method}")
                if license_info.file_path:
                    click.echo(f"  Source: {license_info.file_path}")
                    
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
@click.pass_context
def info(ctx, output_json):
    """Show information about the package metadata extractor.
    
    Examples:
        package-metadata-extractor info
        package-metadata-extractor info --json
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
        "output_formats": ["json", "yaml", "text", "csv", "jsonl"]
    }
    
    if output_json:
        click.echo(json.dumps(info_data, indent=2))
    else:
        click.echo(f"Package Metadata Extractor v{__version__}")
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