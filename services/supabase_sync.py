# services/supabase_sync.py - Sincronização em segundo plano SQLite <-> Supabase
# =============================================================================

import json
import ssl
import threading
import urllib.request
import urllib.error
from typing import Dict, Any, List

from services.supabase_auth import auth_manager, _get_credentials


def _fazer_requisicao(endpoint: str, metodo: str = "GET", dados: Any = None) -> Any:
    url, _ = _get_credentials()
    full_url = f"{url}/rest/v1/{endpoint}"
    headers = auth_manager.get_auth_headers()
    headers["Prefer"] = "return=representation"

    ctx = ssl._create_unverified_context()
    body = json.dumps(dados).encode("utf-8") if dados is not None else None
    req = urllib.request.Request(full_url, data=body, headers=headers, method=metodo)

    with urllib.request.urlopen(req, context=ctx, timeout=6) as resp:
        content = resp.read().decode("utf-8")
        return json.loads(content) if content else None


def enviar_pedido_supabase_async(pedido: Dict[str, Any], itens: List[Dict[str, Any]]):
    """Dispara o envio do pedido e itens para o Supabase em segundo plano (não trava o caixa)."""
    if not auth_manager.is_authenticated():
        # Modo offline ou sem autenticação: mantém persistência no SQLite local
        return

    def _worker():
        try:
            # 1. Montar payload do pedido
            payload_pedido = {
                "numero": pedido.get("numero", 0),
                "cliente_nome": pedido.get("cliente_nome", ""),
                "cliente_fone": pedido.get("cliente_fone", ""),
                "endereco_rua": pedido.get("rua", ""),
                "endereco_num": pedido.get("numero", ""),
                "endereco_comp": pedido.get("complemento", ""),
                "endereco_bairro": pedido.get("bairro", ""),
                "endereco_ref": pedido.get("referencia", ""),
                "subtotal": float(pedido.get("subtotal", 0.0) or 0.0),
                "taxa_entrega": float(pedido.get("taxa_entrega", 0.0) or 0.0),
                "total": float(pedido.get("total", 0.0) or 0.0),
                "forma_pgto": pedido.get("forma_pgto", ""),
                "valor_pago": float(pedido.get("valor_pago", 0.0) or 0.0),
                "troco": float(pedido.get("troco", 0.0) or 0.0),
                "status": "fechado"
            }

            resp_ped = _fazer_requisicao("pedidos", metodo="POST", dados=[payload_pedido])
            if resp_ped and len(resp_ped) > 0:
                pedido_supabase_id = resp_ped[0]["id"]
                # 2. Montar itens vinculados
                payload_itens = []
                for it in itens:
                    payload_itens.append({
                        "pedido_id": pedido_supabase_id,
                        "produto_id": it.get("produto_id"),
                        "nome": it.get("nome", ""),
                        "preco_unit": float(it.get("preco_unit", 0.0) or 0.0),
                        "quantidade": int(it.get("quantidade", 1)),
                        "observacao": it.get("observacao", ""),
                        "categoria": it.get("categoria", "")
                    })
                if payload_itens:
                    _fazer_requisicao("itens_pedido", metodo="POST", dados=payload_itens)
        except Exception:
            # Em caso de falha de conexão ou timeout, o pedido já está 100% seguro no SQLite local
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
