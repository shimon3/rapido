"""Fail the Windows build if its reviewed interpreter/TLS baseline differs."""
import json
import re
import ssl
import sys

PYTHON_VERSION = (3, 13, 16)
MIN_OPENSSL = (3, 5, 9)


def verify_runtime(python_version, openssl_version):
    if tuple(python_version[:3]) != PYTHON_VERSION:
        raise RuntimeError('Unexpected Python baseline')
    # OPENSSL_VERSION_INFO retains legacy packed-number fields: for OpenSSL 3
    # its first three fields do not represent (major, minor, patch).
    match = re.fullmatch(r'OpenSSL (\d+)\.(\d+)\.(\d+) \d{1,2} [A-Za-z]{3} \d{4}', openssl_version)
    if not match or tuple(map(int, match.groups())) < MIN_OPENSSL:
        raise RuntimeError('Unexpected or outdated OpenSSL baseline')


def main():
    print(json.dumps({'python': sys.version.split()[0], 'openssl': ssl.OPENSSL_VERSION}))
    verify_runtime(sys.version_info, ssl.OPENSSL_VERSION)


if __name__ == '__main__':
    main()
