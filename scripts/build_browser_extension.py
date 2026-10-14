"""Build experimental browser-specific Rapido extension directories.

Chrome remains the source of truth. Edge/Firefox builds are development
artifacts only: native-host registration and S2 authentication are incomplete.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "extension"


def build(browser: str, destination: Path) -> None:
    if browser not in ("edge", "firefox"):
        raise ValueError("Unsupported browser")
    source = SOURCE.resolve()
    dest = destination.resolve()
    if dest == source or source in dest.parents or dest in source.parents:
        raise ValueError("Destination must be separate from extension source")
    if dest.exists():
        raise FileExistsError("Refusing to overwrite existing destination")
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != 3:
        raise ValueError("Expected Manifest V3 source")
    if browser == "edge":
        # The Chrome signing key is not an Edge store identity.
        manifest.pop("key", None)
    else:
        manifest.pop("key", None)
        manifest["background"] = {"scripts": ["background.js"]}
        manifest["browser_specific_settings"] = {
            "gecko": {"id": "rapido-capture@rapido.local"}
        }
    # Stage a complete validated manifest before creating the destination.
    serialized = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"\n    shutil.copytree(source, dest)\n    (dest / "manifest.json").write_text(serialized, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("browser", choices=("edge", "firefox"))
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    build(args.browser, args.destination)


if __name__ == "__main__":
    main()
