#define MyAppName "KeyStow"
#define MyAppVersion "1.0.3"
#define MyAppPublisher "KeyStow"
#define MyAppExeName "KeyStow.exe"

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
; Start at sign-in only when the user ticks the option below. The app's own
; tray toggle writes the same value, so Setup must not force it on upgrades.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "KeyStow"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
Name: "autostart"; Description: "Start KeyStow when I sign in to Windows"; GroupDescription: "Startup:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch KeyStow"; Flags: nowait postinstall skipifsilent

[Code]
// The sign-in entry can be created by Setup or by the app's tray toggle, so
// uninstall removes it in both cases.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'KeyStow');
end;
