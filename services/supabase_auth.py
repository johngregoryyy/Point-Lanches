# services/supabase_auth.py - Gerenciamento de Autenticação e Conexão Supabase
# =============================================================================

import os
import sys
import json
import ssl
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any

from config import SUPABASE_URL_DEFAULT, SUPABASE_KEY_DEFAULT


def _get_auth_file_path() -> str:
    """Retorna o caminho seguro para persistência da sessão de login."""
    local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    data_dir = os.path.join(local_app_data, "PointLanches", "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "supabase_session.json")


def _get_credentials() -> Tuple[str, str]:
    """Obtém SUPABASE_URL e SUPABASE_KEY priorizando .env local e usando fallback seguro."""
    url = SUPABASE_URL_DEFAULT
    key = SUPABASE_KEY_DEFAULT

    # Tenta carregar do .env local se existir (desenvolvimento ou máquina da loja)
    caminhos_env = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        os.path.join(getattr(sys, "_MEIPASS", os.path.abspath(".")), ".env"),
        os.path.join(os.path.dirname(sys.executable), ".env") if getattr(sys, "frozen", False) else ""
    ]

    for p in caminhos_env:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip()
                            if k == "SUPABASE_URL" and v:
                                url = v
                            elif k == "SUPABASE_KEY" and v:
                                key = v
                break
            except Exception:
                pass

    return url.rstrip("/"), key


class SupabaseAuthManager:
    """Singleton para gerenciamento da sessão Supabase Auth no PDV."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._session = None
            cls._instance._listeners = []
            cls._instance._carregar_sessao_salva()
        return cls._instance

    def _carregar_sessao_salva(self):
        caminho = _get_auth_file_path()
        if os.path.exists(caminho):
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("access_token"):
                        self._session = data
            except Exception:
                self._session = None

    def add_auth_listener(self, callback):
        """Registra callback que recebe bool (True=logado, False=offline) em mudanças de estado."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _notificar_listeners(self):
        status = self.is_authenticated()
        for cb in self._listeners:
            try:
                cb(status)
            except Exception:
                pass

    def is_authenticated(self) -> bool:
        """Verifica se há sessão autenticada ativa."""
        return bool(self._session and self._session.get("access_token"))

    def get_user_email(self) -> str:
        """Retorna o e-mail do usuário autenticado ou vazio."""
        if self._session and "user" in self._session:
            return self._session["user"].get("email", "")
        return ""

    def get_auth_headers(self) -> Dict[str, str]:
        """Retorna headers para requisições autenticadas no Supabase REST."""
        url, key = _get_credentials()
        headers = {
            "apikey": key,
            "Content-Type": "application/json"
        }
        if self.is_authenticated():
            token = self._session.get("access_token")
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def login(self, email: str, password: str, remember: bool = True) -> Tuple[bool, str]:
        """
        Autentica usuário e senha diretamente no Supabase Auth.
        Endpoint: POST /auth/v1/token?grant_type=password
        """
        email = email.strip()
        if not email or not password:
            return False, "Informe e-mail e senha."

        url, key = _get_credentials()
        endpoint = f"{url}/auth/v1/token?grant_type=password"
        payload = json.dumps({"email": email, "password": password}).encode("utf-8")
        headers = {
            "apikey": key,
            "Content-Type": "application/json"
        }

        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._session = data
                if remember:
                    try:
                        with open(_get_auth_file_path(), "w", encoding="utf-8") as f:
                            json.dump(data, f)
                    except Exception:
                        pass
                self._notificar_listeners()
                return True, "Autenticado com sucesso!"
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                msg = err_data.get("msg") or err_data.get("error_description") or "Credenciais inválidas."
                if "invalid_credentials" in str(err_data).lower():
                    msg = "E-mail ou senha incorretos."
            except Exception:
                msg = f"Falha na autenticação (código HTTP {e.code})."
            return False, msg
        except urllib.error.URLError as e:
            return False, "Sem conexão com a internet ou servidor indisponível."
        except Exception as e:
            return False, f"Erro ao autenticar: {str(e)}"

    def logout(self):
        """Encerra a sessão e remove dados locais."""
        self._session = None
        caminho = _get_auth_file_path()
        if os.path.exists(caminho):
            try:
                os.remove(caminho)
            except Exception:
                pass
        self._notificar_listeners()


# Instância global para uso em todo o aplicativo
auth_manager = SupabaseAuthManager()
