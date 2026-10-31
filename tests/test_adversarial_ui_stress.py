"""
Adversarial UI Stress Test Suite for WebGL UI and Studio Controller (graph_3d.html)
Executes tests/verify_ui_adversarial.js via Node.js and asserts 100% pass rate.
"""

import os
import subprocess
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFY_SCRIPT = os.path.join(PROJECT_ROOT, "tests", "verify_ui_adversarial.js")


def test_adversarial_webgl_ui_and_studio_controller():
    """
    Runs the empirical headless adversarial test harness for graph_3d.html.
    Verifies:
      - DOM Architecture & 38 Studio DOM IDs
      - Event Propagation Stopping (e.stopPropagation isolation from WebGL)
      - 3D CSS Flip Card Transforms & GPU Compositing Isolation
      - StudioAPI Dual-Mode Offline Fallback & Edge Case Resilience (339 assertions)
    """
    assert os.path.exists(VERIFY_SCRIPT), f"Verification script missing at {VERIFY_SCRIPT}"

    result = subprocess.run(
        ["node", VERIFY_SCRIPT],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    assert result.returncode == 0, f"Adversarial UI test failed with exit code {result.returncode}:\n{result.stderr}\n{result.stdout}"
    assert "ALL 339/339 ADVERSARIAL ASSERTIONS PASSED WITH ZERO ERRORS" in result.stdout
