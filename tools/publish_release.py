#!/usr/bin/env python3
# tools/publish_release.py - Script de Publicação Automatizada de Releases no GitHub
# =============================================================================

import os
import sys
import re
import shutil
import zipfile
import argparse
import subprocess
import urllib.request
import urllib.error
import json
from datetime import datetime

# Adicionar pasta raiz ao sys.path para importar config e version
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import GITHUB_OWNER, GITHUB_REPO
from version import __version__ as CURRENT_VERSION


try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ── Gerenciador de Logs (TeeLogger: exibe no terminal e grava em publicar.log) ──

class TeeLogger:
    """Duplica toda saída do terminal para um arquivo publicar.log para diagnóstico."""
    def __init__(self, filename="publicar.log"):
        self.terminal = sys.stdout
        try:
            self.log_file = open(os.path.join(BASE_DIR, filename), "a", encoding="utf-8", errors="replace")
            self.log_file.write(f"\n--- Sessao iniciada em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ---\n")
        except Exception:
            self.log_file = None

    def write(self, message):
        try:
            self.terminal.write(message)
        except UnicodeEncodeError:
            clean = message.encode("ascii", errors="replace").decode("ascii")
            self.terminal.write(clean)
        except Exception:
            pass

        if self.log_file:
            try:
                self.log_file.write(message)
                self.log_file.flush()
            except Exception:
                pass

    def flush(self):
        try:
            self.terminal.flush()
        except Exception:
            pass
        if self.log_file:
            try:
                self.log_file.flush()
            except Exception:
                pass


# ── Utilitários de Detecção de Ferramentas ─────────────────────────────────────

def find_executable(names: list[str], extra_paths: list[str] = None) -> str | None:
    """Procura executável no PATH do sistema ou em caminhos conhecidos do Windows."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path

    if extra_paths:
        for p in extra_paths:
            if os.path.isfile(p):
                return p
    return None


def get_git_path() -> str | None:
    return find_executable(
        ["git", "git.exe"],
        [
            os.path.join(BASE_DIR, "tools", "mingit", "cmd", "git.exe"),
            r"C:\Program Files\Git\cmd\git.exe",
            r"C:\Program Files\Git\bin\git.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe")
        ]
    )


def get_gh_path() -> str | None:
    return find_executable(
        ["gh", "gh.exe"],
        [
            r"C:\Program Files\GitHub CLI\gh.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\GitHub CLI\gh.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin\gh.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\gh.exe"),
        ]
    )


def get_iscc_path() -> str | None:
    """Localiza o compilador do Inno Setup (ISCC.exe)."""
    return find_executable(
        ["ISCC", "ISCC.exe", "iscc", "iscc.exe"],
        [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"),
            r"C:\Program Files\Inno Setup 7\ISCC.exe",
            r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
        ]
    )


def compile_with_inno_setup(new_version: str) -> str | None:
    """Compila o script installer/setup.iss usando o Inno Setup."""
    iscc_path = get_iscc_path()
    iss_file = os.path.join(BASE_DIR, "installer", "setup.iss")
    if not iscc_path or not os.path.isfile(iss_file):
        return None

    print(f"  [INNO] Compilando instalador oficial com Inno Setup...")
    cmd = [
        iscc_path,
        f"/DMyAppVersion={new_version}",
        iss_file
    ]
    res = subprocess.run(cmd, cwd=BASE_DIR)
    if res.returncode == 0:
        expected_setup = os.path.join(BASE_DIR, "dist", f"PointLanches-Setup-v{new_version}.exe")
        if os.path.isfile(expected_setup):
            print(f"  [OK] Instalador gerado: {os.path.basename(expected_setup)}")
            return expected_setup
    print("  [AVISO] Falha ao compilar com Inno Setup.")
    return None


def carregar_token_salvo() -> str | None:
    """Verifica se existe um token salvo em arquivo .github_token ou variável de ambiente."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()

    token_file = os.path.join(BASE_DIR, ".github_token")
    if os.path.isfile(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                t = f.read().strip()
                if t:
                    return t
        except Exception:
            pass
    return None


def salvar_token_local(token: str):
    """Salva token no arquivo local .github_token para não precisar digitar novamente."""
    token_file = os.path.join(BASE_DIR, ".github_token")
    try:
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(token.strip())
    except Exception:
        pass


# ── Etapa 1: Atualização do version.py ─────────────────────────────────────────

def update_version_py(new_version: str) -> bool:
    """Atualiza a constante __version__ no arquivo version.py."""
    version_file = os.path.join(BASE_DIR, "version.py")
    if not os.path.isfile(version_file):
        print(f"[ERRO] Arquivo {version_file} não encontrado.")
        return False

    with open(version_file, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(
        r'__version__\s*=\s*["\'][^"\']+["\']',
        f'__version__ = "{new_version}"',
        content
    )

    with open(version_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  [OK] version.py atualizado para: __version__ = '{new_version}'")
    return True


# ── Etapa 2 & 3: Compilação PyInstaller e Preparação dos Binários ─────────────

def compile_with_pyinstaller(onefile: bool = False) -> bool:
    """Executa o PyInstaller usando a especificação do projeto ou modo onefile."""
    python_exe = sys.executable

    if onefile:
        cmd = [
            python_exe, "-m", "PyInstaller",
            "--noconfirm", "--noconsole", "--onefile",
            "--name", "PointLanches",
            "--collect-all", "customtkinter",
            "main.py"
        ]
    else:
        spec_path = os.path.join(BASE_DIR, "PointLanches.spec")
        cmd = [python_exe, "-m", "PyInstaller", "--noconfirm", spec_path]

    print(f"  [EXEC] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    return result.returncode == 0


def prepare_release_artifacts(new_version: str) -> list[str]:
    """
    Localiza o executável compilado em dist/ e garante a presença de:
    1. dist/PointLanches.exe (binário standalone pronto para upload)
    2. dist/PointLanches-vX.Y.Z-windows.zip (pacote zip com todos os arquivos do modo onedir)
    """
    artifacts = []
    dist_dir = os.path.join(BASE_DIR, "dist")

    onedir_exe = os.path.join(dist_dir, "PointLanches", "PointLanches.exe")
    single_exe = os.path.join(dist_dir, "PointLanches.exe")

    if os.path.isfile(onedir_exe):
        # 1. Copiar o executável principal para dist/PointLanches.exe
        try:
            shutil.copy2(onedir_exe, single_exe)
        except Exception:
            pass

        if os.path.isfile(single_exe):
            artifacts.append(single_exe)
        else:
            artifacts.append(onedir_exe)

        # 2. Criar pacote ZIP completo da pasta PointLanches para instalação em novos computadores
        zip_name = f"PointLanches-v{new_version}-windows.zip"
        zip_path = os.path.join(dist_dir, zip_name)
        folder_to_zip = os.path.join(dist_dir, "PointLanches")

        print(f"  [ZIP] Compactando pasta distribuível em: {zip_name}...")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_to_zip):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, dist_dir)
                    zipf.write(full_p, rel_p)

        if os.path.isfile(zip_path):
            artifacts.append(zip_path)

    elif os.path.isfile(single_exe):
        artifacts.append(single_exe)

    # 3. Localizar instalador oficial Inno Setup se presente em dist/
    setup_name = f"PointLanches-Setup-v{new_version}.exe"
    setup_path = os.path.join(dist_dir, setup_name)
    if os.path.isfile(setup_path):
        artifacts.append(setup_path)
    else:
        for f in os.listdir(dist_dir):
            if "setup" in f.lower() and f.endswith(".exe") and new_version in f:
                setup_found = os.path.join(dist_dir, f)
                if setup_found not in artifacts:
                    artifacts.append(setup_found)
                break

    return artifacts


# ── Etapa 4: Versionamento com Git (Commit e Tag) ─────────────────────────────

def run_git_steps(git_path: str, new_version: str, notes: str) -> bool:
    """Executa git add, commit, tag e push."""
    tag_name = f"v{new_version}"
    first_line = notes.splitlines()[0] if notes else f"Versão {new_version}"
    commit_msg = f"Release {tag_name}: {first_line[:50]}"

    commands = [
        ([git_path, "add", "."], "git add ."),
        ([git_path, "commit", "-m", commit_msg], f"git commit -m '{commit_msg}'"),
        ([git_path, "tag", "-a", tag_name, "-m", f"Point Lanches {tag_name}"], f"git tag {tag_name}"),
        ([git_path, "push", "origin", "main"], "git push origin main"),
        ([git_path, "push", "origin", tag_name], f"git push origin {tag_name}"),
    ]

    for cmd, desc in commands:
        print(f"  [GIT] {desc}...")
        res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
        if res.returncode != 0:
            err_msg = res.stderr.strip()
            if "nothing to commit" in err_msg.lower():
                continue
            if "already exists" in err_msg.lower():
                print(f"  [AVISO] Tag {tag_name} já existia localmente.")
                continue
            print(f"  [AVISO] Git retornou: {err_msg}")

    return True


# ── Etapa 5: Publicação no GitHub Releases com Autenticação Amigável ──────────

def garantir_autenticacao_gh(gh_path: str, owner: str, repo: str) -> bool:
    """
    Verifica se o GitHub CLI já está autenticado.
    Se não estiver, oferece autenticação com 1 clique pelo navegador ou token.
    """
    res = subprocess.run([gh_path, "auth", "status"], capture_output=True, text=True)
    if res.returncode == 0:
        return True

    print("\n" + "=" * 64)
    print("🔑 AUTENTICAÇÃO NECESSÁRIA NO GITHUB CLI")
    print("=" * 64)
    print(f"Para publicar automaticamente em https://github.com/{owner}/{repo},")
    print("o GitHub precisa de sua autorização (necessário apenas uma vez):\n")
    print("  [1] Login Automático pelo Navegador com 1 clique (Recomendado)")
    print("  [2] Inserir Token de Acesso do GitHub (Personal Access Token)")
    print("  [3] Pular etapa de upload")
    print("-" * 64)

    try:
        escolha = input("Digite a opção desejada [1]: ").strip() or "1"
    except (EOFError, KeyboardInterrupt):
        return False

    if escolha == "1":
        print("\n>> Abrindo navegador para login seguro no GitHub...")
        print(">> O código foi copiado automaticamente para sua Área de Transferência (Ctrl+V)!")
        login_res = subprocess.run(
            [gh_path, "auth", "login", "--web", "-h", "github.com", "-p", "https", "--clipboard"],
            cwd=BASE_DIR
        )
        return login_res.returncode == 0

    elif escolha == "2":
        try:
            token = input("Cole seu GitHub Token: ").strip()
        except (EOFError, KeyboardInterrupt):
            return False

        if not token:
            return False

        salvar_token_local(token)
        login_res = subprocess.run(
            [gh_path, "auth", "login", "--with-token"],
            input=token, text=True, cwd=BASE_DIR
        )
        return login_res.returncode == 0

    return False


def publish_via_gh_cli(gh_path: str, owner: str, repo: str, tag_name: str, title: str, notes: str, artifacts: list[str]) -> bool:
    """Publica release usando o GitHub CLI (gh release create -R OWNER/REPO)."""
    # 1. Garantir autenticação interativa se necessário
    if not garantir_autenticacao_gh(gh_path, owner, repo):
        return False

    # 2. Verificar se a release já existe para atualizar com --clobber
    check_cmd = [gh_path, "release", "view", tag_name, "-R", f"{owner}/{repo}"]
    check_res = subprocess.run(check_cmd, cwd=BASE_DIR, capture_output=True, text=True)

    if check_res.returncode == 0:
        print(f"\n  [GH] Release {tag_name} ja existe no GitHub. Atualizando artefatos...")
        upload_cmd = [
            gh_path, "release", "upload", tag_name,
            *artifacts,
            "-R", f"{owner}/{repo}",
            "--clobber"
        ]
        up_res = subprocess.run(upload_cmd, cwd=BASE_DIR)
        edit_cmd = [
            gh_path, "release", "edit", tag_name,
            "-R", f"{owner}/{repo}",
            "--title", title,
            "--notes", notes
        ]
        subprocess.run(edit_cmd, cwd=BASE_DIR)
        return up_res.returncode == 0
    else:
        cmd = [
            gh_path, "release", "create", tag_name,
            *artifacts,
            "-R", f"{owner}/{repo}",
            "--title", title,
            "--notes", notes,
            "--clobber"
        ]
        print(f"\n  [GH] Criando release e enviando binarios para {owner}/{repo}...")
        res = subprocess.run(cmd, cwd=BASE_DIR)
        return res.returncode == 0


def publish_via_rest_api(owner: str, repo: str, tag_name: str, title: str, notes: str, artifacts: list[str], token: str) -> bool:
    """
    Publica release via API REST oficial do GitHub (fallback quando o GitHub CLI
    não puder ser executado).
    """
    print(f"  [API] Criando Release {tag_name} em {owner}/{repo} via REST API...")
    url_release = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": f"PointLanches-Publisher/{CURRENT_VERSION}"
    }
    payload = json.dumps({
        "tag_name": tag_name,
        "name": title,
        "body": notes,
        "draft": False,
        "prerelease": False
    }).encode("utf-8")

    req = urllib.request.Request(url_release, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            upload_url_template = data.get("upload_url", "")
            release_html = data.get("html_url", "")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        print(f"  [ERRO API] Código {exc.code}: {err_body}")
        return False
    except Exception as exc:
        print(f"  [ERRO API] {exc}")
        return False

    upload_base = upload_url_template.split("{")[0]

    # Upload dos arquivos binários anexados
    for art in artifacts:
        filename = os.path.basename(art)
        file_size = os.path.getsize(art)
        print(f"  [API] Enviando anexo: {filename} ({file_size / (1024*1024):.1f} MB)...")

        upload_url = f"{upload_base}?name={filename}"
        with open(art, "rb") as f:
            art_data = f.read()

        up_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(art_data)),
            "User-Agent": f"PointLanches-Publisher/{CURRENT_VERSION}"
        }

        up_req = urllib.request.Request(upload_url, data=art_data, headers=up_headers, method="POST")
        try:
            with urllib.request.urlopen(up_req) as up_resp:
                if up_resp.status in (200, 201):
                    print(f"  [OK] Anexo {filename} enviado com sucesso.")
        except Exception as up_exc:
            print(f"  [AVISO] Falha ao enviar {filename}: {up_exc}")

    print(f"\n🎉 Release publicada com sucesso na API!")
    print(f"🔗 Link da Release: {release_html}")
    return True


# ── Ponto de Entrada Principal (CLI) ──────────────────────────────────────────

def main():
    # Ativar gravação contínua no arquivo publicar.log
    sys.stdout = TeeLogger("publicar.log")

    parser = argparse.ArgumentParser(
        description="Publicador de Releases Automatizadas do Point Lanches no GitHub"
    )
    parser.add_argument("version", nargs="?", help="Número da nova versão (ex: 1.0.0 ou 1.0.1)")
    parser.add_argument("-m", "--notes", help="Notas da versão (Changelog)")
    parser.add_argument("--notes-file", help="Arquivo texto contendo as notas da versão")
    parser.add_argument("--owner", default=GITHUB_OWNER, help=f"Dono/Org no GitHub (Padrão: {GITHUB_OWNER})")
    parser.add_argument("--repo", default=GITHUB_REPO, help=f"Repositório no GitHub (Padrão: {GITHUB_REPO})")
    parser.add_argument("--token", help="GitHub Personal Access Token (ou use env GITHUB_TOKEN)")
    parser.add_argument("--skip-build", action="store_true", help="Pular a etapa de compilação PyInstaller")
    parser.add_argument("--skip-git", action="store_true", help="Pular comandos git commit/tag/push")
    parser.add_argument("--skip-upload", action="store_true", help="Apenas compilar e criar tag sem subir para o GitHub")
    parser.add_argument("--onefile", action="store_true", help="Compilar como arquivo único (--onefile)")

    args = parser.parse_args()

    print("=" * 64)
    print("      POINT LANCHES – PUBLICADOR AUTOMATIZADO DE RELEASES")
    print("=" * 64)
    print(f"Versão atual do sistema: v{CURRENT_VERSION}\n")

    # 1. Determinar o número da versão
    new_version = args.version
    if not new_version:
        sugestao = CURRENT_VERSION
        try:
            entrada = input(f"Digite a versão a ser publicada [Sugestão: {sugestao}]: ").strip()
            new_version = entrada if entrada else sugestao
        except (EOFError, KeyboardInterrupt):
            print("\nCancelado pelo operador.")
            sys.exit(0)

    # Limpar prefixo 'v' se digitado
    new_version = new_version.lstrip("vV")
    tag_name = f"v{new_version}"
    release_title = f"Point Lanches v{new_version}"

    # 2. Determinar notas da versão (Changelog)
    notes = args.notes
    if not notes and args.notes_file and os.path.isfile(args.notes_file):
        with open(args.notes_file, "r", encoding="utf-8") as f:
            notes = f.read().strip()

    if not notes:
        notes = (
            f"### Point Lanches v{new_version} - Lançamento Oficial\n\n"
            f"- Data de compilação: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            f"- PDV comercial com resolução adaptada a 1366x768 e Full HD.\n"
            f"- Integração térmica Elgin i8 (TCP Socket 9100 e USB Spooler).\n"
            f"- Base oficial de ruas de Dois Irmãos - RS e Auto-Update via GitHub."
        )

    print("\n" + "-" * 64)
    print(f"Resumo da Operação:")
    print(f"  • Versão da Release: {tag_name}")
    print(f"  • Repositório Alvo:  https://github.com/{args.owner}/{args.repo}")
    print(f"  • Título do Release: {release_title}")
    print("-" * 64 + "\n")

    # ETAPA 1: Atualizar version.py
    print(f"[1/5] [VERSAO] Verificando version.py...")
    if not update_version_py(new_version):
        sys.exit(1)

    # ETAPA 2: Compilação PyInstaller
    if not args.skip_build:
        print(f"\n[2/5] [BUILD] Compilando executavel com PyInstaller...")
        if not compile_with_pyinstaller(onefile=args.onefile):
            print("[ERRO] Falha na compilacao do executavel com PyInstaller.")
            sys.exit(1)
        print("  [OK] Compilacao concluida com sucesso!")

        # Compilar Instalador Inno Setup se disponível
        iscc_path = get_iscc_path()
        if iscc_path:
            print(f"\n[2B/5] [INNO] Compilando instalador oficial com Inno Setup...")
            compile_with_inno_setup(new_version)
    else:
        print("\n[2/5] [BUILD] Pulando etapa de compilacao (--skip-build).")

    # ETAPA 3: Verificar e preparar artefatos
    print(f"\n[3/5] [ARTEFATOS] Verificando artefatos gerados em dist/...")
    artifacts = prepare_release_artifacts(new_version)
    if not artifacts:
        print("[ERRO] Nenhum executavel ou pacote encontrado na pasta dist/.")
        sys.exit(1)

    for art in artifacts:
        sz_mb = os.path.getsize(art) / (1024 * 1024)
        print(f"  * Artefato pronto: {os.path.basename(art)} ({sz_mb:.2f} MB)")

    # ETAPA 4: Comandos do Git
    git_path = get_git_path()
    if not args.skip_git and git_path:
        print(f"\n[4/5] [GIT] Sincronizando commit e tag ({tag_name})...")
        run_git_steps(git_path, new_version, notes)
    else:
        print(f"\n[4/5] [GIT] Etapa Git ignorada.")

    # ETAPA 5: Publicar no GitHub
    if args.skip_upload:
        print("\n[5/5] [UPLOAD] Upload pulado (--skip-upload). Publicacao local finalizada!")
        return

    print(f"\n[5/5] [RELEASE] Publicando Release oficial em {args.owner}/{args.repo}...")
    gh_path = get_gh_path()
    token = args.token or carregar_token_salvo()

    sucesso = False

    # Opção A: GitHub CLI (prioritário)
    if gh_path:
        print(f"  * Utilizando GitHub CLI ({gh_path})...")
        sucesso = publish_via_gh_cli(gh_path, args.owner, args.repo, tag_name, release_title, notes, artifacts)

    # Opção B: Fallback via REST API com Token
    if not sucesso and token:
        print("  * Utilizando API REST do GitHub com Token...")
        sucesso = publish_via_rest_api(args.owner, args.repo, tag_name, release_title, notes, artifacts, token)

    # Opção C: Se a publicação falhou
    if not sucesso:
        print("\n" + "!" * 64)
        print("[AVISO] A PUBLICACAO AUTOMATICA NAO FOI CONCLUIDA")
        print("!" * 64)
        print("Motivo: A autorizacao ou o envio ao GitHub falhou.")
        print(f"\nOs arquivos ja estao gerados e prontos em:")
        for art in artifacts:
            print(f"   -> {art}")
        print("\nConsulte o arquivo publicar.log para detalhes.")
        print("!" * 64)
        sys.exit(1)

    print("\n" + "=" * 64)
    print(f"[SUCESSO] RELEASE {tag_name} PUBLICADA COM SUCESSO!")
    print(f"Link Oficial: https://github.com/{args.owner}/{args.repo}/releases/tag/{tag_name}")
    print("=" * 64)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[ERRO CRÍTICO] {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
