# services/supabase_sync.py - Sincronização Bidirecional SQLite <-> Supabase
# =============================================================================

import json
import ssl
import threading
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

from services.supabase_auth import auth_manager, _get_credentials


def _fazer_requisicao(endpoint: str, metodo: str = "GET", dados: Any = None, timeout: int = 8) -> Any:
    url, _ = _get_credentials()
    full_url = f"{url}/rest/v1/{endpoint}"
    headers = auth_manager.get_auth_headers()
    headers["Prefer"] = "return=representation"

    ctx = ssl._create_unverified_context()
    body = json.dumps(dados).encode("utf-8") if dados is not None else None
    req = urllib.request.Request(full_url, data=body, headers=headers, method=metodo)

    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        content = resp.read().decode("utf-8")
        return json.loads(content) if content else None


def puxar_dados_do_supabase(timeout: int = 8) -> bool:
    """
    Puxa do Supabase todas as tabelas mestras (categorias, produtos, adicionais,
    taxas de tele, observações rápidas, ruas, configurações) e atualiza o banco local SQLite.
    Garante que o PDV reflita fielmente os dados do Supabase.
    """
    try:
        from database.db import get_connection, _notificar_ruas_modificadas

        # 1. Puxar dados da nuvem
        cat_data = _fazer_requisicao("categorias?select=*&order=ordem.asc,id.asc", timeout=timeout)
        prod_data = _fazer_requisicao("produtos?select=*&order=id.asc", timeout=timeout)
        adic_data = _fazer_requisicao("adicionais?select=*&order=id.asc", timeout=timeout)
        taxas_data = _fazer_requisicao("taxas_entrega?select=*&order=ordem.asc,id.asc", timeout=timeout)
        obs_data = _fazer_requisicao("observacoes_padrao?select=*&order=id.asc", timeout=timeout)
        ruas_data = _fazer_requisicao("ruas?select=*&order=nome.asc", timeout=timeout)
        cfg_data = _fazer_requisicao("configuracoes?select=*", timeout=timeout)

        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF;")

            if cat_data is not None:
                conn.execute("DELETE FROM categorias;")
                for c in cat_data:
                    conn.execute(
                        "INSERT INTO categorias (id, nome, ordem) VALUES (?, ?, ?);",
                        (c["id"], c["nome"], c.get("ordem", 0))
                    )

            if prod_data is not None:
                conn.execute("DELETE FROM produtos;")
                for p in prod_data:
                    conn.execute(
                        "INSERT INTO produtos (id, categoria_id, nome, descricao, preco, ativo) VALUES (?, ?, ?, ?, ?, ?);",
                        (p["id"], p["categoria_id"], p["nome"], p.get("descricao", ""), float(p["preco"]), p.get("ativo", 1))
                    )

            if adic_data is not None:
                conn.execute("DELETE FROM adicionais;")
                for a in adic_data:
                    conn.execute(
                        "INSERT INTO adicionais (id, nome, preco, ativo) VALUES (?, ?, ?, ?);",
                        (a["id"], a["nome"], float(a["preco"]), a.get("ativo", 1))
                    )

            if taxas_data is not None:
                conn.execute("DELETE FROM taxas_entrega;")
                for t in taxas_data:
                    conn.execute(
                        "INSERT INTO taxas_entrega (id, valor, label, ativo, ordem) VALUES (?, ?, ?, ?, ?);",
                        (t["id"], float(t["valor"]), t["label"], t.get("ativo", 1), t.get("ordem", 0))
                    )

            if obs_data is not None:
                conn.execute("DELETE FROM observacoes_padrao;")
                for o in obs_data:
                    conn.execute(
                        "INSERT INTO observacoes_padrao (id, texto, ativo) VALUES (?, ?, ?);",
                        (o["id"], o["texto"], o.get("ativo", 1))
                    )

            if ruas_data is not None and len(ruas_data) > 0:
                conn.execute("DELETE FROM ruas;")
                for r in ruas_data:
                    conn.execute(
                        "INSERT INTO ruas (id, nome, ativo, bairro, taxa) VALUES (?, ?, ?, ?, ?);",
                        (r["id"], r["nome"], r.get("ativo", 1), r.get("bairro", ""), float(r.get("taxa", 0.0) or 0.0))
                    )

            if cfg_data is not None and len(cfg_data) > 0:
                for cfg in cfg_data:
                    conn.execute(
                        "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?);",
                        (cfg["chave"], cfg["valor"])
                    )

            conn.execute("PRAGMA foreign_keys = ON;")

        _notificar_ruas_modificadas()
        return True
    except Exception as e:
        print(f"Aviso: Não foi possível sincronizar catálogo do Supabase: {e}")
        return False


def sincronizar_item_supabase_async(tabela: str, dados: Any, metodo: str = "POST", query_params: str = ""):
    """Envia alteração em segundo plano para o Supabase se autenticado."""
    def _worker():
        try:
            endpoint = f"{tabela}{'?' + query_params if query_params else ''}"
            _fazer_requisicao(endpoint, metodo=metodo, dados=dados)
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def enviar_pedido_supabase_async(pedido: Dict[str, Any], itens: List[Dict[str, Any]]):
    """Dispara o envio do pedido e itens para o Supabase em segundo plano (não trava o caixa)."""
    def _worker():
        try:
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
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def sincronizar_pedidos_pendentes_supabase(timeout: int = 4):
    """Verifica e envia pedidos locais que ainda não constam no Supabase."""
    try:
        from database.db import get_connection

        # Consultar últimos pedidos do Supabase
        pedidos_remotos = _fazer_requisicao("pedidos?select=numero", timeout=timeout) or []
        numeros_remotos = {p["numero"] for p in pedidos_remotos if "numero" in p}

        with get_connection() as conn:
            locais = conn.execute("SELECT * FROM pedidos ORDER BY id ASC").fetchall()
            for ped_row in locais:
                ped = dict(ped_row)
                if ped["numero"] not in numeros_remotos:
                    # Enviar pedido pendente e seus itens
                    itens_rows = conn.execute("SELECT * FROM itens_pedido WHERE pedido_id=?", (ped["id"],)).fetchall()
                    itens = [dict(r) for r in itens_rows]
                    
                    payload_pedido = {
                        "numero": ped["numero"],
                        "cliente_nome": ped.get("cliente_nome", ""),
                        "cliente_fone": ped.get("cliente_fone", ""),
                        "endereco_rua": ped.get("endereco_rua", ""),
                        "endereco_num": ped.get("endereco_num", ""),
                        "endereco_comp": ped.get("endereco_comp", ""),
                        "endereco_bairro": ped.get("endereco_bairro", ""),
                        "endereco_ref": ped.get("endereco_ref", ""),
                        "subtotal": float(ped.get("subtotal", 0.0) or 0.0),
                        "taxa_entrega": float(ped.get("taxa_entrega", 0.0) or 0.0),
                        "total": float(ped.get("total", 0.0) or 0.0),
                        "forma_pgto": ped.get("forma_pgto", ""),
                        "valor_pago": float(ped.get("valor_pago", 0.0) or 0.0),
                        "troco": float(ped.get("troco", 0.0) or 0.0),
                        "status": ped.get("status", "fechado")
                    }
                    resp_ped = _fazer_requisicao("pedidos", metodo="POST", dados=[payload_pedido], timeout=timeout)
                    if resp_ped and len(resp_ped) > 0:
                        supa_id = resp_ped[0]["id"]
                        payload_itens = []
                        for it in itens:
                            payload_itens.append({
                                "pedido_id": supa_id,
                                "produto_id": it.get("produto_id"),
                                "nome": it.get("nome", ""),
                                "preco_unit": float(it.get("preco_unit", 0.0) or 0.0),
                                "quantidade": int(it.get("quantidade", 1)),
                                "observacao": it.get("observacao", ""),
                                "categoria": it.get("categoria", "")
                            })
                        if payload_itens:
                            _fazer_requisicao("itens_pedido", metodo="POST", dados=payload_itens, timeout=timeout)
    except Exception as e:
        print(f"Aviso ao sincronizar pedidos pendentes: {e}")


def sincronizar_tudo_com_supabase(timeout: int = 5) -> bool:
    """Executa sincronização bidirecional completa: envia pendências locais e puxa atualizações da nuvem."""
    try:
        sincronizar_pedidos_pendentes_supabase(timeout=timeout)
        puxar_dados_do_supabase(timeout=timeout)
        return True
    except Exception as e:
        print(f"Erro na sincronização completa: {e}")
        return False
