#!/bin/bash

echo "======================================"
echo "UPMEX Comprehensive Package Testing"
echo "======================================"
echo ""

total=0
success=0
failed=0

# Test all package types
for ext in tgz whl jar gem crate nupkg zip; do
  for pkg in *.$ext; do
    if [ -f "$pkg" ]; then
      ((total++))
      echo "[$total] Testing: $pkg"
      
      result=$(upmex extract "$pkg" --format json 2>&1)
      
      if echo "$result" | jq -e '.licensing.declared_licenses[0]' >/dev/null 2>&1; then
        license=$(echo "$result" | jq -r '.licensing.declared_licenses[0].spdx_id')
        confidence=$(echo "$result" | jq -r '.licensing.declared_licenses[0].confidence')
        name=$(echo "$result" | jq -r '.package.name')
        echo "    Package: $name"
        echo "    License: $license (confidence: $confidence)"
        echo "    Status: SUCCESS"
        ((success++))
      else
        name=$(echo "$result" | jq -r '.package.name' 2>/dev/null || echo "UNKNOWN")
        echo "    Package: $name"
        echo "    Status: NO LICENSE DETECTED"
        ((failed++))
      fi
      echo ""
    fi
  done
done

echo "======================================"
echo "SUMMARY"
echo "======================================"
echo "Total packages tested: $total"
echo "Successfully detected licenses: $success"
echo "Failed to detect licenses: $failed"

if [ $total -gt 0 ]; then
  success_rate=$(echo "scale=1; $success * 100 / $total" | bc)
  echo "Success rate: ${success_rate}%"
fi

if [ $failed -eq 0 ]; then
  echo ""
  echo "All tests passed!"
  exit 0
else
  echo ""
  echo "Some packages failed license detection"
  exit 1
fi
