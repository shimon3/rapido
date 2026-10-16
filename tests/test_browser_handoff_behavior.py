"""Execute browser handoff behavior tests against the real background script."""
import shutil
import subprocess
from pathlib import Path


def test_browser_handoff_preserves_original_request():
    node = shutil.which("node")
    assert node, "Node.js is required for browser security behavior tests"
    script = Path(__file__).with_name("browser_handoff_behavior.cjs")
    try:
        result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as error:
        # Show which scenarios passed before the hang (CI run #212 timed out once).
        partial = [part.decode("utf-8", "replace") if isinstance(part, bytes) else (part or "")
                   for part in (error.stdout, error.stderr)]
        raise AssertionError("Node behavior test timed out; output so far:\n" + "".join(partial)) from None
    assert result.returncode == 0, result.stdout + result.stderr
