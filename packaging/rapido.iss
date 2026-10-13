; Rapido - installateur Windows (Inno Setup 6)
; Compile par GitHub Actions :  ISCC.exe /DAppVersion=1.0.0 packaging\rapido.iss

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8F3B2A61-4C7E-4D5B-9A2E-6B1C0D7E5F42}
AppName=Rapido
AppVersion={#AppVersion}
AppVerName=Rapido {#AppVersion}
AppPublisher=Samuel Bentouza
AppPublisherURL=https://github.com/shimon3/rapido
AppSupportURL=https://github.com/shimon3/rapido/issues
AppUpdatesURL=https://github.com/shimon3/rapido/releases
; installation pour l'utilisateur courant : pas besoin de droits administrateur
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Rapido
DefaultGroupName=Rapido
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=..\dist
OutputBaseFilename=Rapido-Setup-{#AppVersion}
SetupIconFile=rapido.ico
UninstallDisplayIcon={app}\Rapido.exe
UninstallDisplayName=Rapido
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Installation de Rapido
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "he"; MessagesFile: "compiler:Languages\Hebrew.isl"

[CustomMessages]
fr.AutoStart=Lancer Rapido au démarrage de Windows
en.AutoStart=Start Rapido when Windows starts
he.AutoStart=הפעל את Rapido עם הפעלת Windows
fr.Options=Options :
en.Options=Options:
he.Options=אפשרויות:
fr.Uninstall=Désinstaller Rapido
en.Uninstall=Uninstall Rapido
he.Uninstall=הסר את Rapido
fr.ChromeExt=Extension Chrome de Rapido (dossier)
en.ChromeExt=Rapido Chrome extension (folder)
he.ChromeExt=תוסף Chrome של Rapido (תיקייה)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "{cm:AutoStart}"; GroupDescription: "{cm:Options}"

[Files]
Source: "..\dist\Rapido\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Rapido"; Filename: "{app}\Rapido.exe"
Name: "{group}\{cm:ChromeExt}"; Filename: "{app}\extension"
Name: "{group}\{cm:Uninstall}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Rapido"; Filename: "{app}\Rapido.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Rapido"; \
  ValueData: """{app}\Rapido.exe"" --tray"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\Rapido.exe"; Description: "{cm:LaunchProgram,Rapido}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im Rapido.exe"; Flags: runhidden; RunOnceId: "StopRapido"

[Code]
// Ferme Rapido s'il tourne (mise a jour par-dessus une version deja installee)
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im Rapido.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(500);
  Result := '';
end;

// Retire le demarrage automatique meme s'il a ete active depuis les Options de Rapido
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Rapido');
end;
