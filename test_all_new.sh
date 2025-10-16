#\!/bin/bash

echo "Testing ALL Package Types:"
echo "=========================="

success=0
fail=0

# Test each package type
for pkg in test-packages/*; do
    [ -f "$pkg" ] || continue
    name=$(basename "$pkg")
    
    # Skip non-package files
    case "$name" in
        *.sh|gin-test|oslili_output.txt|test_license.txt|test_all.sh)
            continue
            ;;
    esac
    
    echo -n "$name: "
    result=$(upmex extract "$pkg" --format json 2>/dev/null | jq -r ".package.name // \"FAIL\"")
    
    if [ "$result" \!= "FAIL" ] && [ "$result" \!= "NO-ASSERTION" ]; then
        echo "✓ $result"
        ((success++))
    else
        echo "✗ Failed to extract"
        ((fail++))
    fi
done

echo ""
echo "Summary: $success succeeded, $fail failed"

