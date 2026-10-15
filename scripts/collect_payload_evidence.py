"""Inspect locally built PyInstaller payloads without executing their code.

Build-time review evidence only, never an admission policy or a compliance verdict.
Python ownership candidates come from exact module names in installed RECORDs;
only native ownership candidates are matched by file size and SHA-256. Unmatched
and ambiguous entries remain visible. All output paths are bundle-relative.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import io
from importlib import metadata
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

NATIVE_SUFFIXES = {'.dll', '.pyd', '.exe', '.so', '.dylib'}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_relative(name):
    name = str(name).replace('\\', '/')
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or '..' in path.parts or any(':' in p for p in path.parts):
        raise ValueError('Non-relative payload or metadata path')
    return path.as_posix()


def module_name(record):
    path = PurePosixPath(record)
    if path.suffix.lower() not in {'.py', '.pyc', '.pyd', '.so'}:
        return None
    parts = list(path.parts)
    if '__pycache__' in parts:
        return None
    parts[-1] = parts[-1].split('.')[0]
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts) if parts and all(p.isidentifier() for p in parts) else None


def distribution_index(distributions):
    modules = defaultdict(set)
    native = defaultdict(list)
    packages = []
    seen = set()
    for dist in sorted(distributions, key=lambda d: d.metadata.get('Name', '').lower()):
        name = dist.metadata.get('Name', '')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name):
            raise ValueError('Invalid distribution name')
        canonical = re.sub(r'[-_.]+', '-', name).lower()
        if canonical in seen:
            raise ValueError('Ambiguous distribution identity')
        seen.add(canonical)
        item = {'name': name, 'version': dist.version, 'problems': []}
        packages.append(item)
        root = Path(dist.locate_file('')).resolve()
        for record in dist.files or []:
            try:
                relative = safe_relative(record)
                source = Path(dist.locate_file(record))
                source.resolve().relative_to(root)
            except ValueError:
                item['problems'].append('external-or-unsafe-record')
                continue
            module = module_name(relative)
            if module:
                modules[module].add(name)
            if source.suffix.lower() in NATIVE_SUFFIXES:
                try:
                    native[source.stat().st_size].append((source, name))
                except OSError:
                    item['problems'].append('unreadable-native-record')
        item['problems'] = sorted(set(item['problems']))
    return modules, native, packages


def collect(bundle, *, distributions=None, archive_factory=None):
    if archive_factory is None:
        # PyInstaller is a build dependency, not a runtime dependency.
        from PyInstaller.archive.readers import CArchiveReader
        archive_factory = CArchiveReader
    bundle = Path(bundle).resolve()
    for executable in ('Rapido.exe', 'RapidoNativeHost.exe'):
        if not (bundle / executable).is_file():
            raise ValueError('Both built Rapido executables are required')
    distributions = metadata.distributions() if distributions is None else distributions
    modules, native, packages = distribution_index(distributions)
    native_hash_cache = {}

    def native_candidates(size, sha):
        matches = set()
        for source, name in native.get(size, []):
            if source not in native_hash_cache:
                native_hash_cache[source] = digest(source)
            if native_hash_cache[source] == sha:
                matches.add(name)
        return sorted(matches)

    def module_entry(name):
        return {'name': name, 'distribution_candidates_by_record_name': sorted(modules.get(name, []))}

    files, archives = [], []
    for path in sorted(bundle.rglob('*')):
        # Evidence is generated separately; do not recursively inventory itself.
        relative = path.relative_to(bundle).as_posix()
        if PurePosixPath(relative).parts[0] == 'third-party':
            continue
        path.resolve().relative_to(bundle)  # Reject external links, even for directories.
        if path.is_symlink():
            raise ValueError('Symlinks are not supported in payload evidence')
        if not path.is_file():
            continue
        item = {'path': relative, 'size': path.stat().st_size, 'sha256': digest(path)}
        if path.suffix.lower() in NATIVE_SUFFIXES:
            item['native_distribution_candidates_by_sha256'] = native_candidates(item['size'], item['sha256'])
        files.append(item)
        if path.name == 'base_library.zip':
            with zipfile.ZipFile(path) as archive:
                archives.append({'path': relative, 'format': 'stdlib-zip',
                                 'modules': [module_entry(m) for n in sorted(archive.namelist())
                                             if (m := module_name(safe_relative(n)))],
                                 'embedded_native': []})

    for executable in ('Rapido.exe', 'RapidoNativeHost.exe'):
        archive = archive_factory(str(bundle / executable))
        item = {'path': executable, 'format': 'PyInstaller-CArchive', 'modules': [], 'embedded_native': []}
        pyz_count = 0
        for original_name, entry in sorted(archive.toc.items()):
            name = safe_relative(original_name)
            _, _, size, _, typecode = entry
            if typecode == 'z':
                pyz_count += 1
                pyz = archive.open_embedded_archive(original_name)
                item['modules'].extend(module_entry(m) for m in sorted(pyz.toc))
            elif typecode in {'m', 'M', 's'}:
                item['modules'].append(module_entry(name))
            elif typecode in {'x', 'b'} and PurePosixPath(name).name == 'base_library.zip':
                if size > 32 * 1024 * 1024:
                    raise ValueError('Unexpected embedded standard library size')
                data = archive.extract(original_name)
                if len(data) != size:
                    raise ValueError('Embedded standard library size mismatch')
                with zipfile.ZipFile(io.BytesIO(data)) as standard_library:
                    archives.append({'path': executable + '!/' + name, 'format': 'stdlib-zip',
                        'modules': [module_entry(m) for n in sorted(standard_library.namelist())
                                    if (m := module_name(safe_relative(n)))], 'embedded_native': []})
            elif typecode == 'b':
                # Read bytes only: do not load DLLs or unmarshal module code.
                if size > 128 * 1024 * 1024:
                    raise ValueError('Unexpected embedded native size')
                data = archive.extract(original_name)
                if len(data) != size:
                    raise ValueError('Embedded native size mismatch')
                sha = hashlib.sha256(data).hexdigest()
                item['embedded_native'].append({'path': name, 'size': size, 'sha256': sha,
                    'native_distribution_candidates_by_sha256': native_candidates(size, sha)})
        if not pyz_count:
            raise ValueError('Expected an embedded Python archive in each executable')
        archives.append(item)
    return {'schema': 1, 'scope': 'built-payload-excluding-third-party-evidence',
            'compliance_verified': False, 'runtime_integrity_policy': False,
            'limitations': [
                'Module candidates match installed RECORD names, not compiled code identity.',
                'Native candidates match installed bytes; bundled DLLs may contain other libraries.',
                'Unmatched or ambiguous entries require review, including Python and system runtimes.',
                'No execution, behavioral coverage, installer bootstrap or license compatibility verdict.',
            ], 'distributions': packages, 'files': files, 'archives': archives}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    report = collect(args.bundle)
    target = args.bundle / 'third-party/payload.json'
    # Existing output would hide a stale or duplicated build step.
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(f"Payload evidence: {len(report['files'])} files, {len(report['archives'])} archives; compliance review remains required.")


if __name__ == '__main__':
    main()
