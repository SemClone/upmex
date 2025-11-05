# UPMEX Examples

This document provides practical examples of using UPMEX in various scenarios.

## Basic Examples

### Extract Metadata from a Python Wheel

```bash
upmex extract numpy-1.24.0-py3-none-any.whl
```

Output:
```json
{
  "package": {
    "name": "numpy",
    "version": "1.24.0",
    "type": "wheel",
    "purl": "pkg:pypi/numpy@1.24.0"
  },
  "licensing": {
    "licenses": [
      {
        "spdx_id": "BSD-3-Clause",
        "name": "BSD 3-Clause License"
      }
    ]
  }
}
```

### Extract from NPM Package

```bash
upmex extract express-4.18.0.tgz --pretty
```

### Extract from Java JAR

```bash
upmex extract commons-lang3-3.12.0.jar -o metadata.json
```

## Real-World Scenarios

### Scenario 1: License Compliance Check

Check licenses for all dependencies in a project:

```bash
#!/bin/bash
# check-licenses.sh

ALLOWED_LICENSES="MIT Apache-2.0 BSD-3-Clause BSD-2-Clause ISC"

for package in lib/*.jar; do
    echo "Checking $package..."

    # Extract metadata
    metadata=$(upmex extract "$package" 2>/dev/null)

    # Get license
    license=$(echo "$metadata" | jq -r '.licensing.licenses[0].spdx_id // "UNKNOWN"')

    # Check if allowed
    if [[ " $ALLOWED_LICENSES " =~ " $license " ]]; then
        echo "  ✓ License: $license (approved)"
    else
        echo "  ✗ License: $license (NOT APPROVED)"
        exit 1
    fi
done
```

### Scenario 2: Generate Software Bill of Materials (SBOM)

```python
#!/usr/bin/env python3
"""Generate SBOM for all packages in a directory"""

import json
from pathlib import Path
from upmex import PackageExtractor

def generate_sbom(directory):
    """Generate SBOM for all packages in directory"""

    extractor = PackageExtractor()
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "components": []
    }

    for package_file in Path(directory).glob("*"):
        try:
            metadata = extractor.extract(str(package_file))

            component = {
                "type": "library",
                "bom-ref": metadata.purl,
                "name": metadata.name,
                "version": metadata.version,
                "purl": metadata.purl,
                "licenses": []
            }

            for license in metadata.licenses:
                component["licenses"].append({
                    "license": {
                        "id": license.spdx_id or license.name
                    }
                })

            sbom["components"].append(component)
            print(f"Added: {metadata.name}@{metadata.version}")

        except Exception as e:
            print(f"Error processing {package_file}: {e}")

    return sbom

# Generate SBOM
sbom = generate_sbom("./dependencies")

# Save to file
with open("sbom.json", "w") as f:
    json.dump(sbom, f, indent=2)

print(f"SBOM generated with {len(sbom['components'])} components")
```

### Scenario 3: Vulnerability Scanning

```python
#!/usr/bin/env python3
"""Scan packages for vulnerabilities"""

from upmex import PackageExtractor
from upmex.config import Config
import sys

# Configure for vulnerability scanning
config = Config()
config.api.vulnerablecode.enabled = True
config.api.vulnerablecode.api_key = os.getenv('PME_VULNERABLECODE_API_KEY')

extractor = PackageExtractor(config=config)

def scan_for_vulnerabilities(package_path):
    """Scan package for known vulnerabilities"""

    metadata = extractor.extract(package_path)

    # Check if vulnerabilities were found
    vulns = metadata.metadata.get('vulnerabilities', [])

    if vulns:
        print(f"⚠️  {metadata.name}@{metadata.version} has {len(vulns)} vulnerabilities:")
        for vuln in vulns:
            print(f"   - {vuln['id']}: {vuln['summary']}")
            print(f"     Severity: {vuln['severity']}")
        return False
    else:
        print(f"✓ {metadata.name}@{metadata.version} - No known vulnerabilities")
        return True

# Scan package
package = sys.argv[1] if len(sys.argv) > 1 else "package.jar"
is_safe = scan_for_vulnerabilities(package)

sys.exit(0 if is_safe else 1)
```

### Scenario 4: Dependency Analysis

```python
#!/usr/bin/env python3
"""Analyze package dependencies"""

from upmex import PackageExtractor
import networkx as nx
import matplotlib.pyplot as plt

def analyze_dependencies(package_path):
    """Create dependency graph"""

    extractor = PackageExtractor()
    metadata = extractor.extract(package_path)

    # Create directed graph
    G = nx.DiGraph()

    # Add root node
    root = f"{metadata.name}@{metadata.version}"
    G.add_node(root, type='root')

    # Add dependencies
    for dep in metadata.dependencies.runtime:
        dep_node = f"{dep.name}@{dep.version_constraint}"
        G.add_node(dep_node, type='runtime')
        G.add_edge(root, dep_node)

    for dep in metadata.dependencies.development:
        dep_node = f"{dep.name}@{dep.version_constraint}"
        G.add_node(dep_node, type='development')
        G.add_edge(root, dep_node)

    # Visualize
    pos = nx.spring_layout(G)

    # Color nodes by type
    colors = []
    for node in G.nodes():
        if G.nodes[node]['type'] == 'root':
            colors.append('red')
        elif G.nodes[node]['type'] == 'runtime':
            colors.append('blue')
        else:
            colors.append('gray')

    nx.draw(G, pos, node_color=colors, with_labels=True,
            node_size=3000, font_size=8, arrows=True)

    plt.title(f"Dependency Graph for {metadata.name}")
    plt.savefig("dependencies.png")
    plt.show()

    print(f"Total dependencies: {len(G.nodes()) - 1}")
    print(f"Runtime: {len(metadata.dependencies.runtime)}")
    print(f"Development: {len(metadata.dependencies.development)}")

analyze_dependencies("package.whl")
```

## API Enrichment Examples

### Using ClearlyDefined

```bash
# Get comprehensive license data
upmex extract --api clearlydefined lodash-4.17.21.tgz
```

Enhanced output includes:
- License score
- Attribution requirements
- Copyright holders
- Source location

### Using Ecosyste.ms

```bash
# Get ecosystem data
upmex extract --api ecosystems requests-2.28.0.tar.gz
```

Enhanced output includes:
- Download statistics
- Repository metrics
- Maintainer information
- Version history

### Combined Enrichment

```bash
# Use all available APIs
upmex extract --api all --registry package.jar --pretty -o full-metadata.json
```

## Integration Examples

### Integration with CI/CD

#### GitHub Actions

```yaml
name: Package Analysis

on: [push, pull_request]

jobs:
  analyze-dependencies:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install UPMEX
      run: pip install upmex

    - name: Extract Package Metadata
      run: |
        for package in lib/*.jar; do
          upmex extract "$package" -o "metadata/$(basename $package .jar).json"
        done

    - name: Check Licenses
      run: |
        python scripts/check_licenses.py metadata/*.json

    - name: Upload Metadata
      uses: actions/upload-artifact@v3
      with:
        name: package-metadata
        path: metadata/
```

#### GitLab CI

```yaml
analyze-packages:
  stage: analyze
  script:
    - pip install upmex
    - mkdir -p reports
    - |
      for pkg in dependencies/*.whl; do
        upmex extract "$pkg" -o "reports/$(basename $pkg .whl).json"
      done
    - python scripts/generate_sbom.py reports/ > sbom.json
  artifacts:
    reports:
      sbom: sbom.json
    paths:
      - reports/
```

### Integration with SEMCL.ONE Tools

#### Complete Workflow

```bash
#!/bin/bash
# complete-analysis.sh

# 1. Extract metadata with UPMEX
echo "Extracting package metadata..."
upmex extract library.jar -o metadata.json

# 2. Generate legal notices with purl2notices
echo "Generating legal notices..."
purl=$(jq -r '.package.purl' metadata.json)
purl2notices -i "$purl" -o NOTICE.txt

# 3. Check license compliance with ospac
echo "Checking compliance..."
ospac evaluate NOTICE.txt --policy compliance-policy.yaml

# 4. Scan with osslili for additional licenses
echo "Deep license scan..."
osslili scan extracted/ -o license-report.json

echo "Analysis complete!"
```

#### Python Integration

```python
#!/usr/bin/env python3
"""Complete SEMCL.ONE workflow"""

from upmex import PackageExtractor
import subprocess
import json

def complete_analysis(package_path):
    """Run complete SEMCL.ONE analysis"""

    # Extract metadata
    extractor = PackageExtractor()
    metadata = extractor.extract(package_path)

    # Save metadata
    with open("metadata.json", "w") as f:
        json.dump(metadata.to_dict(), f, indent=2)

    # Generate notices
    purl = metadata.purl
    subprocess.run([
        "purl2notices",
        "-i", purl,
        "-o", "NOTICE.txt"
    ])

    # Check compliance
    result = subprocess.run([
        "ospac",
        "evaluate",
        "NOTICE.txt",
        "--policy", "policy.yaml"
    ], capture_output=True)

    if result.returncode == 0:
        print("✓ Package is compliant")
    else:
        print("✗ Compliance issues found")
        print(result.stdout.decode())

    return result.returncode == 0

# Analyze package
compliant = complete_analysis("package.jar")
```

## Advanced Examples

### Custom Package Format

```python
from upmex.extractors import BaseExtractor
from upmex import register_extractor, PackageMetadata, PackageType

class CustomPackageExtractor(BaseExtractor):
    """Extractor for custom package format"""

    @classmethod
    def can_extract(cls, file_path: str) -> bool:
        return file_path.endswith('.custom')

    def extract(self, file_path: str) -> PackageMetadata:
        # Parse custom format
        with open(file_path, 'r') as f:
            data = parse_custom_format(f.read())

        return PackageMetadata(
            name=data['name'],
            version=data['version'],
            package_type=PackageType.UNKNOWN,
            purl=f"pkg:custom/{data['name']}@{data['version']}",
            description=data.get('description'),
            licenses=self.extract_licenses(data)
        )

# Register custom extractor
register_extractor(CustomPackageExtractor)

# Now can extract custom packages
extractor = PackageExtractor()
metadata = extractor.extract("package.custom")
```

### Parallel Processing

```python
#!/usr/bin/env python3
"""Process multiple packages in parallel"""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from upmex import PackageExtractor
import json

def process_package(package_path):
    """Process single package"""
    try:
        extractor = PackageExtractor()
        metadata = extractor.extract(str(package_path))
        return {
            'success': True,
            'file': package_path.name,
            'metadata': metadata.to_dict()
        }
    except Exception as e:
        return {
            'success': False,
            'file': package_path.name,
            'error': str(e)
        }

def parallel_extraction(directory, max_workers=4):
    """Extract metadata from all packages in parallel"""

    packages = list(Path(directory).glob("*"))
    results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for result in executor.map(process_package, packages):
            results.append(result)

            if result['success']:
                print(f"✓ {result['file']}")
            else:
                print(f"✗ {result['file']}: {result['error']}")

    # Save results
    with open("extraction_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Statistics
    successful = sum(1 for r in results if r['success'])
    print(f"\nProcessed {len(results)} packages")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")

# Run parallel extraction
parallel_extraction("./packages", max_workers=8)
```

### Custom Reporting

```python
#!/usr/bin/env python3
"""Generate custom HTML report"""

from upmex import PackageExtractor
from pathlib import Path
from jinja2 import Template

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Package Analysis Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        .license-ok { color: green; }
        .license-warn { color: orange; }
        .license-error { color: red; }
    </style>
</head>
<body>
    <h1>Package Analysis Report</h1>
    <p>Generated: {{ timestamp }}</p>

    <table>
        <tr>
            <th>Package</th>
            <th>Version</th>
            <th>License</th>
            <th>Dependencies</th>
            <th>PURL</th>
        </tr>
        {% for pkg in packages %}
        <tr>
            <td>{{ pkg.name }}</td>
            <td>{{ pkg.version }}</td>
            <td class="{{ pkg.license_class }}">{{ pkg.license }}</td>
            <td>{{ pkg.dep_count }}</td>
            <td><code>{{ pkg.purl }}</code></td>
        </tr>
        {% endfor %}
    </table>

    <h2>Summary</h2>
    <ul>
        <li>Total Packages: {{ total_packages }}</li>
        <li>Unique Licenses: {{ unique_licenses|length }}</li>
        <li>Total Dependencies: {{ total_deps }}</li>
    </ul>

    <h3>License Distribution</h3>
    <ul>
        {% for license, count in license_counts.items() %}
        <li>{{ license }}: {{ count }}</li>
        {% endfor %}
    </ul>
</body>
</html>
"""

def generate_html_report(directory):
    """Generate HTML report for all packages"""

    extractor = PackageExtractor()
    packages_data = []
    license_counts = {}
    total_deps = 0

    for package_file in Path(directory).glob("*"):
        try:
            metadata = extractor.extract(str(package_file))

            license_name = metadata.licenses[0].spdx_id if metadata.licenses else "UNKNOWN"
            dep_count = len(metadata.dependencies.runtime) + len(metadata.dependencies.development)

            # Determine license class
            if license_name in ["MIT", "Apache-2.0", "BSD-3-Clause"]:
                license_class = "license-ok"
            elif license_name == "UNKNOWN":
                license_class = "license-error"
            else:
                license_class = "license-warn"

            packages_data.append({
                'name': metadata.name,
                'version': metadata.version,
                'license': license_name,
                'license_class': license_class,
                'dep_count': dep_count,
                'purl': metadata.purl
            })

            # Count licenses
            license_counts[license_name] = license_counts.get(license_name, 0) + 1
            total_deps += dep_count

        except Exception as e:
            print(f"Error processing {package_file}: {e}")

    # Generate report
    template = Template(HTML_TEMPLATE)
    html = template.render(
        packages=packages_data,
        total_packages=len(packages_data),
        unique_licenses=set(p['license'] for p in packages_data),
        total_deps=total_deps,
        license_counts=license_counts,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # Save report
    with open("report.html", "w") as f:
        f.write(html)

    print(f"Report generated: report.html")
    print(f"Analyzed {len(packages_data)} packages")

# Generate report
from datetime import datetime
generate_html_report("./packages")
```

## Command-Line Tips

### Useful One-Liners

```bash
# Extract name and version only
upmex extract package.whl | jq -r '"\(.package.name)@\(.package.version)"'

# Get all licenses from multiple packages
for pkg in *.jar; do
    upmex extract "$pkg" | jq -r '.licensing.licenses[].spdx_id'
done | sort | uniq

# Find packages with no license
for pkg in *.whl; do
    license=$(upmex extract "$pkg" | jq -r '.licensing.licenses[0].spdx_id // "NONE"')
    [ "$license" = "NONE" ] && echo "$pkg"
done

# Create CSV of package data
echo "Package,Version,License,PURL" > packages.csv
for pkg in *.gem; do
    upmex extract "$pkg" | \
    jq -r '[.package.name, .package.version, .licensing.licenses[0].spdx_id // "UNKNOWN", .package.purl] | @csv' \
    >> packages.csv
done
```

### Filtering and Processing

```bash
# Find packages with specific license
upmex extract *.jar | jq 'select(.licensing.licenses[].spdx_id == "Apache-2.0")'

# Extract packages with vulnerabilities
upmex extract --api vulnerablecode package.jar | \
    jq 'select(.metadata.vulnerabilities | length > 0)'

# Get dependency tree
upmex extract package.whl | \
    jq '.dependencies.runtime[] | "\(.name) \(.version_constraint)"'
```