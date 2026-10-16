"""Exercise shipped confirmation helpers and action handlers using Node."""
from pathlib import Path
import shutil
import subprocess


def test_dialog_refusal_and_destructive_action_behavior():
    node = shutil.which('node')
    assert node, 'Node.js is required for UI behavior checks'
    result = subprocess.run([node, str(Path(__file__).with_name('dialog_behavior.cjs'))],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
