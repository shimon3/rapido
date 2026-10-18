; Rapido - installateur Windows (Inno Setup 6)
; Compile par GitHub Actions :  ISCC.exe /DAppVersion=1.0.0 packaging\rapido.iss

#ifndef AppVersion
  #define AppVersion "1.3.0-beta.1"
#endif
; Windows exige 4 entiers : voir rapido_version.dotted (beta N -> .N, finale -> .100)
#ifndef AppFileVersion
  #define AppFileVersion "1.3.0.1"
#endif
; Dossier du payload deja signe et verifie (la repetition CI en passe une copie).
#ifndef PayloadDir
  #define PayloadDir "..\dist\Rapido"
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
VersionInfoVersion={#AppFileVersion}
VersionInfoProductTextVersion={#AppVersion}
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
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs
; RapidoNativeHost.exe comes only from dist\Rapido, the signed and verified payload.

[Icons]
Name: "{group}\Rapido"; Filename: "{app}\Rapido.exe"
Name: "{group}\{cm:ChromeExt}"; Filename: "{app}\extension"
Name: "{group}\{cm:Uninstall}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Rapido"; Filename: "{app}\Rapido.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Rapido"; \
  ValueData: """{app}\Rapido.exe"" --tray"; Tasks: autostart

[Run]
Filename: "{app}\Rapido.exe"; Description: "{cm:LaunchProgram,Rapido}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\RapidoNativeHost.exe"; Parameters: "--unregister-native-hosts"; Flags: runhidden waituntilterminated; RunOnceId: "UnregisterNativeHosts"

[Code]
// Ferme Rapido s'il tourne (mise a jour par-dessus une version deja installee)
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
    if not Exec(ExpandConstant('{app}\RapidoNativeHost.exe'), '--register-native-hosts',
                '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
      RaiseException('Cannot register native bridge for Chrome, Edge and Firefox. Another Rapido installation may own it.');
end;

// Inno Setup Restart Manager handles files held by this installation.
// Do not terminate every process called Rapido.exe on the machine.

// Retire le demarrage automatique meme s'il a ete active depuis les Options de Rapido
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  CurrentRunValue: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Only remove the Run value if it still points to this installation.
    // A portable or newer installation may have taken ownership.
    if RegQueryStringValue(HKEY_CURRENT_USER,
         'Software\Microsoft\Windows\CurrentVersion\Run',
         'Rapido', CurrentRunValue) and
       (CompareText(CurrentRunValue,
         '"' + ExpandConstant('{app}\Rapido.exe') + '" --tray') = 0) then
      RegDeleteValue(HKEY_CURRENT_USER,
        'Software\Microsoft\Windows\CurrentVersion\Run', 'Rapido');
  end;
end;
