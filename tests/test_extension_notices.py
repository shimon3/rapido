"""Execute the real content and popup scripts: refusal reasons and browser name."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("script", ["content_notice_behavior.cjs", "popup_browser_name.cjs"])
def test_extension_user_facing_texts(script):
    node = shutil.which("node")
    assert node, "Node.js is required for browser behavior tests"
    path = Path(__file__).with_name(script)
    result = subprocess.run([node, str(path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
