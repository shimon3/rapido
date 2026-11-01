"""Repeat the compiled graphical self-test; a PID alone never counts as success."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import time


def port_is_free():
    with socket.socket() as probe:
        if os.name == 'nt':
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(('127.0.0.1', 9614))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--count', type=int, default=20)
    args = parser.parse_args()
    if args.count < 1:
        parser.error('--count must be positive')
    image = args.exe.resolve(strict=True)
    args.work.mkdir(parents=True, exist_ok=False)
    report = {'platform': platform.platform(), 'requested': args.count,
              'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(), 'cycles': [], 'ok': False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    def save():
        args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    save()
    for number in range(1, args.count + 1):
        port_is_free()
        profile = args.work / str(number)
        profile.mkdir()
        (profile / 'settings.json').write_text(json.dumps({'monitor_clipboard': False,
            'show_complete_dialog': False, 'download_dir': str(profile / 'Downloads')}), encoding='utf-8')
        out = profile / 'selftest.json'
        start = time.monotonic()
        with (profile / 'console.log').open('wb') as log:
            process = subprocess.Popen([str(image), '--selftest', '--selftest-out', str(out)],
                env=dict(os.environ, RAPIDO_DATA=str(profile)), stdout=log, stderr=log)
            try:
                code = process.wait(timeout=180)
            except subprocess.TimeoutExpired:
                # Stop this exact owned process only; no global image-name kill.
                process.kill()
                process.wait(timeout=10)
                report['cycles'].append({'number': number, 'pid': process.pid,
                    'ok': False, 'timeout': True, 'forced_termination': True})
                save()
                return 1
        result = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
        required = ('ok', 'main_loaded', 'main_url_ok', 'main_rows_html',
                    'webview_auth', 'native_pipe', 'native_capture', 'native_handoff')
        row = {'number': number, 'pid': process.pid, 'exit_code': code,
               'seconds': round(time.monotonic() - start, 3), 'forced_termination': False,
               'selftest': result}
        try:
            port_is_free()
            row['port_released'] = True
        except OSError:
            row['port_released'] = False
        row['ok'] = bool(code == 0 and all(result.get(key) is True for key in required)
                         and result.get('main_title') == 'Rapido' and row['port_released'])
        report['cycles'].append(row)
        save()
        print(f"GUI cycle {number}/{args.count}: ok={row['ok']} seconds={row['seconds']}", flush=True)
        if not row['ok']:
            print(json.dumps(row, ensure_ascii=True), flush=True)
            return 1
    report['ok'] = hashlib.sha256(image.read_bytes()).hexdigest() == report['image_sha256']
    save()
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
