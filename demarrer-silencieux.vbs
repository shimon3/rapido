' Lance Rapido en arriere-plan, sans fenetre noire.
' Pour un demarrage automatique avec Windows : Win+R -> shell:startup
' puis colle un raccourci vers ce fichier dans le dossier qui s'ouvre.
' (Lance demarrer.bat une premiere fois avant, pour installer les dependances.)
Set fso = CreateObject("Scripting.FileSystemObject")
dossier = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = dossier
shell.Run """" & dossier & "\.venv\Scripts\pythonw.exe"" app.py", 0, False
