"""Run the test suite on a developer's own PC without touching their real data.

    python scripts/run_safe_local_tests.py [pytest arguments]

* HOME, USERPROFILE, APPDATA, LOCALAPPDATA, TEMP, TMP and RAPIDO_DATA point
  into a fresh folder under build/local-test-sandbox, so ~/.rapido, Downloads
  and temporary files of the real profile are never used.
* scripts/local_test_safety.py blocks in-process registry writes and deselects
  the tests listed in VM_ONLY. Run those only on a disposable Windows VM or CI.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sandbox_environment(base: Path) -> dict:
    home = base / "home"
    folders = {
        "HOME": home, "USERPROFILE": home,
        "APPDATA": home / "AppData" / "Roaming",
        "LOCALAPPDATA": home / "AppData" / "Local",
        "TEMP": base / "temp", "TMP": base / "temp",
        "RAPIDO_DATA": base / "rapido-data",
    }
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, **{key: str(value) for key, value in folders.items()})
    env["RAPIDO_LOCAL_SANDBOX"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT), env.get("PYTHONPATH")]))
    env.pop("RAPIDO_SIGNATURE_FIXTURES", None)
    return env


def interpreter(env: dict) -> str:
    # A Windows venv python.exe is a redirector that starts the base image, so
    # process-identity and pipe-peer tests would see a different executable.
    # Run the base image directly with the venv's packages on the path instead.
    if sys.prefix == sys.base_prefix:
        return sys.executable
    import site
    env["PYTHONPATH"] = os.pathsep.join([env["PYTHONPATH"], *site.getsitepackages()])
    # Some managed Pythons sit behind a linked folder; identity checks reject links.
    return os.path.realpath(getattr(sys, "_base_executable", sys.executable))


def main(argv):
    # The process id keeps two runs started in the same second apart.
    base = ROOT / "build" / "local-test-sandbox" / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    env = sandbox_environment(base)
    command = [interpreter(env), "-m", "pytest", "-p", "scripts.local_test_safety",
               "-p", "no:cacheprovider", *(argv or ["-q", "tests"])]
    print("sandbox:", base, flush=True)
    return subprocess.call(command, cwd=ROOT, env=env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
