# services/supabase_sync.py - Sincronização Bidirecional SQLite <-> Supabase
# =============================================================================

import json
import ssl
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from services.supabase_auth import auth_manager, _get_credentials

TZ_BRASILIA = timezone(timedelta(hours=-3))


def normalizar_data_iso(data_str: str) -> str:
    """Converte timestamp ISO do Supabase para formato local do SQLite (YYYY-MM-DD HH:MM:SS)."""
    if not data_str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if "T" in data_str:
            clean = data_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean)
            if dt.tzinfo is not None:
                dt = dt.astimezone(TZ_BRASILIA)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return data_str[:19]
    except Exception:
        return str(data_str)[:19]


def _fazer_requisicao(endpoint: str, metodo: str = "GET", dados: Any = None, timeout: int = 8) -> Any:
    url, _ = _get_credentials()
    full_url = f"{url}/rest/v1/{endpoint}"

    for tentativa in range(2):
        headers = auth_manager.get_auth_headers()
        headers["Prefer"] = "return=representation"

        ctx = ssl._create_unverified_context()
        body = json.dumps(dados).encode("utf-8") if dados is not None else None
        req = urllib.request.Request(full_url, data=body, headers=headers, method=metodo)

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                content = resp.read().decode("utf-8")
                return json.loads(content) if content else None
        except urllib.error.HTTPError as e:
            if e.code == 401 and tentativa == 0:
                # Token expirado: tenta refresh transparente e reexecuta
                if auth_manager.refresh_session():
                    continue
            raise e
        except Exception as e:
            raise e


def puxar_dados_do_supabase(timeout: int = 8) -> bool:
    """
    Puxa do Supabase todas as tabelas mestras (categorias, produtos, adicionais,
    taxas de tele, observações rápidas, ruas, configurações) em PARALELO e atualiza o SQLite em lote.
    Máxima performance com zero travamento.
    """
    try:
        import concurrent.futures
        from database.db import get_connection, _notificar_ruas_modificadas

        # 1. Puxar dados da nuvem em PARALELO (7 requisições simultâneas)
        endpoints = {
            "cat": "categorias?select=*&order=ordem.asc,id.asc",
            "prod": "produtos?select=*&order=id.asc",
            "adic": "adicionais?select=*&order=id.asc",
            "taxas": "taxas_entrega?select=*&order=ordem.asc,id.asc",
            "obs": "observacoes_padrao?select=*&order=id.asc",
            "ruas": "ruas?select=*&order=nome.asc",
            "cfg": "configuracoes?select=*",
        }

        resultados = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            future_to_key = {
                executor.submit(_fazer_requisicao, ep, timeout=timeout): k
                for k, ep in endpoints.items()
            }
            for future in concurrent.futures.as_completed(future_to_key):
                k = future_to_key[future]
                try:
                    resultados[k] = future.result()
                except Exception:
                    resultados[k] = None

        cat_data   = resultados.get("cat")
        prod_data  = resultados.get("prod")
        adic_data  = resultados.get("adic")
        taxas_data = resultados.get("taxas")
        obs_data   = resultados.get("obs")
        ruas_data  = resultados.get("ruas")
        cfg_data   = resultados.get("cfg")

        # 2. Atualização atômica e em lote no SQLite (executemany)
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF;")

            if cat_data is not None:
                conn.execute("DELETE FROM categorias;")
                conn.executemany(
                    "INSERT INTO categorias (id, nome, ordem, eh_bebida) VALUES (?, ?, ?, ?);",
                    [
                        (
                            c["id"],
                            c["nome"],
                            c.get("ordem", 0),
                            int(c["eh_bebida"]) if "eh_bebida" in c and c["eh_bebida"] is not None else (1 if "bebida" in c.get("nome", "").lower() else 0)
                        )
                        for c in cat_data
                    ]
                )

            if prod_data is not None:
                conn.execute("DELETE FROM produtos;")
                conn.executemany(
                    "INSERT INTO produtos (id, categoria_id, nome, descricao, preco, ativo) VALUES (?, ?, ?, ?, ?, ?);",
                    [(p["id"], p["categoria_id"], p["nome"], p.get("descricao", ""), float(p["preco"]), p.get("ativo", 1)) for p in prod_data]
                )

            if adic_data is not None:
                conn.execute("DELETE FROM adicionais;")
                conn.executemany(
                    "INSERT INTO adicionais (id, nome, preco, ativo) VALUES (?, ?, ?, ?);",
                    [(a["id"], a["nome"], float(a["preco"]), a.get("ativo", 1)) for a in adic_data]
                )

            if taxas_data is not None:
                conn.execute("DELETE FROM taxas_entrega;")
                conn.executemany(
                    "INSERT INTO taxas_entrega (id, valor, label, ativo, ordem) VALUES (?, ?, ?, ?, ?);",
                    [(t["id"], float(t["valor"]), t["label"], t.get("ativo", 1), t.get("ordem", 0)) for t in taxas_data]
                )

            if obs_data is not None:
                conn.execute("DELETE FROM observacoes_padrao;")
                conn.executemany(
                    "INSERT INTO observacoes_padrao (id, texto, ativo) VALUES (?, ?, ?);",
                    [(o["id"], o["texto"], o.get("ativo", 1)) for o in obs_data]
                )

            if ruas_data is not None and len(ruas_data) > 0:
                conn.execute("DELETE FROM ruas;")
                conn.executemany(
                    "INSERT INTO ruas (id, nome, ativo, bairro, taxa) VALUES (?, ?, ?, ?, ?);",
                    [(r["id"], r["nome"], r.get("ativo", 1), r.get("bairro", ""), float(r.get("taxa", 0.0) or 0.0)) for r in ruas_data]
                )

            if cfg_data is not None and len(cfg_data) > 0:
                conn.executemany(
                    "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?);",
                    [(cfg["chave"], cfg["valor"]) for cfg in cfg_data]
                )

            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON;")

        _notificar_ruas_modificadas()
        return True
    except Exception as e:
        print(f"Aviso: Não foi possível sincronizar catálogo do Supabase: {e}")
        try:
            from services.error_logger import log_exception
            log_exception(modulo="supabase_sync", exc=e, contexto="Falha ao puxar catálogo do Supabase", tipo="SUPABASE")
        except Exception:
            pass
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
            from database.db import get_connection

            id_local = pedido.get("id_local")
            num_pedido = int(pedido.get("numero_pedido") or pedido.get("numero") or 0)
            rua = str(pedido.get("endereco_rua") or pedido.get("rua") or "")
            num_casa = str(pedido.get("endereco_num") or pedido.get("numero_casa") or (pedido.get("numero") if pedido.get("numero_pedido") else "") or "")
            comp = str(pedido.get("endereco_comp") or pedido.get("complemento") or "")
            bairro = str(pedido.get("endereco_bairro") or pedido.get("bairro") or "")
            ref = str(pedido.get("endereco_ref") or pedido.get("referencia") or "")

            payload_pedido = {
                "numero": num_pedido,
                "cliente_nome": str(pedido.get("cliente_nome") or ""),
                "cliente_fone": str(pedido.get("cliente_fone") or ""),
                "endereco_rua": rua,
                "endereco_num": num_casa,
                "endereco_comp": comp,
                "endereco_bairro": bairro,
                "endereco_ref": ref,
                "subtotal": float(pedido.get("subtotal", 0.0) or 0.0),
                "taxa_entrega": float(pedido.get("taxa_entrega", 0.0) or 0.0),
                "total": float(pedido.get("total", 0.0) or 0.0),
                "forma_pgto": str(pedido.get("forma_pgto") or ""),
                "valor_pago": float(pedido.get("valor_pago", 0.0) or 0.0),
                "troco": float(pedido.get("troco", 0.0) or 0.0),
                "status": "fechado"
            }

            resp_ped = _fazer_requisicao("pedidos", metodo="POST", dados=[payload_pedido])
            if resp_ped and len(resp_ped) > 0:
                pedido_supabase_id = resp_ped[0]["id"]
                if id_local:
                    try:
                        with get_connection() as conn:
                            conn.execute("UPDATE pedidos SET supabase_id=? WHERE id=?", (pedido_supabase_id, id_local))
                            conn.commit()
                    except Exception:
                        pass

                payload_itens = []
                for it in itens:
                    payload_itens.append({
                        "pedido_id": pedido_supabase_id,
                        "produto_id": None,  # None previne erro 409 de foreign key caso o ID de produto divirja
                        "nome": it.get("nome", ""),
                        "preco_unit": float(it.get("preco_unit", 0.0) or 0.0),
                        "quantidade": int(it.get("quantidade", 1)),
                        "observacao": it.get("observacao", ""),
                        "categoria": it.get("categoria", "")
                    })
                if payload_itens:
                    _fazer_requisicao("itens_pedido", metodo="POST", dados=payload_itens)
        except Exception as e:
            print(f"Aviso ao enviar pedido assíncrono para Supabase: {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def sincronizar_pedidos_com_supabase(timeout: int = 8) -> bool:
    """
    Sincronização bidirecional completa de Pedidos e Itens:
    1. Envia pedidos locais não sincronizados para o Supabase (garante subida de todos os pedidos da loja).
    2. Puxa do Supabase pedidos e itens inexistentes no SQLite local (popula máquinas novas ou com base limpa).
    """
    try:
        from database.db import get_connection

        # 1. Obter todos os pedidos do Supabase
        pedidos_remotos = _fazer_requisicao("pedidos?select=*&order=id.asc", timeout=timeout) or []

        with get_connection() as conn:
            # A) Checar pedidos locais sem supabase_id (ou novos que foram salvos offline)
            locais_sem_sync = conn.execute("SELECT * FROM pedidos WHERE supabase_id IS NULL ORDER BY id ASC").fetchall()

            for ped_row in locais_sem_sync:
                ped = dict(ped_row)
                local_id = ped["id"]
                num_local = ped.get("numero", 0)
                tot_local = float(ped.get("total", 0.0) or 0.0)
                rua_local = (ped.get("endereco_rua") or "").strip().lower()

                # Tentar encontrar correspondência em pedidos remotos já existentes
                match_supa_id = None
                for rem in pedidos_remotos:
                    if rem.get("numero") == num_local and abs(float(rem.get("total", 0.0) or 0.0) - tot_local) < 0.05:
                        rem_rua = (rem.get("endereco_rua") or "").strip().lower()
                        if not rua_local or not rem_rua or rua_local == rem_rua:
                            match_supa_id = rem["id"]
                            break

                if match_supa_id:
                    conn.execute("UPDATE pedidos SET supabase_id=? WHERE id=?", (match_supa_id, local_id))
                else:
                    # Enviar pedido inédito para o Supabase
                    payload_pedido = {
                        "numero": num_local,
                        "cliente_nome": ped.get("cliente_nome", ""),
                        "cliente_fone": ped.get("cliente_fone", ""),
                        "endereco_rua": ped.get("endereco_rua", ""),
                        "endereco_num": ped.get("endereco_num", ""),
                        "endereco_comp": ped.get("endereco_comp", ""),
                        "endereco_bairro": ped.get("endereco_bairro", ""),
                        "endereco_ref": ped.get("endereco_ref", ""),
                        "subtotal": float(ped.get("subtotal", 0.0) or 0.0),
                        "taxa_entrega": float(ped.get("taxa_entrega", 0.0) or 0.0),
                        "total": tot_local,
                        "forma_pgto": ped.get("forma_pgto", ""),
                        "valor_pago": float(ped.get("valor_pago", 0.0) or 0.0),
                        "troco": float(ped.get("troco", 0.0) or 0.0),
                        "status": ped.get("status", "fechado")
                    }
                    resp_ped = _fazer_requisicao("pedidos", metodo="POST", dados=[payload_pedido], timeout=timeout)
                    if resp_ped and len(resp_ped) > 0:
                        new_supa_id = resp_ped[0]["id"]
                        conn.execute("UPDATE pedidos SET supabase_id=? WHERE id=?", (new_supa_id, local_id))

                        itens_rows = conn.execute("SELECT * FROM itens_pedido WHERE pedido_id=?", (local_id,)).fetchall()
                        payload_itens = []
                        for it in itens_rows:
                            it_d = dict(it)
                            payload_itens.append({
                                "pedido_id": new_supa_id,
                                "produto_id": None,
                                "nome": it_d.get("nome", ""),
                                "preco_unit": float(it_d.get("preco_unit", 0.0) or 0.0),
                                "quantidade": int(it_d.get("quantidade", 1)),
                                "observacao": it_d.get("observacao", ""),
                                "categoria": it_d.get("categoria", "")
                            })
                        if payload_itens:
                            _fazer_requisicao("itens_pedido", metodo="POST", dados=payload_itens, timeout=timeout)

            conn.commit()

            # B) Puxar pedidos do Supabase que NÃO estão no SQLite local
            locais_supa_ids = {
                r[0] for r in conn.execute("SELECT supabase_id FROM pedidos WHERE supabase_id IS NOT NULL").fetchall()
            }

            pedidos_para_baixar = [p for p in pedidos_remotos if p["id"] not in locais_supa_ids]

            if pedidos_para_baixar:
                # Baixar todos os itens dos pedidos em lote
                supa_ids_str = ",".join(str(p["id"]) for p in pedidos_para_baixar)
                try:
                    todos_itens_remotos = _fazer_requisicao(f"itens_pedido?pedido_id=in.({supa_ids_str})&order=id.asc", timeout=timeout) or []
                except Exception:
                    todos_itens_remotos = []

                itens_por_pedido = {}
                for it in todos_itens_remotos:
                    pid = it.get("pedido_id")
                    if pid:
                        itens_por_pedido.setdefault(pid, []).append(it)

                conn.execute("PRAGMA foreign_keys = OFF;")
                for rem in pedidos_para_baixar:
                    data_normalizada = normalizar_data_iso(rem.get("criado_em"))
                    cur = conn.execute("""
                        INSERT INTO pedidos
                          (numero, cliente_nome, cliente_fone, endereco_rua, endereco_num,
                           endereco_comp, endereco_bairro, endereco_ref,
                           subtotal, taxa_entrega, total, forma_pgto, valor_pago, troco, status, criado_em, supabase_id)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        rem.get("numero", 0),
                        rem.get("cliente_nome", ""),
                        rem.get("cliente_fone", ""),
                        rem.get("endereco_rua", ""),
                        rem.get("endereco_num", ""),
                        rem.get("endereco_comp", ""),
                        rem.get("endereco_bairro", ""),
                        rem.get("endereco_ref", ""),
                        float(rem.get("subtotal", 0.0) or 0.0),
                        float(rem.get("taxa_entrega", 0.0) or 0.0),
                        float(rem.get("total", 0.0) or 0.0),
                        rem.get("forma_pgto", ""),
                        float(rem.get("valor_pago", 0.0) or 0.0),
                        float(rem.get("troco", 0.0) or 0.0),
                        rem.get("status", "fechado"),
                        data_normalizada,
                        rem["id"]
                    ))
                    local_new_id = cur.lastrowid

                    itens_deste = itens_por_pedido.get(rem["id"], [])
                    for it in itens_deste:
                        conn.execute("""
                            INSERT INTO itens_pedido
                              (pedido_id, produto_id, nome, preco_unit, quantidade, observacao, categoria)
                            VALUES (?,?,?,?,?,?,?)
                        """, (
                            local_new_id,
                            it.get("produto_id"),
                            it.get("nome", ""),
                            float(it.get("preco_unit", 0.0) or 0.0),
                            int(it.get("quantidade", 1)),
                            it.get("observacao", ""),
                            it.get("categoria", "")
                        ))

                conn.commit()
                conn.execute("PRAGMA foreign_keys = ON;")

        return True
    except Exception as e:
        print(f"Aviso ao sincronizar pedidos com Supabase: {e}")
        try:
            from services.error_logger import log_exception
            log_exception(modulo="supabase_sync", exc=e, contexto="Falha na sincronização de pedidos", tipo="SUPABASE")
        except Exception:
            pass
        return False


# Alias de retrocompatibilidade
sincronizar_pedidos_pendentes_supabase = sincronizar_pedidos_com_supabase


def sincronizar_log_supabase_async(log_id: int, log_data: Dict[str, Any]):
    """Envia o log de erro para o Supabase em segundo plano com fallback transparente."""
    def _worker():
        try:
            from database.db import get_connection

            payload = {
                "tipo": log_data.get("tipo", "ERRO"),
                "modulo": log_data.get("modulo", ""),
                "mensagem": str(log_data.get("mensagem", ""))[:500],
                "detalhes": str(log_data.get("detalhes", ""))[:4000],
                "versao_app": str(log_data.get("versao_app", "1.1.6"))
            }

            try:
                resp = _fazer_requisicao("logs_erro", metodo="POST", dados=[payload], timeout=5)
                if resp and len(resp) > 0:
                    supa_id = resp[0].get("id")
                    if supa_id:
                        with get_connection() as conn:
                            conn.execute("UPDATE logs_erro SET supabase_id=? WHERE id=?", (supa_id, log_id))
                            conn.commit()
                        return
            except urllib.error.HTTPError as he:
                if he.code == 404:
                    # Tabela logs_erro ainda não criada no Supabase Dashboard
                    # Fallback de contingência: grava na tabela configuracoes
                    try:
                        cfg_payload = {
                            "chave": "ultimo_log_erro",
                            "valor": json.dumps(payload, ensure_ascii=False)
                        }
                        _fazer_requisicao("configuracoes", metodo="POST", dados=[cfg_payload], timeout=4)
                    except Exception:
                        pass
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def sincronizar_logs_pendentes_supabase(timeout: int = 5):
    """Envia logs de erro locais ainda não sincronizados para o Supabase."""
    try:
        from database.db import get_connection

        with get_connection() as conn:
            pendentes = conn.execute("SELECT * FROM logs_erro WHERE supabase_id IS NULL ORDER BY id ASC LIMIT 50").fetchall()
            for row in pendentes:
                r = dict(row)
                payload = {
                    "tipo": r.get("tipo", "ERRO"),
                    "modulo": r.get("modulo", ""),
                    "mensagem": str(r.get("mensagem", ""))[:500],
                    "detalhes": str(r.get("detalhes", ""))[:4000],
                    "versao_app": str(r.get("versao_app", "1.1.6"))
                }
                try:
                    resp = _fazer_requisicao("logs_erro", metodo="POST", dados=[payload], timeout=timeout)
                    if resp and len(resp) > 0:
                        supa_id = resp[0].get("id")
                        if supa_id:
                            conn.execute("UPDATE logs_erro SET supabase_id=? WHERE id=?", (supa_id, r["id"]))
                except urllib.error.HTTPError as he:
                    if he.code == 404:
                        break  # Tabela logs_erro ainda não criada no Supabase
                except Exception:
                    pass
            conn.commit()
    except Exception:
        pass


def sincronizar_tudo_com_supabase(timeout: int = 8) -> bool:
    """Executa sincronização bidirecional completa: pedidos, catálogo e logs."""
    try:
        sincronizar_pedidos_com_supabase(timeout=timeout)
        puxar_dados_do_supabase(timeout=timeout)
        sincronizar_logs_pendentes_supabase(timeout=timeout)
        return True
    except Exception as e:
        print(f"Erro na sincronização completa: {e}")
        return False
        return False
