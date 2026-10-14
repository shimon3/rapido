"""Execute browser handoff behavior tests against the real background script."""
import shutil
import subprocess
from pathlib import Path


def test_browser_handoff_preserves_original_request():
    node = shutil.which("node")
    assert node, "Node.js is required for browser security behavior tests"
    script = Path(__file__).with_name("browser_handoff_behavior.cjs")
    result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
