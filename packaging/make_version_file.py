"""Genere le fichier de version Windows (proprietes > Details de Rapido.exe) pour PyInstaller."""
import sys

v = sys.argv[1] if len(sys.argv) > 1 else "1.0.0"
parts = [int(x) for x in v.split(".")] + [0] * 4
t = tuple(parts[:4])
print(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040C04B0', [
      StringStruct('CompanyName', 'Samuel Bentouza'),
      StringStruct('FileDescription', 'Rapido - gestionnaire de telechargement'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'Rapido'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', 'Rapido.exe'),
      StringStruct('ProductName', 'Rapido'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [0x040C, 1200])])
  ]
)""")
