; Script de Instalador Inno Setup para Point Lanches
; =============================================================================

#define MyAppName "Point Lanches"
#define MyAppVersion "1.0.2"
#define MyAppPublisher "Point Lanches"
#define MyAppURL "https://github.com/johngregoryyy/Point-Lanches"
#define MyAppExeName "PointLanches.exe"

[Setup]
; Identificador exclusivo da aplicação
AppId={{8F12D783-A845-4DC3-810C-5D62B72E31F4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
SourceDir=..
OutputDir=dist
OutputBaseFilename=PointLanches-Setup-v{#MyAppVersion}
SetupIconFile=assets\images.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Dirs]
Name: "{app}"; Permissions: users-full

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Todos os arquivos da distribuição onedir gerada pelo PyInstaller
Source: "dist\PointLanches\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Garantir a presença do ícone no diretório instalado
Source: "assets\images.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Point Lanches"; Filename: "{app}\PointLanches.exe"; IconFilename: "{app}\assets\images.ico"
Name: "{autodesktop}\Point Lanches"; Filename: "{app}\PointLanches.exe"; IconFilename: "{app}\assets\images.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
