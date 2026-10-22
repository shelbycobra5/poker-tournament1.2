#define MyAppName "MyPoker Tournament"
#define MyAppVersion "1.2.0"
#define MyAppExeName "MyPoker Tournament.exe"

[Setup]
AppId={{C8FA5BE9-7F1D-4C1B-9DA6-1F5E5F8C2B31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=MyPoker Tournament
DefaultDirName={localappdata}\Programs\MyPoker Tournament
DefaultGroupName=MyPoker Tournament
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=MyPokerTournament-Setup-{#MyAppVersion}
SetupIconFile=..\assets\MyPokerTournament.ico
WizardImageFile=..\assets\InstallerSidebar.bmp
WizardSmallImageFile=..\assets\InstallerSmall.bmp
UninstallDisplayIcon={app}\MyPokerTournament.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
CloseApplications=yes
RestartIfNeededByRun=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\MyPoker Tournament.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\User Manual.pdf"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\User Manual.docx"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Release Notes.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Long Gong.wav"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\One Minute.wav"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\MyPokerTournament.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\MyPokerTournament_Icon.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\MyPokerTournament_Banner.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\MyPoker Tournament"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\MyPokerTournament.ico"
Name: "{autoprograms}\User Manual (PDF)"; Filename: "{app}\User Manual.pdf"
Name: "{autodesktop}\MyPoker Tournament"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\MyPokerTournament.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch MyPoker Tournament"; Flags: nowait postinstall skipifsilent
