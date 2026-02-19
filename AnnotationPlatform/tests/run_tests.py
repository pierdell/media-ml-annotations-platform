#!/usr/bin/env python3
"""
Test runner for the Index Factory platform.

Usage:
    python tests/run_tests.py              # Run all tests
    python tests/run_tests.py -v           # Verbose output
    python tests/run_tests.py -k auth      # Run tests matching 'auth'
"""

import sys
import os
import unittest

# Ensure correct paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'backend'))

# Import mock deps BEFORE any app code
import tests.mock_deps  # noqa: E402, F401


def run_all_tests():
    """Discover and run all tests."""
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=os.path.join(ROOT_DIR, 'tests'),
        pattern='test_*.py',
    )

    verbosity = 2 if '-v' in sys.argv else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return result


if __name__ == '__main__':
    result = run_all_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
