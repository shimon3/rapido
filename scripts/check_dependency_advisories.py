"""Check exact build-inventory versions against PyPI's version-specific JSON API.

This is a dated advisory snapshot, not native-library coverage, a complete
security review, a license verdict, or proof of package authenticity.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request


def canonical(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name):
        raise ValueError('Invalid distribution name')
    return re.sub(r'[-_.]+', '-', name).lower()


def read_pins(path):
    pins = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)', line)
        if not match:
            raise ValueError('Build constraints must contain exact versions only')
        name, version = match.groups()
        key = canonical(name)
        if key in pins:
            raise ValueError('Duplicate build constraint')
        pins[key] = version
    if not pins:
        raise ValueError('Empty build constraints')
    return pins


def inventory_packages(inventory):
    if not isinstance(inventory.get('packages'), list) or not inventory['packages']:
        raise ValueError('Empty or invalid build inventory')
    result = {}
    for item in inventory['packages']:
        name, version = item['name'], item['version']
        key = canonical(name)
        if key in result or not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.!+_-]*', version):
            raise ValueError('Invalid or duplicate inventory identity')
        result[key] = {'name': name, 'version': version}
    return result


def pin_problems(packages, pins):
    issues = []
    for key in sorted(packages.keys() | pins.keys()):
        if key not in packages:
            issues.append({'name': key, 'problem': 'reviewed-package-missing'})
        elif key not in pins:
            issues.append({'name': key, 'problem': 'unreviewed-package-installed'})
        elif packages[key]['version'] != pins[key]:
            issues.append({'name': key, 'problem': 'different-installed-version'})
    return issues


def fetch_metadata(url):
    # Fixed PyPI host; no package code, environment values or credentials sent.
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(request, timeout=10) as response:
                origin = urllib.parse.urlsplit(response.geturl())
                if origin.scheme != 'https' or origin.netloc != 'pypi.org':
                    raise ValueError('Unexpected metadata response origin')
                data = response.read(3 * 1024 * 1024 + 1)
            if len(data) > 3 * 1024 * 1024:
                raise ValueError('Oversized metadata response')
            return json.loads(data)
        except OSError:
            if attempt:
                raise


def check_package(package, fetch=fetch_metadata):
    name, version = package['name'], package['version']
    url = 'https://pypi.org/pypi/' + canonical(name) + '/' + urllib.parse.quote(version, safe='') + '/json'
    item = {**package, 'source': url, 'status': 'unverified'}
    try:
        data = fetch(url)
        info = data['info']
        if canonical(info['name']) != canonical(name) or info['version'] != version:
            raise ValueError('Metadata identity mismatch')
        advisories, files = data['vulnerabilities'], data['urls']
        if not isinstance(advisories, list) or not isinstance(files, list) or not files or type(info['yanked']) is not bool:
            raise ValueError('Missing or invalid advisory/release fields')
        active = []
        for advisory in advisories:
            if not isinstance(advisory, dict) or not isinstance(advisory.get('id'), str) or not advisory['id']:
                raise ValueError('Invalid advisory identity')
            withdrawn = advisory.get('withdrawn')
            if withdrawn is not None:
                if not isinstance(withdrawn, str):
                    raise ValueError('Invalid withdrawal timestamp')
                stamp = datetime.fromisoformat(withdrawn.replace('Z', '+00:00'))
                if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
                    raise ValueError('Unverified withdrawal timestamp')
            else:
                active.append(advisory['id'])
        for record in files:
            if type(record.get('yanked')) is not bool:
                raise ValueError('Missing file withdrawal field')
        item.update(status='queried', active_advisory_ids=active, advisories=advisories,
                    release_yanked=info['yanked'], any_release_file_yanked=any(f['yanked'] for f in files),
                    release_file_count=len(files), last_serial=data.get('last_serial'))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        item['error_type'] = type(error).__name__
    return item


def audit(inventory, pins, *, fetch=fetch_metadata):
    packages = inventory_packages(inventory)
    problems = pin_problems(packages, pins)
    results = []
    # Unknown names/versions must be reviewed locally before querying a registry.
    if not problems:
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(lambda p: check_package(p, fetch), packages.values()))
    blocked = problems or any(p['status'] != 'queried' or p['active_advisory_ids'] or
                              p['release_yanked'] or p['any_release_file_yanked'] for p in results)
    return {'schema': 1, 'scope': 'PyPI-version-specific-advisories-for-installed-build-environment',
            'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'gate_passed': not bool(blocked),
            'complete_security_review': False, 'compliance_verified': False,
            'pin_problems': problems, 'packages': results,
            'limitations': ['Empty advisory lists are not proof of absence of vulnerabilities.',
                            'Native/embedded libraries and later browser-smoke dependencies require separate review.',
                            'Exact versions are checked; this is not hash-locked installation or byte reproducibility.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--constraints', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.inventory.read_text(encoding='utf-8')), read_pins(args.constraints))
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    verified = sum(p['status'] == 'queried' for p in report['packages'])
    print(f"PyPI advisory gate: {verified}/{len(report['packages'])} responses verified; passed={report['gate_passed']}; full review remains required.")
    if not report['gate_passed']:
        raise SystemExit('Dependency versions/advisory availability/withdrawals require review; build stopped')


if __name__ == '__main__':
    main()
