#!/usr/bin/env python3
"""
Academic KB Intelligent Study Engine — E2E Test Suite Runner
Executes 4-tier requirement-driven E2E tests and produces structured summary reports.
"""

import os
import sys
import argparse
import subprocess
import time
from typing import List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TIER_FILES = {
    1: "tests/test_e2e_tier1_features.py",
    2: "tests/test_e2e_tier2_boundaries.py",
    3: "tests/test_e2e_tier3_combinations.py",
    4: "tests/test_e2e_tier4_scenarios.py",
}

TIER_NAMES = {
    1: "Tier 1: Feature Coverage (>=5 tests per feature)",
    2: "Tier 2: Boundary & Corner Cases (>=5 tests per feature)",
    3: "Tier 3: Cross-Feature Combinations & Pipelines",
    4: "Tier 4: Real-World Application Scenarios",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run Academic KB Intelligent Study Engine E2E Test Suite"
    )
    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        help="Run only the specified tier (1, 2, 3, or 4). Default: all tiers.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose test output.",
    )
    parser.add_argument(
        "-x", "--fail-fast",
        action="store_true",
        help="Stop execution on the first failure.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        default=True,
        help="Force offline mock provider (LLM_PROVIDER=mock). Default: True.",
    )
    return parser.parse_args()


def run_tests():
    args = parse_args()
    
    # Configure offline environment
    env = os.environ.copy()
    if args.offline:
        env["LLM_PROVIDER"] = "mock"
        env["EMBEDDING_PROVIDER"] = "mock"

    target_files = []
    if args.tier:
        target_files.append(TIER_FILES[args.tier])
    else:
        target_files.extend(TIER_FILES.values())

    pytest_bin = os.path.join(PROJECT_ROOT, ".venv", "bin", "pytest")
    if not os.path.exists(pytest_bin):
        # Fallback to python3 -m pytest
        pytest_cmd = [sys.executable, "-m", "pytest"]
    else:
        pytest_cmd = [pytest_bin]

    cmd = pytest_cmd + target_files
    if args.verbose:
        cmd.append("-v")
    if args.fail_fast:
        cmd.append("-x")

    print("\n" + "=" * 80)
    print("🎓 Academic KB Intelligent Study Engine — E2E Test Runner")
    print("=" * 80)
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Target Tiers: {f'Tier {args.tier}' if args.tier else 'All (Tiers 1-4)'}")
    print(f"LLM Provider: {env.get('LLM_PROVIDER', 'mock')}")
    print(f"Command:      {' '.join(cmd)}")
    print("=" * 80 + "\n")

    start_time = time.time()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print(f"🏁 Test Execution Completed in {elapsed:.2f} seconds")
    print(f"Exit Code: {result.returncode} ({'SUCCESS' if result.returncode == 0 else 'FAILURE'})")
    print("=" * 80 + "\n")

    sys.exit(result.returncode)


if __name__ == "__main__":
    run_tests()
