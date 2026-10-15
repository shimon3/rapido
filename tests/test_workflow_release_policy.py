"""Ensure PR, main and manual test runs cannot enter the release job."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/windows.yml"


class ReleaseWorkflowTests(unittest.TestCase):
    def test_write_permission_and_publishing_action_are_separate_from_build(self):
        source = WORKFLOW.read_text()
        build, release = source.split("\n  release:\n", 1)
        self.assertNotIn("contents: write", build)
        self.assertNotIn("action-gh-release", build)
        self.assertIn("contents: read", build)
        self.assertIn("needs: build", release)
        self.assertIn("if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') && needs.build.outputs.release == 'true'", release)
        self.assertIn("contents: write", release)
        self.assertIn("actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093", release)
        self.assertNotIn("steps.ver.outputs", release)

    @unittest.skipUnless(shutil.which("bash"), "Workflow predicate uses bash")
    def test_actual_release_request_predicate_rejects_nonpublishing_events(self):
        source = WORKFLOW.read_text()
        # Execute the workflow's actual output decision, without version read,
        # downloads, API calls or any publishing action.
        block = re.search(r'          if \[\[ "\$GITHUB_EVENT_NAME".*?          fi', source, re.S)
        self.assertIsNotNone(block)
        script = "\n".join(line[10:] for line in block.group(0).splitlines())
        cases = [("pull_request", "refs/pull/32/merge", False),
                 ("pull_request", "refs/tags/v1.2.2", False),
                 ("workflow_dispatch", "refs/tags/v1.2.2", False),
                 ("workflow_dispatch", "refs/heads/main", False),
                 ("push", "refs/heads/main", False),
                 ("push", "refs/heads/work/security-26-followup-20261015", False),
                 ("push", "refs/tags/test", False),
                 ("push", "refs/tags/v1.2.2", True)]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            for event, ref, expected in cases:
                with self.subTest(event=event, ref=ref):
                    output.write_text("")
                    # Forward slashes work in both Windows Git Bash and Linux.
                    env = dict(os.environ, GITHUB_EVENT_NAME=event, GITHUB_REF=ref,
                               GITHUB_OUTPUT=output.as_posix())
                    subprocess.run([shutil.which("bash"), "--noprofile", "--norc", "-e", "-c", script],
                                   env=env, capture_output=True, check=True, timeout=10)
                    self.assertEqual(output.read_text().strip(), "release=" + str(expected).lower())
