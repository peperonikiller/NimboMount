#define AppVersion "0.8.5"
[Setup]
AppId={{3CD4D2ED-8DD3-4B1F-9EC8-99E47CF45538}
AppName=NimboMount
AppVersion={#AppVersion}
AppPublisher=NimboMount
DefaultDirName={autopf}\NimboMount
DefaultGroupName=NimboMount
OutputDir=..\..\dist\installers
OutputBaseFilename=NimboMount-{#AppVersion}-windows-x64-setup
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\NimboMount.exe
SetupIconFile=..\..\nimbomount\assets\NimboMount.ico
WizardStyle=modern
CloseApplications=yes

[Files]
Source: "..\..\dist\NimboMount\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\..\build\windows-deps\winfsp-2.2.26286.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{autoprograms}\NimboMount"; Filename: "{app}\NimboMount.exe"
Name: "{autodesktop}\NimboMount"; Filename: "{app}\NimboMount.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\winfsp-2.2.26286.msi"" /qn /norestart"; StatusMsg: "Installing WinFsp filesystem driver..."; Flags: waituntilterminated; Check: not WinFspInstalled
Filename: "{app}\NimboMount.exe"; Description: "Launch NimboMount"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
function WinFspInstalled: Boolean;
begin
  { Both common 64-bit DLL install locations; do not downgrade existing installation. }
  Result := FileExists(ExpandConstant('{pf}\WinFsp\bin\winfsp-x64.dll')) or
    FileExists(ExpandConstant('{pf32}\WinFsp\bin\winfsp-x64.dll'));
end;
