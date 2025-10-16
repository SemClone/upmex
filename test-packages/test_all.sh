#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}===================================================${NC}"
echo -e "${YELLOW}     UPMEX Comprehensive Package Testing Suite    ${NC}"
echo -e "${YELLOW}===================================================${NC}"
echo ""

# Function to test a package
test_package() {
    local pkg=$1
    local expected_license=$2

    echo -n "Testing $pkg... "

    result=$(upmex extract "$pkg" --format json 2>/dev/null)

    if [ $? -ne 0 ]; then
        echo -e "${RED}FAILED (extraction error)${NC}"
        return 1
    fi

    # Extract license info
    license=$(echo "$result" | jq -r '.licensing.declared_licenses[0].spdx_id // "NONE"')
    confidence=$(echo "$result" | jq -r '.licensing.declared_licenses[0].confidence // 0')
    name=$(echo "$result" | jq -r '.package.name')

    if [ "$license" = "NONE" ]; then
        echo -e "${RED}FAILED (no license detected)${NC}"
        echo "  Package: $name"
        return 1
    fi

    # Check if license matches expected (if provided)
    if [ -n "$expected_license" ] && [ "$license" != "$expected_license" ]; then
        echo -e "${YELLOW}WARNING${NC}"
        echo "  Package: $name"
        echo "  Expected: $expected_license, Got: $license (confidence: $confidence)"
    else
        echo -e "${GREEN}OK${NC}"
        echo "  Package: $name"
        echo "  License: $license (confidence: $confidence)"
    fi

    return 0
}

# Test counters
total=0
passed=0
failed=0
warnings=0

echo -e "${YELLOW}=== NPM Packages ===${NC}"
for pkg in *.tgz; do
    if [ -f "$pkg" ]; then
        ((total++))
        if test_package "$pkg" "MIT"; then
            ((passed++))
        else
            ((failed++))
        fi
    fi
done
echo ""

echo -e "${YELLOW}=== Python Packages ===${NC}"
for pkg in *.whl; do
    if [ -f "$pkg" ]; then
        ((total++))
        case "$pkg" in
            Django*) expected="BSD-3-Clause" ;;
            flask*) expected="BSD-3-Clause" ;;
            numpy*) expected="BSD-3-Clause" ;;
            requests*) expected="Apache-2.0" ;;
            *) expected="" ;;
        esac
        if test_package "$pkg" "$expected"; then
            ((passed++))
        else
            ((failed++))
        fi
    fi
done
echo ""

echo -e "${YELLOW}=== Java Packages ===${NC}"
for pkg in *.jar; do
    if [ -f "$pkg" ]; then
        ((total++))
        case "$pkg" in
            junit*) expected="EPL-2.0" ;;
            *) expected="Apache-2.0" ;;
        esac
        if test_package "$pkg" "$expected"; then
            ((passed++))
        else
            ((failed++))
        fi
    fi
done
echo ""

echo -e "${YELLOW}=== Ruby Packages ===${NC}"
for pkg in *.gem; do
    if [ -f "$pkg" ]; then
        ((total++))
        if test_package "$pkg" "MIT"; then
            ((passed++))
        else
            ((failed++))
        fi
    fi
done
echo ""

echo -e "${YELLOW}=== Rust Packages ===${NC}"
for pkg in *.crate; do
    if [ -f "$pkg" ]; then
        ((total++))
        if test_package "$pkg" ""; then
            ((passed++))
        else
            ((failed++))
        fi
    fi
done
echo ""

echo -e "${YELLOW}=== .NET Packages ===${NC}"
for pkg in *.nupkg; do
    if [ -f "$pkg" ]; then
        ((total++))
        case "$pkg" in
            Newtonsoft*) expected="MIT" ;;
            *) expected="Apache-2.0" ;;
        esac
        if test_package "$pkg" "$expected"; then
            ((passed++))
        else
            ((failed++))
        fi
    fi
done
echo ""

echo -e "${YELLOW}=== Go Packages ===${NC}"
for pkg in *.zip; do
    if [ -f "$pkg" ]; then
        ((total++))
        if test_package "$pkg" "Apache-2.0"; then
            ((passed++))
        else
            ((failed++))
        fi
    fi
done
echo ""

echo -e "${YELLOW}=== DEB Packages ===${NC}"
for pkg in *.deb; do
    if [ -f "$pkg" ]; then
        ((total++))
        if test_package "$pkg" ""; then
            ((passed++))
        else
            ((failed++))
        fi
    fi
done
echo ""

# Summary
echo -e "${YELLOW}===================================================${NC}"
echo -e "${YELLOW}                    SUMMARY                       ${NC}"
echo -e "${YELLOW}===================================================${NC}"
echo "Total packages tested: $total"
echo -e "Passed: ${GREEN}$passed${NC}"
echo -e "Failed: ${RED}$failed${NC}"

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi