"""Shared best-effort link checks for native registration and admission.

These pathname checks do not establish file integrity or prevent path races.
"""
import os
from pathlib import Path


def has_linked_component(path):
    """Reject a symlink/junction at the leaf or any existing ancestor."""
    candidate = Path(os.path.abspath(path))
    for part in (candidate, *candidate.parents):
        if part.is_symlink() or (os.name == "nt" and part.is_junction()):
            return True
    return False
