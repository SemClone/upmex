#!/bin/bash

echo "=== Testing NPM Packages ==="
for pkg in express-4.21.2.tgz yargs-17.7.2.tgz; do
    echo "Package: $pkg"
    upmex extract "$pkg" --format json 2>&1 | jq -c '{name: .package.name, license: .licensing.declared_licenses[0].spdx_id, confidence: .licensing.declared_licenses[0].confidence}'
    echo ""
done

echo "=== Testing Python Package ==="
echo "Package: requests-2.32.3-py3-none-any.whl"
upmex extract "requests-2.32.3-py3-none-any.whl" --format json 2>&1 | jq -c '{name: .package.name, license: .licensing.declared_licenses[0].spdx_id, confidence: .licensing.declared_licenses[0].confidence}'
echo ""

echo "=== Testing Java Packages ==="
for pkg in gson-2.10.1.jar guava-33.4.0-jre.jar; do
    echo "Package: $pkg"
    upmex extract "$pkg" --format json 2>&1 | jq -c '{name: .package.name, license: .licensing.declared_licenses[0].spdx_id, confidence: .licensing.declared_licenses[0].confidence}'
    echo ""
done

echo "=== Testing Ruby Package ==="
echo "Package: rails-7.1.5.gem"
upmex extract "rails-7.1.5.gem" --format json 2>&1 | jq -c '{name: .package.name, license: .licensing.declared_licenses[0].spdx_id, confidence: .licensing.declared_licenses[0].confidence}'
echo ""

echo "=== Testing Rust Packages ==="
for pkg in serde-1.0.210.crate tokio-1.41.0.crate; do
    echo "Package: $pkg"
    upmex extract "$pkg" --format json 2>&1 | jq -c '{name: .package.name, license: .licensing.declared_licenses[0].spdx_id, confidence: .licensing.declared_licenses[0].confidence}'
    echo ""
done

echo "=== Testing .NET Packages ==="
for pkg in Newtonsoft.Json.13.0.3.nupkg Serilog.3.1.1.nupkg; do
    echo "Package: $pkg"
    upmex extract "$pkg" --format json 2>&1 | jq -c '{name: .package.name, license: .licensing.declared_licenses[0].spdx_id, confidence: .licensing.declared_licenses[0].confidence}'
    echo ""
done

echo "=== Testing Go Packages ==="
for pkg in cobra-v1.8.1.zip gin-v1.10.0.zip; do
    echo "Package: $pkg"
    upmex extract "$pkg" --format json 2>&1 | jq -c '{name: .package.name, license: .licensing.declared_licenses[0].spdx_id, confidence: .licensing.declared_licenses[0].confidence}'
    echo ""
done
