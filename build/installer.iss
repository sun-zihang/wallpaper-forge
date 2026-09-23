; Inno Setup script for Wallpaper Converter
; Build: iscc build\installer.iss

#define MyAppName "Wallpaper Converter"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "wallpaper-forge"
#define MyAppURL "https://github.com/sun-zihang/wallpaper-forge"
#define MyAppExeName "WallpaperConverter.exe"

[Setup]
AppId={{8F3A2C1E-5B47-4D9A-9C21-WALLPAPERFORGE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\WallpaperConverter
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=..\build\Output
OutputBaseFilename=WallpaperConverter-Setup-{#MyAppVersion}
SetupIconFile=..\assets\app.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\WallpaperConverter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName}"; Flags: nowait postinstall skipifsilent
