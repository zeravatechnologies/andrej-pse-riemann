#define AppName "PSE Riemann"
[Setup]
AppId={{6eec0400-73b4-4e1d-858e-1e66b642c3e2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Andrej Ristic
AppPublisherURL=https://github.com/zeravatechnologies/andrej-pse-riemann
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile={#SourceDir}\LICENSE.txt
OutputDir={#OutDir}
OutputBaseFilename=PSERiemann-Setup-{#AppVersion}
SetupIconFile={#SourceDir}\pse-riemann.ico
UninstallDisplayIcon={app}\pse-riemann.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\pse-riemann.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\pse-riemann.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\pse-riemann.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
