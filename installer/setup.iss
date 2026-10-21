; Script de Instalador Inno Setup para Point Lanches
; =============================================================================

#define MyAppName "Point Lanches"
#define MyAppVersion "1.1.8"
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
DefaultDirName={commonpf}\{#MyAppName}
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
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no
SetupLogging=yes

[Dirs]
Name: "{app}"; Permissions: users-full

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Todos os arquivos da distribuição onedir gerada pelo PyInstaller (exclui explicitamente qualquer arquivo de banco SQLite)
Source: "dist\PointLanches\*"; DestDir: "{app}"; Excludes: "*.db,*.db-wal,*.db-shm"; Flags: ignoreversion recursesubdirs createallsubdirs
; Garantir a presença de todos os assets (ícone, loading gif, etc.) no diretório instalado
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Point Lanches"; Filename: "{app}\PointLanches.exe"; IconFilename: "{app}\assets\images.ico"; Check: NotPublicShortcutExists
Name: "{autodesktop}\Point Lanches"; Filename: "{app}\PointLanches.exe"; IconFilename: "{app}\assets\images.ico"; Tasks: desktopicon; Check: NotPublicDesktopExists

[InstallDelete]
; Limpar executável e pasta interna da versão antiga antes de instalar a nova
Type: files; Name: "{app}\PointLanches.exe"
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\*.bat"
Type: files; Name: "{app}\*temp*.exe"

[Code]
var
  BackupDbFile, BackupWalFile, BackupShmFile: String;

function GetFileSizeBytes(const FileName: String): Int64;
var
  Sz: Int64;
begin
  if FileSize64(FileName, Sz) then
    Result := Sz
  else
    Result := 0;
end;

procedure BackupDatabase;
var
  AppDir, LocalDataDir, SourceDbFile: String;
begin
  AppDir := ExpandConstant('{app}');
  LocalDataDir := ExpandConstant('{localappdata}\PointLanches\data');
  BackupDbFile := ExpandConstant('{tmp}\point_lanches_backup.db');
  BackupWalFile := ExpandConstant('{tmp}\point_lanches_backup.db-wal');
  BackupShmFile := ExpandConstant('{tmp}\point_lanches_backup.db-shm');

  // Localizar o banco de dados existente com dados válidos
  if FileExists(AppDir + '\point_lanches.db') and (GetFileSizeBytes(AppDir + '\point_lanches.db') > 0) then
    SourceDbFile := AppDir + '\point_lanches.db'
  else if FileExists(LocalDataDir + '\point_lanches.db') and (GetFileSizeBytes(LocalDataDir + '\point_lanches.db') > 0) then
    SourceDbFile := LocalDataDir + '\point_lanches.db'
  else if FileExists(ExpandConstant('{localappdata}\Point Lanches\point_lanches.db')) then
    SourceDbFile := ExpandConstant('{localappdata}\Point Lanches\point_lanches.db')
  else
    SourceDbFile := '';

  if SourceDbFile <> '' then
  begin
    CopyFile(SourceDbFile, BackupDbFile, False);
    CopyFile(SourceDbFile, ExpandConstant('{userappdata}\..\Local\Temp\point_lanches_safe_backup.db'), False);

    if FileExists(SourceDbFile + '-wal') then
      CopyFile(SourceDbFile + '-wal', BackupWalFile, False);
    if FileExists(SourceDbFile + '-shm') then
      CopyFile(SourceDbFile + '-shm', BackupShmFile, False);
  end;
end;

function NotPublicShortcutExists: Boolean;
begin
  // Evita atalhos duplicados no menu Iniciar se o atalho publico ja existir
  Result := not FileExists(ExpandConstant('{commonprograms}\Point Lanches.lnk'));
end;

function NotPublicDesktopExists: Boolean;
begin
  // Evita atalhos duplicados na Area de Trabalho se o atalho publico ja existir
  Result := not FileExists(ExpandConstant('{commondesktop}\Point Lanches.lnk'));
end;

procedure DeleteOldShortcuts;
begin
  // Remove atalhos antigos duplicados no Menu Iniciar e Desktop do usuario
  DeleteFile(ExpandConstant('{userdesktop}\Point Lanches.lnk'));
  DeleteFile(ExpandConstant('{userprograms}\Point Lanches.lnk'));
  DelTree(ExpandConstant('{userprograms}\Point Lanches'), True, True, True);
end;

procedure WipeAppDir;
var
  AppDir: String;
  FindRec: TFindRec;
  ItemPath, FileName: String;
begin
  AppDir := ExpandConstant('{app}');
  if DirExists(AppDir) then
  begin
    if FindFirst(AppDir + '\*', FindRec) then
    begin
      try
        repeat
          FileName := FindRec.Name;
          // Preserva apenas os arquivos de controle do uninstaller para integridade do Windows
          if (FileName <> '.') and (FileName <> '..') and (Pos('unins', Lowercase(FileName)) <> 1) then
          begin
            ItemPath := AppDir + '\' + FileName;
            if FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then
              DelTree(ItemPath, True, True, True)
            else
              DeleteFile(ItemPath);
          end;
        until not FindNext(FindRec);
      finally
        FindClose(FindRec);
      end;
    end;
  end;
end;

procedure RestoreDatabase;
var
  AppDir, LocalDataDir, SafeBackup: String;
begin
  SafeBackup := ExpandConstant('{userappdata}\..\Local\Temp\point_lanches_safe_backup.db');
  if (not FileExists(BackupDbFile)) or (GetFileSizeBytes(BackupDbFile) = 0) then
  begin
    if FileExists(SafeBackup) and (GetFileSizeBytes(SafeBackup) > 0) then
      BackupDbFile := SafeBackup;
  end;

  if FileExists(BackupDbFile) and (GetFileSizeBytes(BackupDbFile) > 0) then
  begin
    AppDir := ExpandConstant('{app}');
    LocalDataDir := ExpandConstant('{localappdata}\PointLanches\data');
    ForceDirectories(LocalDataDir);

    // 1. Substituir o banco na pasta da aplicação pelo banco do backup
    CopyFile(BackupDbFile, AppDir + '\point_lanches.db', False);
    if FileExists(BackupWalFile) then
      CopyFile(BackupWalFile, AppDir + '\point_lanches.db-wal', False);
    if FileExists(BackupShmFile) then
      CopyFile(BackupShmFile, AppDir + '\point_lanches.db-shm', False);

    // 2. Substituir o banco na pasta persistente LocalAppData
    CopyFile(BackupDbFile, LocalDataDir + '\point_lanches.db', False);
    if FileExists(BackupWalFile) then
      CopyFile(BackupWalFile, LocalDataDir + '\point_lanches.db-wal', False);
    if FileExists(BackupShmFile) then
      CopyFile(BackupShmFile, LocalDataDir + '\point_lanches.db-shm', False);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    // 1. Fazer backup do banco para pasta temporária
    BackupDatabase;
    // 2. Apagar atalhos antigos do Menu Iniciar e Desktop
    DeleteOldShortcuts;
    // 3. Limpar completamente os arquivos da versão anterior
    WipeAppDir;
  end
  else if CurStep = ssPostInstall then
  begin
    // 4. Restaurar o banco de dados do backup substituindo o padrão
    RestoreDatabase;
  end;
end;

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
