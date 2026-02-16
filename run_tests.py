#!/usr/bin/env python3
"""
Test runner script for Talk2Data application.

Run this script to execute all tests and verify:
- All requirements are installed
- LLM connection is working
- Database is correctly loaded
- End-to-end functionality works
"""

import sys
from pathlib import Path

import pytest

if __name__ == "__main__":
    # Get project root
    project_root = Path(__file__).parent
    
    print("=" * 70)
    print("Talk2Data Test Suite")
    print("=" * 70)
    print("\nRunning comprehensive tests...")
    print("This will verify:")
    print("  1. All requirements are installed")
    print("  2. LLM (Gemini) connection is established")
    print("  3. Database is correctly loaded")
    print("  4. End-to-end functionality\n")
    print("-" * 70)
    
    # Run pytest with verbose output
    exit_code = pytest.main([
        str(project_root / "test_talk2data.py"),
        "-v",
        "--tb=short",
        "--color=yes",
    ])
    
    print("\n" + "=" * 70)
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ Some tests failed (exit code: {exit_code})")
    print("=" * 70)
    
    sys.exit(exit_code)
