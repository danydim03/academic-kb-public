#!/usr/bin/env python3
"""
Academic KB Voice Studio — Gemini Live & Talking Avatar E2E Test Runner
Executes 4-tier requirement-driven E2E tests and produces structured summary reports.
"""

import os
import sys
import argparse
import subprocess
import time
from typing import List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

VOICE_TEST_FILES = [
    "tests/voice/test_ws_handshake.py",
    "tests/voice/test_audio_routing.py",
    "tests/voice/test_grounding.py",
    "tests/voice/test_barge_in.py",
    "tests/voice/test_avatar_dom.py",
    "tests/voice/test_student_workflows.py",
]

TIER_FILTERS = {
    1: ["TestTier1"],
    2: ["TestTier2"],
    3: ["TestTier3"],
    4: ["TestTier4"],
}

TIER_DESCRIPTIONS = {
    1: "Tier 1: Feature Coverage (WebSocket Handshake, Audio Routing, Grounding, Barge-In, Avatar)",
    2: "Tier 2: Boundary & Corner Cases (Corrupted PCM, Disconnects, Zero Bytes, Missing Docs)",
    3: "Tier 3: Cross-Feature Combinations (Barge-In during Retrieval, Avatar Reset, Cyber Glow)",
    4: "Tier 4: Real-World Student Workflows (TLS 1.3 Handshake, Interruption, Follow-up, Zero Hallucination)",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run Academic KB Gemini Live Voice & Talking Avatar E2E Test Suite"
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
    return parser.parse_args()


def find_pytest_executable() -> List[str]:
    venv_pytest = os.path.join(PROJECT_ROOT, ".venv", "bin", "pytest")
    if os.path.exists(venv_pytest):
        return [venv_pytest]
    return [sys.executable, "-m", "pytest"]


def run_tests() -> int:
    args = parse_args()

    pytest_cmd = find_pytest_executable()
    cmd = list(pytest_cmd)

    # Add test targets
    if args.tier:
        filter_expr = " or ".join(TIER_FILTERS[args.tier])
        cmd.extend(["-k", filter_expr])
        tier_label = f"Tier {args.tier} ({TIER_DESCRIPTIONS[args.tier]})"
    else:
        tier_label = "All Tiers (Tiers 1-4 Complete Suite)"

    cmd.extend(VOICE_TEST_FILES)

    if args.verbose:
        cmd.append("-v")
    if args.fail_fast:
        cmd.append("-x")

    print("\n" + "=" * 84)
    print("🎙️  Academic KB Voice Studio — Gemini Live Voice & Talking Avatar E2E Runner")
    print("=" * 84)
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Scope:        {tier_label}")
    print(f"Command:      {' '.join(cmd)}")
    print("=" * 84 + "\n")

    start_time = time.time()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    elapsed = time.time() - start_time

    print("\n" + "-" * 84)
    if result.returncode == 0:
        print(f"✅ ALL TESTS PASSED in {elapsed:.2f}s")
    else:
        print(f"❌ TEST FAILURES DETECTED (exit code: {result.returncode}) in {elapsed:.2f}s")
    print("-" * 84 + "\n")

    return result.returncode


if __name__ == "__main__":
    sys.exit(run_tests())
