#define MyAppName "Murmur"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Murmur"
#define MyAppExeName "Murmur.exe"

[Setup]
AppId={{8F3A2B71-9C4E-4D2A-A5F1-MURMUR000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={userdownloads}\{#MyAppName}
DisableDirPage=yes
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=MurmurSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=murmur.ico
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Murmur"; ValueData: "\"{app}\{#MyAppExeName}\""; Flags: uninsdeletevalue

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Murmur"; Flags: nowait postinstall skipifsilent
