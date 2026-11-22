#define MyAppName "KeyStow"
#define MyAppVersion "1.0.6"
#define MyAppPublisher "KeyStow"
#define MyAppExeName "KeyStow.exe"
; Passed by the sign-in entry so the app starts minimised (keystow/autostart.py).
#define StartupArgument "--startup"

[Setup]
AppId={{8F3A2B71-9C4E-4D2A-A5F1-KEYST0W00001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Per-user program folder. Existing installs keep their previous folder on
; upgrade (Inno Setup's UsePreviousAppDir default); only new installs move.
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableDirPage=yes
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=KeyStowSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=keystow.ico
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Registry]
; Start at sign-in is a Setup option, ticked by default. Setup remembers the
; choice on later updates. The app's own tray toggle writes the same value.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "KeyStow"; ValueData: """{app}\{#MyAppExeName}"" {#StartupArgument}"; Tasks: autostart

[InstallDelete]
; The app is installed as KeyStow.exe plus its _internal folder. Clear the old
; folder first so files a new version no longer ships cannot linger. Settings
; and word counts live in the user's .keystow folder and are not touched.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; Ordinary installed files. Versions up to 1.0.5 were one self-extracting file
; that unpacked about 500 MB into the temp folder at every start.
Source: "..\dist\KeyStow\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
Name: "autostart"; Description: "Start KeyStow when I sign in to Windows"; GroupDescription: "Startup:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch KeyStow"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
// The sign-in entry can be created by Setup or by the app's tray toggle, so
// uninstall removes it in both cases.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'KeyStow');
end;
