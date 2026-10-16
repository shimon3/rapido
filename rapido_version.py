"""Version unique de Rapido et sa forme numerique (Windows, extension, mises a jour).

Formats acceptes : "X.Y.Z" (finale) ou "X.Y.Z-beta.N" (N de 1 a 99).
Forme numerique a 4 entiers : beta N -> (X, Y, Z, N), finale -> (X, Y, Z, 100),
pour qu'une finale soit toujours plus recente que ses betas.
"""
import re

VERSION = "1.3.0-beta.1"

FINAL_BUILD = 100
_PATTERN = re.compile(r"v?(\d{1,5})\.(\d{1,5})\.(\d{1,5})(?:-beta\.([1-9]\d?))?")


def numeric(value: str):
    """Tuple a 4 entiers comparable, ou None si le format est inconnu."""
    match = _PATTERN.fullmatch(value)
    if not match:
        return None
    major, minor, patch, beta = match.groups()
    return (int(major), int(minor), int(patch), int(beta) if beta else FINAL_BUILD)


def is_prerelease(value: str) -> bool:
    match = _PATTERN.fullmatch(value)
    return bool(match and match.group(4))


def dotted(value: str) -> str:
    """"1.3.0-beta.1" -> "1.3.0.1" ; leve ValueError si le format est inconnu."""
    parts = numeric(value)
    if parts is None:
        raise ValueError("Format de version inconnu")
    return ".".join(map(str, parts))
