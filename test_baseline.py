#!/usr/bin/env python3
"""Baseline test to verify all extractors work before refactoring."""

import json
import os
from pathlib import Path
from src.upmex import PackageExtractor

def test_package(extractor, package_path, expected_type):
    """Test a single package extraction."""
    print(f"\nTesting {package_path}...")
    try:
        metadata = extractor.extract(package_path)
        
        # Basic validation
        assert metadata.name, f"Missing name for {package_path}"
        assert metadata.version, f"Missing version for {package_path}"
        assert metadata.package_type.value == expected_type, f"Wrong type: {metadata.package_type.value} != {expected_type}"
        
        # Print summary
        print(f"  ✓ Name: {metadata.name}")
        print(f"  ✓ Version: {metadata.version}")
        print(f"  ✓ Type: {metadata.package_type.value}")
        print(f"  ✓ Licenses: {len(metadata.licenses) if metadata.licenses else 0}")
        print(f"  ✓ Dependencies: {len(metadata.dependencies) if metadata.dependencies else 0}")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    """Run baseline tests on all test packages."""
    test_dir = Path("test-packages")
    extractor = PackageExtractor()
    
    test_cases = [
        ("requests-2.32.3-py3-none-any.whl", "python_wheel"),
        ("express-4.21.2.tgz", "npm"),
        ("guava-33.4.0-jre.jar", "maven"),
        ("rails-7.1.5.gem", "ruby_gem"),
        ("serde-1.0.210.crate", "rust_crate"),
        ("Newtonsoft.Json.13.0.3.nupkg", "nuget"),
        ("gin-v1.10.0.zip", "go_module"),
        ("cobra-v1.8.1.zip", "go_module"),
    ]
    
    results = []
    print("=" * 60)
    print("BASELINE TEST - Before Refactoring")
    print("=" * 60)
    
    for package_file, expected_type in test_cases:
        package_path = test_dir / package_file
        if package_path.exists():
            success = test_package(extractor, str(package_path), expected_type)
            results.append((package_file, success))
        else:
            print(f"\nSkipping {package_file} - not found")
            results.append((package_file, None))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    
    for package_file, result in results:
        status = "✓ PASS" if result is True else "✗ FAIL" if result is False else "- SKIP"
        print(f"{status}: {package_file}")
    
    print(f"\nTotal: {len(results)} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    
    # Save results for comparison after refactoring
    with open("baseline_results.json", "w") as f:
        json.dump({
            "results": [(p, r) for p, r in results],
            "summary": {"total": len(results), "passed": passed, "failed": failed, "skipped": skipped}
        }, f, indent=2)
    
    return failed == 0

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)