#!/bin/bash
# Functional tests for upmex - can be run locally or in CI

set -e

echo "=== Running Functional Tests for UPMEX ==="
echo

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0
SKIPPED=0

# Test function
run_test() {
    local test_name="$1"
    local command="$2"
    local expected="$3"

    printf "Testing %-50s " "$test_name..."

    # Check if file exists for package tests
    if [[ "$command" == *"test-packages/"* ]]; then
        pkg_file=$(echo "$command" | grep -o 'test-packages/[^ ]*' | head -1)
        if [ ! -f "$pkg_file" ]; then
            echo -e "${YELLOW}SKIPPED${NC} (file not found)"
            ((SKIPPED++))
            return
        fi
    fi

    # Run the test
    if output=$(eval "$command" 2>&1); then
        if [ -n "$expected" ]; then
            if echo "$output" | grep -q "$expected"; then
                echo -e "${GREEN}✓${NC}"
                ((PASSED++))
            else
                echo -e "${RED}✗${NC} (expected: $expected)"
                ((FAILED++))
            fi
        else
            echo -e "${GREEN}✓${NC}"
            ((PASSED++))
        fi
    else
        echo -e "${RED}✗${NC} (command failed)"
        ((FAILED++))
    fi
}

# Check if upmex is installed
if ! command -v upmex &> /dev/null; then
    echo "Error: upmex is not installed or not in PATH"
    echo "Please run: pip install -e ."
    exit 1
fi

echo "Using upmex version: $(upmex --version)"
echo

# Test 1: Basic extraction for all package types
echo "=== Test 1: Basic Extraction ==="
run_test "NPM package (express)" "upmex extract test-packages/express-4.21.2.tgz" '"name": "express"'
run_test "Python wheel (requests)" "upmex extract test-packages/requests-2.32.3-py3-none-any.whl" '"name": "requests"'
run_test "Java JAR (gson)" "upmex extract test-packages/gson-2.10.1.jar" '"name": "com.google.code.gson:gson"'
run_test "Ruby gem (rails)" "upmex extract test-packages/rails-7.1.5.gem" '"name": "rails"'
run_test "Rust crate (serde)" "upmex extract test-packages/serde-1.0.210.crate" '"name": "serde"'
run_test "NuGet package (Newtonsoft)" "upmex extract test-packages/Newtonsoft.Json.13.0.3.nupkg" '"name": "Newtonsoft.Json"'
run_test "Debian package (hello)" "upmex extract test-packages/hello_2.10-3_amd64.deb" '"name": "hello"'
run_test "RPM package (zsh)" "upmex extract test-packages/zsh-5.0.2-34.el7_8.2.x86_64.rpm" '"name": "zsh"'
run_test "Conda package (numpy)" "upmex extract test-packages/numpy-1.26.4-py312hc5e2394_0.conda" '"name": "numpy"'
run_test "Conan package (fmt)" "upmex extract test-packages/fmt-10.2.1.tgz" '"name": "fmt"'
run_test "Perl package (Capture-Tiny)" "upmex extract test-packages/Capture-Tiny-0.48.tar.gz" '"name": "Capture-Tiny"'
run_test "CocoaPods (AFNetworking)" "upmex extract test-packages/AFNetworking-4.0.1.podspec.json" '"name": "AFNetworking"'
run_test "Gradle build file" "upmex extract test-packages/build.gradle" '"package_type": "gradle"'
echo

# Test 2: Output formats
echo "=== Test 2: Output Formats ==="
run_test "JSON output (default)" "upmex extract test-packages/express-4.21.2.tgz | python -m json.tool > /dev/null"
run_test "Pretty JSON output" "upmex extract --pretty test-packages/rails-7.1.5.gem | head -1" "{"
run_test "Text format output" "upmex extract --format text test-packages/gson-2.10.1.jar" "Package: com.google.code.gson:gson"
run_test "Output to file" "upmex extract test-packages/serde-1.0.210.crate -o /tmp/test_output.json && [ -f /tmp/test_output.json ]"
echo

# Test 3: Package detection
echo "=== Test 3: Package Type Detection ==="
run_test "Detect NPM package" "upmex detect test-packages/express-4.21.2.tgz" "npm"
run_test "Detect Python wheel" "upmex detect test-packages/requests-2.32.3-py3-none-any.whl" "python_wheel"
run_test "Detect Java JAR" "upmex detect test-packages/gson-2.10.1.jar" "maven"
run_test "Detect Ruby gem" "upmex detect test-packages/rails-7.1.5.gem" "ruby_gem"
run_test "Detect Rust crate" "upmex detect test-packages/serde-1.0.210.crate" "rust_crate"
run_test "Detect NuGet package" "upmex detect test-packages/Newtonsoft.Json.13.0.3.nupkg" "nuget"
run_test "Detect Debian package" "upmex detect test-packages/hello_2.10-3_amd64.deb" "deb"
run_test "Detect RPM package" "upmex detect test-packages/zsh-5.0.2-34.el7_8.2.x86_64.rpm" "rpm"
run_test "Detect Conda package" "upmex detect test-packages/numpy-1.26.4-py312hc5e2394_0.conda" "conda"
echo

# Test 4: License detection
echo "=== Test 4: License Detection ==="
run_test "MIT license (express)" "upmex license test-packages/express-4.21.2.tgz" "MIT"
run_test "Apache-2.0 license (gson)" "upmex license test-packages/gson-2.10.1.jar" "Apache-2.0"
run_test "MIT license (rails)" "upmex license test-packages/rails-7.1.5.gem" "MIT"
echo

# Test 5: Performance tests
echo "=== Test 5: Performance Tests ==="
for pkg in test-packages/guava-33.4.0-jre.jar test-packages/Newtonsoft.Json.13.0.3.nupkg test-packages/zsh-5.0.2-34.el7_8.2.x86_64.rpm; do
    if [ -f "$pkg" ]; then
        name=$(basename "$pkg")
        size=$(du -h "$pkg" | cut -f1)
        printf "Testing %-40s (size: %s) " "$name" "$size"

        start_time=$(date +%s%N)
        timeout 5 upmex extract "$pkg" > /dev/null 2>&1
        exit_code=$?
        end_time=$(date +%s%N)

        if [ $exit_code -eq 124 ]; then
            echo -e "${RED}✗${NC} (timeout > 5s)"
            ((FAILED++))
        else
            duration=$((($end_time - $start_time) / 1000000))
            if [ $duration -lt 2000 ]; then
                echo -e "${GREEN}✓${NC} (${duration}ms)"
                ((PASSED++))
            else
                echo -e "${YELLOW}✓${NC} (${duration}ms - slow but passed)"
                ((PASSED++))
            fi
        fi
    fi
done
echo

# Test 6: Error handling
echo "=== Test 6: Error Handling ==="
run_test "Non-existent file" "! upmex extract /tmp/nonexistent.pkg 2>/dev/null"
run_test "Invalid package format" "echo 'not a package' > /tmp/invalid.txt && ! upmex extract /tmp/invalid.txt 2>/dev/null"
echo

# Clean up
rm -f /tmp/test_output.json /tmp/invalid.txt

# Summary
echo "========================================"
echo "            TEST SUMMARY"
echo "========================================"
echo -e "Passed:  ${GREEN}$PASSED${NC}"
echo -e "Failed:  ${RED}$FAILED${NC}"
echo -e "Skipped: ${YELLOW}$SKIPPED${NC}"
echo "========================================"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi