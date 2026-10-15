"""Collect installed-distribution license evidence, not a compliance verdict.

This intentionally inventories the build environment, including build/test tools.
It does not claim every package is shipped or cover all bundled native binaries.
No package code is imported; URLs, absolute host paths and environment variables
are not exported. Unsafe metadata paths are recorded as problems, never copied.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path, PurePosixPath
import platform
import re
import sys

MAX_LICENSE_BYTES = 1024 * 1024
PROXY_TOOLS_MODULE_SHA256 = "d1539d95e1a713c068ca81d42e047b2c76568964cf277596d4e19efb22f476be"
PROXY_TOOLS_LICENSE_SHA256 = "a428fb8a2e762af3eb0a6edbbb88e9b42ccfee80fd9b423958bcacf9b9abbfe4"
PROXY_TOOLS_SOURCE = "https://github.com/jtushman/proxy_tools/blob/db43f1e35d4f90a65c5a4d56d9e9af88212ec6e6/LICENSE.txt"

WEBVIEW2_SDK_FILES = {'webview/lib/Microsoft.Web.WebView2.Core.dll': '8219a3135436c147f8eb02fb831e99596103eebc18b6d7b794ca93f4c67018a2',
 'webview/lib/Microsoft.Web.WebView2.WinForms.dll': 'c48f8d729dc531288d2c53a6241effe7922ed1b947850b2442008a945c098c48',
 'webview/lib/runtimes/win-arm64/native/WebView2Loader.dll': '0937030efc718f3da77c5e0978fb5046e381d0bb7b01acaad31a535a1b588a33',
 'webview/lib/runtimes/win-x64/native/WebView2Loader.dll': 'eb5335edeaa6f2122c044e82aab2351dc8c9b4e0fe5e578c71922fb61be285e7',
 'webview/lib/runtimes/win-x86/native/WebView2Loader.dll': '04814b2c59314c6452d61b821a4a3a5c5f8e8577b55b985f6a7a4b59f8907ec5'}
WEBVIEW2_SDK_TEXTS = {'LICENSE.txt': '0af8f1b807512aae39c2ac1aa4d0cae65cabecb6fd554b8439a5162a0d6eca55',
 'NOTICE.txt': '106423785c5b7eba0a8e61d1837f2132e9c828e20ad530f565d981c1df60dd90'}
WEBVIEW2_SDK_SOURCE = 'https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.3856.49/microsoft.web.webview2.1.0.3856.49.nupkg'


def _supplement_known_missing_text(dist, root, output, item):
    # The published 0.1.0 sdist omits LICENSE. Its module says BSD while its
    # packaging metadata says MIT. Preserve authentic upstream text and report
    # the discrepancy; do not invent an attribution or resolve the legal issue.
    if re.sub(r"[-_.]+", "-", item["name"]).lower() != "proxy-tools" or item["version"] != "0.1.0":
        return
    try:
        module = Path(dist.locate_file("proxy_tools/__init__.py"))
        module.resolve().relative_to(root)
        with module.open("rb") as stream:
            data = stream.read(MAX_LICENSE_BYTES + 1)
        if hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() != PROXY_TOOLS_MODULE_SHA256:
            raise ValueError("Different module identity")
        original = Path(__file__).resolve().parents[1] / "packaging/licenses/proxy_tools-0.1.0/LICENSE.txt"
        data = original.read_bytes()
        # A Windows checkout may convert line endings; preserve textual identity.
        data = data.replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != PROXY_TOOLS_LICENSE_SHA256:
            raise ValueError("Different supplemental license identity")
    except (OSError, ValueError):
        item["problems"].append("supplemental-license-identity-unverified")
        return
    target = "packages/proxy-tools/UPSTREAM-LICENSE.txt"
    destination = output / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    item["files"].append({"path": target, "sha256": hashlib.sha256(data).hexdigest(),
                          "source": PROXY_TOOLS_SOURCE,
                          "installed_module_sha256_lf": PROXY_TOOLS_MODULE_SHA256})
    item["problems"].append("upstream-BSD-text-supplemented-metadata-MIT-review-required")



def _supplement_webview2_sdk(dist, root, output, item):
    if re.sub(r"[-_.]+", "-", item["name"]).lower() != "pywebview":
        return
    try:
        if item["version"] != "6.2.1":
            raise ValueError("Unreviewed SDK carrier version")
        for relative, expected in WEBVIEW2_SDK_FILES.items():
            source = Path(dist.locate_file(relative))
            source.resolve().relative_to(root)
            with source.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ValueError("Different SDK file identity")
        originals = Path(__file__).resolve().parents[1] / "packaging/licenses/Microsoft.Web.WebView2-1.0.3856.49"
        texts = {}
        for name, expected in WEBVIEW2_SDK_TEXTS.items():
            data = (originals / name).read_bytes().replace(b"\r\n", b"\n")
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("Different SDK text identity")
            texts[name] = data
    except (OSError, ValueError):
        item["problems"].append("webview2-sdk-notice-identity-unverified")
        return
    for name, data in texts.items():
        target = "packages/pywebview/Microsoft.Web.WebView2-1.0.3856.49/" + name
        destination = output / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        item["files"].append({"path": target, "sha256": hashlib.sha256(data).hexdigest(),
                              "source": WEBVIEW2_SDK_SOURCE + "!/" + name,
                              "component": "Microsoft.Web.WebView2 1.0.3856.49"})
    item["supplemental_components"] = [{"name": "Microsoft.Web.WebView2", "version": "1.0.3856.49",
        "source": WEBVIEW2_SDK_SOURCE, "complete_legal_review": False,
        "matched_installed_files": [{"path": p, "sha256": h} for p, h in WEBVIEW2_SDK_FILES.items()]}]


def _license_path(record):
    parts = PurePosixPath(str(record).replace("\\", "/")).parts
    if not parts:
        return False
    name = parts[-1].lower()
    return (name.startswith(("license", "licence", "copying", "notice")) or
            "licenses" in (part.lower() for part in parts[:-1]))


def collect(output, *, distributions=None, python_license=None):
    output = Path(output)
    # Refuse to merge evidence with stale files from an earlier build.
    output.mkdir(parents=True, exist_ok=False)
    packages = []
    seen = set()
    distributions = metadata.distributions() if distributions is None else distributions
    for dist in sorted(distributions, key=lambda d: (d.metadata.get("Name", "").lower(), d.version)):
        name = dist.metadata.get("Name", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            raise ValueError("Invalid distribution name in license evidence")
        canonical = re.sub(r"[-_.]+", "-", name).lower()
        if canonical in seen:
            raise ValueError("Ambiguous duplicate distribution in build environment")
        seen.add(canonical)
        item = {"name": name, "version": dist.version,
                "license_expression": dist.metadata.get("License-Expression", ""),
                "license_metadata": dist.metadata.get("License", ""),
                "files": [], "problems": []}
        root = Path(dist.locate_file("")).resolve()
        for record in sorted(dist.files or [], key=str):
            if not _license_path(record):
                continue
            relative = PurePosixPath(str(record).replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts or any(":" in part for part in relative.parts):
                item["problems"].append("unsafe-license-path")
                continue
            try:
                source = Path(dist.locate_file(record))
                source.resolve().relative_to(root)
                with source.open("rb") as stream:
                    data = stream.read(MAX_LICENSE_BYTES + 1)
                if len(data) > MAX_LICENSE_BYTES:
                    item["problems"].append("oversized-license-file")
                    continue
            except (OSError, ValueError):
                item["problems"].append("unreadable-or-external-license-file")
                continue
            target = Path("packages", canonical, *relative.parts)
            destination = output / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            item["files"].append({"path": target.as_posix(),
                                  "sha256": hashlib.sha256(data).hexdigest()})
        if not item["files"]:
            _supplement_known_missing_text(dist, root, output, item)
        if not item["files"]:
            item["problems"].append("license-text-not-collected")
        _supplement_webview2_sdk(dist, root, output, item)
        packages.append(item)

    python_license = Path(python_license) if python_license is not None else Path(sys.base_prefix) / "LICENSE.txt"
    interpreter = {"version": platform.python_version(), "license_collected": False}
    try:
        data = python_license.read_bytes()
        if not data or len(data) > MAX_LICENSE_BYTES:
            raise ValueError("Invalid interpreter license size")
        (output / "Python-LICENSE.txt").write_bytes(data)
        interpreter.update(license_collected=True, path="Python-LICENSE.txt",
                           sha256=hashlib.sha256(data).hexdigest())
    except (OSError, ValueError):
        interpreter["problem"] = "python-license-not-collected"

    report = {"schema": 1, "scope": "installed-build-environment",
              "compliance_verified": False, "python": interpreter, "packages": packages}
    (output / "inventory.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "README.txt").write_text(
        "Third-party license evidence\n\n"
        "Scope: installed build environment, including build and test tools.\n"
        "inventory.json records versions, metadata, copied license texts and their SHA-256 hashes.\n"
        "It is not an exact inventory of shipped modules or a license compatibility verdict.\n"
        "Native libraries, runtimes, notices and redistribution obligations still require review.\n"
        "Missing license text or unsafe/unreadable metadata paths are reported, not silently treated as compliant.\n",
        encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = collect(args.output)
    print(f"License evidence collected for {len(report['packages'])} installed distributions; compliance review remains required.")
    if any("webview2-sdk-notice-identity-unverified" in p["problems"] for p in report["packages"]):
        raise SystemExit("WebView2 SDK notices unverified: review carrier/version/binary/text identity before building")
    if not report["python"]["license_collected"]:
        raise SystemExit("Python interpreter license missing: refusing an incomplete evidence bundle")


if __name__ == "__main__":
    main()
