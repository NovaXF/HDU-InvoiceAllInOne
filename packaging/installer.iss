#ifndef AppVersion
  #error AppVersion must be supplied by the release workflow
#endif

[Setup]
AppId={{C2B3C059-EBDA-409F-9200-FCD0BCD951D2}
AppName=HDU Invoice Workbench
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\HDU-InvoiceAllInOne
DefaultGroupName=HDU Invoice Workbench
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=HDU-InvoiceAllInOne-v{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\HDU-InvoiceAllInOne.exe

[Files]
Source: "..\dist\HDU-InvoiceAllInOne\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\HDU Invoice Workbench"; Filename: "{app}\HDU-InvoiceAllInOne.exe"

[Run]
Filename: "{app}\HDU-InvoiceAllInOne.exe"; Description: "Launch HDU Invoice Workbench"; Flags: nowait postinstall skipifsilent
