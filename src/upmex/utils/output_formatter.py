"""Output formatting utilities for various formats."""

import json
from typing import Any, Dict
from ..core.models import PackageMetadata


class OutputFormatter:
    """Format package metadata for different output formats."""
    
    def __init__(self, pretty: bool = False):
        """Initialize formatter.
        
        Args:
            pretty: Whether to pretty-print output
        """
        self.pretty = pretty
    
    def format(self, metadata: PackageMetadata, format: str) -> str:
        """Format metadata to specified format.
        
        Args:
            metadata: Package metadata to format
            format: Output format (json, text)
            
        Returns:
            Formatted string
        """
        if format == 'json':
            return self.to_json(metadata)
        elif format == 'text':
            return self.to_text(metadata)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def format_dict(self, data: Dict[str, Any], format: str) -> str:
        """Format dictionary to specified format.
        
        Args:
            data: Dictionary to format
            format: Output format
            
        Returns:
            Formatted string
        """
        if format == 'json':
            if self.pretty:
                return json.dumps(data, indent=2, sort_keys=True)
            return json.dumps(data)
        else:
            return str(data)
    
    def to_json(self, metadata: PackageMetadata) -> str:
        """Convert metadata to JSON string.
        
        Args:
            metadata: Package metadata
            
        Returns:
            JSON string
        """
        data = metadata.to_dict()
        if self.pretty:
            return json.dumps(data, indent=2, sort_keys=True)
        return json.dumps(data)
    
    def to_text(self, metadata: PackageMetadata) -> str:
        """Convert metadata to human-readable text.
        
        Args:
            metadata: Package metadata
            
        Returns:
            Formatted text string
        """
        lines = []
        lines.append(f"Package: {metadata.name}")
        
        if metadata.version:
            lines.append(f"Version: {metadata.version}")
        
        lines.append(f"Type: {metadata.package_type.value}")
        
        if metadata.description:
            lines.append(f"Description: {metadata.description}")
        
        if metadata.homepage:
            lines.append(f"Homepage: {metadata.homepage}")
        
        if metadata.repository:
            lines.append(f"Repository: {metadata.repository}")
        
        if metadata.authors:
            lines.append("Authors:")
            for author in metadata.authors:
                name = author.get('name', 'Unknown')
                email = author.get('email', '')
                if email:
                    lines.append(f"  - {name} <{email}>")
                else:
                    lines.append(f"  - {name}")
        
        if metadata.licenses:
            lines.append("Licenses:")
            for license_info in metadata.licenses:
                if license_info.spdx_id:
                    lines.append(f"  - {license_info.spdx_id} (confidence: {license_info.confidence:.2%})")
                elif license_info.name:
                    lines.append(f"  - {license_info.name} (confidence: {license_info.confidence:.2%})")
                else:
                    lines.append(f"  - Unknown")
        
        if metadata.dependencies:
            lines.append("Dependencies:")
            # Handle both dict and list formats
            if isinstance(metadata.dependencies, dict):
                for dep_type, deps in metadata.dependencies.items():
                    if deps:
                        lines.append(f"  {dep_type}:")
                        for dep in deps:
                            lines.append(f"    - {dep}")
            elif isinstance(metadata.dependencies, list):
                for dep in metadata.dependencies:
                    if isinstance(dep, dict):
                        dep_str = dep.get('name', 'Unknown')
                        if dep.get('version'):
                            dep_str += f" {dep['version']}"
                        if dep.get('phase'):
                            dep_str += f" ({dep['phase']})"
                        lines.append(f"  - {dep_str}")
                    else:
                        lines.append(f"  - {dep}")
        
        if metadata.keywords:
            lines.append(f"Keywords: {', '.join(metadata.keywords)}")
        
        if metadata.file_size:
            lines.append(f"File Size: {metadata.file_size:,} bytes")
        
        if metadata.file_hash:
            lines.append(f"SHA256: {metadata.file_hash}")
        
        lines.append(f"Schema Version: {metadata.schema_version}")
        
        return '\n'.join(lines)