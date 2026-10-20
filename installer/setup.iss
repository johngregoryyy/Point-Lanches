; Script de Instalador Inno Setup para Point Lanches
; =============================================================================

#define MyAppName "Point Lanches"
#define MyAppVersion "1.0.5"
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
Name: "{autoprograms}\Point Lanches"; Filename: "{app}\PointLanches.exe"; IconFilename: "{app}\assets\images.ico"
Name: "{autodesktop}\Point Lanches"; Filename: "{app}\PointLanches.exe"; IconFilename: "{app}\assets\images.ico"; Tasks: desktopicon

[InstallDelete]
; Limpar executável e pasta interna da versão antiga antes de instalar a nova
Type: files; Name: "{app}\PointLanches.exe"
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\*.bat"
Type: files; Name: "{app}\*temp*.exe"

[Code]
// Procedimento de limpeza profunda da versão anterior antes da instalação
// Preserva estritamente o banco de dados (point_lanches.db) e logs de desinstalação
procedure CurStepChanged(CurStep: TSetupStep);
var
  FindRec: TFindRec;
  AppDir, ItemPath, FileName, Ext: String;
begin
  if CurStep = ssInstall then
  begin
    AppDir := ExpandConstant('{app}');
    if DirExists(AppDir) then
    begin
      if FindFirst(AppDir + '\*', FindRec) then
      begin
        try
          repeat
            FileName := FindRec.Name;
            if (FileName <> '.') and (FileName <> '..') then
            begin
              Ext := Lowercase(ExtractFileExt(FileName));
              // Blindagem: NUNCA remover o banco de dados SQLite nem arquivos wal/shm
              if (Ext <> '.db') and (Ext <> '.db-wal') and (Ext <> '.db-shm') and (Pos('unins', Lowercase(FileName)) <> 1) then
              begin
                ItemPath := AppDir + '\' + FileName;
                if FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then
                  DelTree(ItemPath, True, True, True)
                else
                  DeleteFile(ItemPath);
              end;
            end;
          until not FindNext(FindRec);
        finally
          FindClose(FindRec);
        end;
      end;
    end;
  end;
end;

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
