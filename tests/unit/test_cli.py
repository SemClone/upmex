"""Tests for CLI module."""

import json
import pytest
from pathlib import Path
from click.testing import CliRunner
from upmex.cli import cli
from upmex.core.models import PackageMetadata, PackageType


class TestCLI:
    """Test CLI commands."""
    
    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()
    
    @pytest.fixture
    def sample_package(self, temp_dir):
        """Create a sample package file."""
        import zipfile
        
        # Create a minimal wheel file
        wheel_path = temp_dir / "test_package-1.0.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, 'w') as zf:
            # Add minimal metadata
            metadata = """Name: test-package
Version: 1.0.0
Summary: Test package for CLI testing
Author: Test Author
Author-email: test@example.com
License: MIT
"""
            zf.writestr("test_package-1.0.0.dist-info/METADATA", metadata)
            zf.writestr("test_package/__init__.py", "# Test package")
        
        return str(wheel_path)
    
    def test_cli_version(self, runner):
        """Test version option."""
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert '1.6.0' in result.output
    
    def test_info_command(self, runner):
        """Test info command."""
        result = runner.invoke(cli, ['info'])
        assert result.exit_code == 0
        assert 'UPMEX' in result.output
        assert 'python_wheel' in result.output
        assert 'npm' in result.output
    
    def test_info_command_json(self, runner):
        """Test info command with JSON output."""
        result = runner.invoke(cli, ['info', '--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['version'] == '1.6.0'
        assert 'supported_packages' in data
    
    def test_detect_command(self, runner, sample_package):
        """Test detect command."""
        result = runner.invoke(cli, ['detect', sample_package])
        assert result.exit_code == 0
        assert 'python_wheel' in result.output
    
    def test_detect_command_verbose(self, runner, sample_package):
        """Test detect command with verbose output."""
        result = runner.invoke(cli, ['detect', '-v', sample_package])
        assert result.exit_code == 0
        assert 'File:' in result.output
        assert 'Size:' in result.output
        assert 'Type: python_wheel' in result.output
    
    def test_detect_nonexistent_file(self, runner):
        """Test detect command with non-existent file."""
        result = runner.invoke(cli, ['detect', 'nonexistent.whl'])
        assert result.exit_code == 2  # Click returns 2 for invalid arguments
        assert 'Error' in result.output
    
    def test_extract_command(self, runner, sample_package):
        """Test extract command."""
        result = runner.invoke(cli, ['extract', sample_package])
        assert result.exit_code == 0
        
        # Parse JSON output
        data = json.loads(result.output)
        assert data['package']['name'] == 'test-package'
        assert data['package']['version'] == '1.0.0'
        assert data['package']['type'] == 'python_wheel'
    
    def test_extract_command_pretty(self, runner, sample_package):
        """Test extract command with pretty print."""
        result = runner.invoke(cli, ['extract', '--pretty', sample_package])
        assert result.exit_code == 0
        assert '  "package"' in result.output  # Indented JSON
        assert 'test-package' in result.output
    
    def test_extract_command_text_format(self, runner, sample_package):
        """Test extract command with text format."""
        result = runner.invoke(cli, ['extract', '--format', 'text', sample_package])
        assert result.exit_code == 0
        assert 'Package: test-package' in result.output
        assert 'Version: 1.0.0' in result.output
        assert 'Type: python_wheel' in result.output
    
    def test_extract_with_output_file(self, runner, sample_package, temp_dir):
        """Test extract command with output file."""
        output_file = temp_dir / 'output.json'
        result = runner.invoke(cli, ['extract', sample_package, '-o', str(output_file)])
        assert result.exit_code == 0
        assert output_file.exists()
        
        # Check output file content
        data = json.loads(output_file.read_text())
        assert data['package']['name'] == 'test-package'
    
    def test_extract_quiet_mode(self, runner, sample_package, temp_dir):
        """Test extract command in quiet mode."""
        output_file = temp_dir / 'output.json'
        result = runner.invoke(cli, ['--quiet', 'extract', sample_package, '-o', str(output_file)])
        assert result.exit_code == 0
        assert 'Output written to' not in result.output
    
    def test_license_command(self, runner, sample_package):
        """Test license command."""
        result = runner.invoke(cli, ['license', sample_package])
        assert result.exit_code == 0
        # Note: Our sample doesn't have license detection yet
        # This will show "No license information found" for now
    
    def test_cli_with_config_file(self, runner, sample_package, temp_dir):
        """Test CLI with custom config file."""
        config_file = temp_dir / 'config.json'
        config_file.write_text(json.dumps({
            "output": {"format": "json", "pretty_print": True}
        }))
        
        result = runner.invoke(cli, ['--config', str(config_file), 'extract', sample_package])
        assert result.exit_code == 0