#define MyAppName "KeyStow"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "KeyStow"
#define MyAppExeName "KeyStow.exe"

[Setup]
AppId={{8F3A2B71-9C4E-4D2A-A5F1-KEYST0W00001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={%USERPROFILE}\Downloads\{#MyAppName}
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
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "KeyStow"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch KeyStow"; Flags: nowait postinstall skipifsilent
