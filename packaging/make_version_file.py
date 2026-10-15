"""Genere le fichier de version Windows (proprietes > Details de Rapido.exe) pour PyInstaller."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rapido_version import VERSION, dotted, numeric  # noqa: E402

v = sys.argv[1] if len(sys.argv) > 1 else VERSION
t = numeric(v)
if t is None:
    raise SystemExit(f"Format de version inconnu : {v!r}")
print(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040C04B0', [
      StringStruct('CompanyName', 'Samuel Bentouza'),
      StringStruct('FileDescription', 'Rapido - gestionnaire de telechargement'),
      StringStruct('FileVersion', '{dotted(v)}'),
      StringStruct('InternalName', 'Rapido'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 Samuel Bentouza. MIT License.'),
      StringStruct('OriginalFilename', 'Rapido.exe'),
      StringStruct('ProductName', 'Rapido'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [0x040C, 1200])])
  ]
)""")
