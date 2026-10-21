# database/db.py - Conexão SQLite e operações CRUD (v2)
# =============================================================================

import sqlite3
import os
import sys
import threading

_local_conn = threading.local()
_CACHED_DB_PATH = None


def _can_write_to_dir(folder: str) -> bool:
    """Testa se o diretório permite criação, escrita e exclusão de arquivos pelo usuário atual."""
    try:
        os.makedirs(folder, exist_ok=True)
        test_file = os.path.join(folder, f".write_test_{os.getpid()}.tmp")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception:
        return False


def get_persistent_data_dir() -> str:
    """
    Retorna o diretório persistente oficial para os dados da aplicação:
    %LOCALAPPDATA%/PointLanches/data/
    """
    local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    data_dir = os.path.join(local_app_data, "PointLanches", "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_base_dir() -> str:
    """
    Retorna o diretório base persistente da aplicação para o banco SQLite.
    Garante que atualizações do software NUNCA sobrescrevam os dados existentes:
    1. Se o banco 'point_lanches.db' já existir em %LOCALAPPDATA%/PointLanches/data/, usa ele diretamente
       e NUNCA o substitui nem sobrescreve.
    2. Se NÃO existir no diretório persistente (primeira execução ou upgrade de versão legada):
       - Verifica se há banco existente na pasta legada (%LOCALAPPDATA%/Point Lanches ou pasta do executável)
         e migra com segurança para o novo diretório sem perda de pedidos ou produtos.
       - Se for instalação limpa nova, cria o diretório para que init_db() crie o schema inicial.
    """
    # Em modo de desenvolvimento (não compilado), se houver banco na raiz do projeto, utiliza ele
    if not getattr(sys, "frozen", False):
        dev_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if os.path.isfile(os.path.join(dev_dir, "point_lanches.db")):
            return dev_dir

    data_dir = get_persistent_data_dir()
    target_db = os.path.join(data_dir, "point_lanches.db")

    # REGRA CRÍTICA: Se o banco já existe no diretório persistente, NUNCA substitua!
    if os.path.isfile(target_db):
        return data_dir

    # Se ainda não existe no diretório persistente, busca bases de dados legadas para migrar
    candidatos_legados = [
        # a) %LOCALAPPDATA%/Point Lanches/point_lanches.db (usado em v1.0.1 a v1.0.4)
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Point Lanches", "point_lanches.db"),
        # b) Pasta do executável (modo portátil legado)
        os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "point_lanches.db") if getattr(sys, "frozen", False) else "",
    ]

    for legado in candidatos_legados:
        if legado and os.path.isfile(legado):
            try:
                import shutil
                shutil.copy2(legado, target_db)
                break
            except Exception:
                pass

    return data_dir


def get_resource_path(relative_path: str = "") -> str:
    """
    Retorna o caminho de recursos empacotados (assets, imagens, temas):
    - Se empacotado pelo PyInstaller, aponta para sys._MEIPASS.
    - Se em desenvolvimento, aponta para a raiz do projeto.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path) if relative_path else base


def get_db_path() -> str:
    global _CACHED_DB_PATH
    if _CACHED_DB_PATH is None:
        _CACHED_DB_PATH = os.path.join(get_base_dir(), "point_lanches.db")
    return _CACHED_DB_PATH


DB_PATH = get_db_path()


def get_connection():
    """
    Retorna conexão SQLite reutilizável por thread com PRAGMAs de alta performance:
    - WAL Mode + synchronous NORMAL
    - 64MB Cache de memória RAM
    - Temp store em memória
    - Reuso transparente de conexão eliminando centenas de I/O de abertura/fechamento de arquivo.
    """
    conn = getattr(_local_conn, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            conn = None

    db_file = get_db_path()
    conn = sqlite3.connect(db_file, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-64000;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")
    _local_conn.conn = conn
    return conn


# ── Schema Padrão e Retrocompatibilidade ──────────────────────────────────────

SCHEMA_TABELAS_PADRAO = {
    "categorias": """
        CREATE TABLE IF NOT EXISTS categorias (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nome      TEXT NOT NULL UNIQUE,
            ordem     INTEGER DEFAULT 0,
            eh_bebida INTEGER DEFAULT 0
        )
    """,
    "produtos": """
        CREATE TABLE IF NOT EXISTS produtos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria_id INTEGER NOT NULL REFERENCES categorias(id),
            nome         TEXT NOT NULL,
            descricao    TEXT DEFAULT '',
            preco        REAL NOT NULL,
            ativo        INTEGER DEFAULT 1
        )
    """,
    "adicionais": """
        CREATE TABLE IF NOT EXISTS adicionais (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            nome  TEXT NOT NULL,
            preco REAL NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    """,
    "taxas_entrega": """
        CREATE TABLE IF NOT EXISTS taxas_entrega (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            valor REAL NOT NULL,
            label TEXT NOT NULL,
            ativo INTEGER DEFAULT 1,
            ordem INTEGER DEFAULT 0
        )
    """,
    "pedidos": """
        CREATE TABLE IF NOT EXISTS pedidos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            numero          INTEGER NOT NULL,
            cliente_nome    TEXT DEFAULT '',
            cliente_fone    TEXT DEFAULT '',
            endereco_rua    TEXT DEFAULT '',
            endereco_num    TEXT DEFAULT '',
            endereco_comp   TEXT DEFAULT '',
            endereco_bairro TEXT DEFAULT '',
            endereco_ref    TEXT DEFAULT '',
            subtotal        REAL DEFAULT 0,
            taxa_entrega    REAL DEFAULT 0,
            total           REAL DEFAULT 0,
            forma_pgto      TEXT DEFAULT '',
            valor_pago      REAL DEFAULT 0,
            troco           REAL DEFAULT 0,
            status          TEXT DEFAULT 'fechado',
            criado_em       TEXT DEFAULT (datetime('now','localtime')),
            supabase_id     INTEGER DEFAULT NULL
        )
    """,
    "itens_pedido": """
        CREATE TABLE IF NOT EXISTS itens_pedido (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id  INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
            produto_id INTEGER REFERENCES produtos(id),
            nome       TEXT NOT NULL,
            preco_unit REAL NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 1,
            observacao TEXT DEFAULT '',
            categoria  TEXT DEFAULT ''
        )
    """,
    "configuracoes": """
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """,
    "observacoes_padrao": """
        CREATE TABLE IF NOT EXISTS observacoes_padrao (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            texto TEXT NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    """,
    "ruas": """
        CREATE TABLE IF NOT EXISTS ruas (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            nome   TEXT NOT NULL UNIQUE,
            bairro TEXT DEFAULT '',
            taxa   REAL DEFAULT 0.0,
            ativo  INTEGER DEFAULT 1
        )
    """,
    "insumos": """
        CREATE TABLE IF NOT EXISTS insumos (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nome           TEXT NOT NULL,
            unidade_medida TEXT NOT NULL,
            custo_unitario REAL NOT NULL DEFAULT 0.0,
            estoque_atual  REAL NOT NULL DEFAULT 0.0,
            ativo          INTEGER DEFAULT 1
        )
    """,
    "movimentacoes_insumos": """
        CREATE TABLE IF NOT EXISTS movimentacoes_insumos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            insumo_id   INTEGER NOT NULL REFERENCES insumos(id),
            tipo        TEXT NOT NULL,
            quantidade  REAL NOT NULL,
            valor_total REAL NOT NULL,
            data        TEXT NOT NULL
        )
    """,
    "historico_enderecos": """
        CREATE TABLE IF NOT EXISTS historico_enderecos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            rua           TEXT NOT NULL COLLATE NOCASE,
            numero        TEXT NOT NULL COLLATE NOCASE,
            bairro        TEXT DEFAULT '',
            taxa_frete    REAL NOT NULL DEFAULT 0.0,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rua, numero)
        )
    """,
    "logs_erro": """
        CREATE TABLE IF NOT EXISTS logs_erro (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora   TEXT DEFAULT (datetime('now', 'localtime')),
            tipo        TEXT DEFAULT 'ERRO',
            modulo      TEXT DEFAULT '',
            mensagem    TEXT NOT NULL,
            detalhes    TEXT DEFAULT '',
            versao_app  TEXT DEFAULT '1.1.6',
            supabase_id INTEGER DEFAULT NULL
        )
    """
}

COLUNAS_TABELAS_PADRAO = {
    "categorias": {
        "ordem": "INTEGER DEFAULT 0",
        "eh_bebida": "INTEGER DEFAULT 0",
    },
    "taxas_entrega": {
        "ordem": "INTEGER DEFAULT 0",
        "ativo": "INTEGER DEFAULT 1",
    },
    "itens_pedido": {
        "categoria": "TEXT DEFAULT ''",
        "observacao": "TEXT DEFAULT ''",
    },
    "pedidos": {
        "endereco_bairro": "TEXT DEFAULT ''",
        "endereco_ref": "TEXT DEFAULT ''",
        "endereco_comp": "TEXT DEFAULT ''",
        "valor_pago": "REAL DEFAULT 0",
        "troco": "REAL DEFAULT 0",
        "status": "TEXT DEFAULT 'fechado'",
        "criado_em": "TEXT DEFAULT (datetime('now','localtime'))",
        "supabase_id": "INTEGER DEFAULT NULL",
    },
    "ruas": {
        "bairro": "TEXT DEFAULT ''",
        "taxa": "REAL DEFAULT 0.0",
        "ativo": "INTEGER DEFAULT 1",
    },
    "produtos": {
        "descricao": "TEXT DEFAULT ''",
        "ativo": "INTEGER DEFAULT 1",
    },
    "adicionais": {
        "ativo": "INTEGER DEFAULT 1",
    },
    "observacoes_padrao": {
        "ativo": "INTEGER DEFAULT 1",
    },
    "insumos": {
        "ativo": "INTEGER DEFAULT 1",
    },
    "historico_enderecos": {
        "bairro": "TEXT DEFAULT ''",
        "taxa_frete": "REAL DEFAULT 0.0",
        "atualizado_em": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "logs_erro": {
        "tipo": "TEXT DEFAULT 'ERRO'",
        "modulo": "TEXT DEFAULT ''",
        "detalhes": "TEXT DEFAULT ''",
        "versao_app": "TEXT DEFAULT '1.1.6'",
        "supabase_id": "INTEGER DEFAULT NULL",
    }
}


def executar_migracoes_retrocompativeis(db_path: str = None) -> int:
    """
    Inspeciona o schema do banco SQLite informado (ou banco ativo) e aplica
    todas as migrações necessárias para a versão atual:
    - Cria tabelas novas ausentes em versões legadas (v1.0.2 em diante).
    - Inspeciona PRAGMA table_info e adiciona colunas faltantes via ALTER TABLE.
    - Popula tabelas essenciais (ruas, observações, histórico) caso vazias.
    - Preserva integralmente todos os registros existentes de pedidos, clientes e produtos.
    """
    alvo = db_path or get_db_path()
    conn = sqlite3.connect(alvo)
    conn.row_factory = sqlite3.Row
    migracoes_aplicadas = 0

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=OFF")

        # 1. Criação de tabelas novas ausentes
        for nome_tab, ddl in SCHEMA_TABELAS_PADRAO.items():
            conn.execute(ddl)

        # 2. Inspecionar e adicionar colunas faltantes
        for nome_tab, cols in COLUNAS_TABELAS_PADRAO.items():
            try:
                existentes = {r["name"].lower() for r in conn.execute(f"PRAGMA table_info({nome_tab})").fetchall()}
                for col_nome, col_def in cols.items():
                    if col_nome.lower() not in existentes:
                        conn.execute(f"ALTER TABLE {nome_tab} ADD COLUMN {col_nome} {col_def}")
                        migracoes_aplicadas += 1
            except Exception:
                pass

        # 3. Backfill inteligente do histórico de endereços se tabela vazia
        try:
            cnt_hist = conn.execute("SELECT COUNT(*) FROM historico_enderecos").fetchone()[0]
            if cnt_hist == 0:
                conn.execute("""
                    INSERT OR IGNORE INTO historico_enderecos (rua, numero, bairro, taxa_frete, atualizado_em)
                    SELECT endereco_rua, endereco_num, endereco_bairro, taxa_entrega, criado_em
                    FROM pedidos
                    WHERE endereco_rua != '' AND endereco_num != '' AND taxa_entrega > 0
                    ORDER BY id ASC
                """)
        except Exception:
            pass

        # 4. População de ruas padrão caso tabela vazia
        try:
            cnt_ruas = conn.execute("SELECT COUNT(*) FROM ruas").fetchone()[0]
            if cnt_ruas == 0:
                from config import RUAS_DOIS_IRMAOS
                for r in RUAS_DOIS_IRMAOS:
                    conn.execute("INSERT OR IGNORE INTO ruas (nome, ativo) VALUES (?, 1)", (r,))
        except Exception:
            pass

        # 5. População de observações padrão caso tabela vazia
        try:
            cnt_obs = conn.execute("SELECT COUNT(*) FROM observacoes_padrao").fetchone()[0]
            if cnt_obs == 0:
                from database.seed import OBS_PADRAO
                for texto in OBS_PADRAO:
                    conn.execute("INSERT INTO observacoes_padrao (texto, ativo) VALUES (?, 1)", (texto,))
        except Exception:
            pass

        # 6. Índices de alta performance para velocidade máxima nas consultas
        try:
            indices = [
                "CREATE INDEX IF NOT EXISTS idx_produtos_cat_ativo ON produtos(categoria_id, ativo);",
                "CREATE INDEX IF NOT EXISTS idx_pedidos_numero ON pedidos(numero);",
                "CREATE INDEX IF NOT EXISTS idx_pedidos_criado_em ON pedidos(criado_em);",
                "CREATE INDEX IF NOT EXISTS idx_itens_pedido_id ON itens_pedido(pedido_id);",
                "CREATE INDEX IF NOT EXISTS idx_ruas_ativo_nome ON ruas(ativo, nome);",
                "CREATE INDEX IF NOT EXISTS idx_hist_end_rua_num ON historico_enderecos(rua, numero);",
                "CREATE INDEX IF NOT EXISTS idx_taxas_ordem ON taxas_entrega(ordem, ativo);",
                "CREATE INDEX IF NOT EXISTS idx_obs_ativo ON observacoes_padrao(ativo);",
                "CREATE INDEX IF NOT EXISTS idx_pedidos_supabase_id ON pedidos(supabase_id);",
                "CREATE INDEX IF NOT EXISTS idx_logs_erro_data ON logs_erro(data_hora);"
            ]
            for idx_sql in indices:
                conn.execute(idx_sql)
        except Exception:
            pass

        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute("PRAGMA wal_checkpoint(FULL)")
        except Exception:
            pass
    finally:
        conn.close()

    return migracoes_aplicadas


def init_db():
    """Cria/migra tabelas com auto-upgrade retrocompatível."""
    executar_migracoes_retrocompativeis(get_db_path())


def exportar_banco_sqlite(caminho_destino: str) -> str:
    """
    Exporta uma cópia consistente do banco SQLite ativo.
    Garante checkpoint WAL prévio e cópia segura via SQLite backup API.
    """
    if not caminho_destino:
        raise ValueError("Caminho de destino não especificado.")

    os.makedirs(os.path.dirname(os.path.abspath(caminho_destino)), exist_ok=True)

    with get_connection() as conn:
        try:
            conn.execute("PRAGMA wal_checkpoint(FULL)")
        except Exception:
            pass

        dest_conn = sqlite3.connect(caminho_destino)
        try:
            conn.backup(dest_conn)
            dest_conn.commit()
        finally:
            dest_conn.close()

    if not os.path.exists(caminho_destino) or os.path.getsize(caminho_destino) == 0:
        raise RuntimeError("Arquivo de backup gerado está vazio ou não foi criado.")

    return caminho_destino


def importar_banco_sqlite(caminho_origem: str) -> tuple[bool, str]:
    """
    Importa e migra retrocompativelmente um banco de dados SQLite (.db ou .sqlite).
    1. Valida integridade prévia do arquivo selecionado.
    2. Cria cópia de segurança point_lanches.db.bak do banco ativo.
    3. Substitui o conteúdo do banco ativo pelo banco importado via backup API.
    4. Executa migrações retrocompatíveis adaptando o schema antigo para o atual.
    5. Em caso de falha, restaura automaticamente o backup preventivo .bak.
    """
    if not os.path.exists(caminho_origem):
        return False, f"Arquivo não encontrado: {caminho_origem}"

    # 1. Validação de integridade do arquivo importado
    try:
        test_conn = sqlite3.connect(caminho_origem)
        test_conn.row_factory = sqlite3.Row
        check = test_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            test_conn.close()
            return False, f"O arquivo selecionado está corrompido: PRAGMA integrity_check retornou '{check}'."

        tabelas = [r[0] for r in test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        test_conn.close()

        tabelas_esperadas = {"pedidos", "produtos", "categorias", "configuracoes"}
        if not any(t in tabelas for t in tabelas_esperadas):
            return False, "O arquivo selecionado não é um banco de dados reconhecido do Point Lanches."
    except Exception as e:
        return False, f"Arquivo inválido ou ilegível: {str(e)}"

    db_path = get_db_path()
    bak_path = db_path + ".bak"

    # 2. Cópia preventiva de segurança (.bak) do banco ativo
    try:
        with get_connection() as active_conn:
            try:
                active_conn.execute("PRAGMA wal_checkpoint(FULL)")
            except Exception:
                pass
            bak_conn = sqlite3.connect(bak_path)
            try:
                active_conn.backup(bak_conn)
                bak_conn.commit()
            finally:
                bak_conn.close()
    except Exception as e:
        try:
            if os.path.exists(db_path):
                import shutil
                shutil.copy2(db_path, bak_path)
        except Exception:
            pass

    # 3. Aplicar conteúdo do banco importado sobre o banco ativo
    try:
        src_conn = sqlite3.connect(caminho_origem)
        with get_connection() as active_conn:
            src_conn.backup(active_conn)
            active_conn.commit()
        src_conn.close()

        # 4. Executar migrações retrocompatíveis automáticas (auto-upgrade)
        executar_migracoes_retrocompativeis(db_path)

        # 5. Notificar ouvintes e caches em memória
        _notificar_ruas_modificadas()

        return True, "Backup importado com sucesso! A estrutura do banco foi atualizada para a versão atual mantendo todos os seus registros anteriores."
    except Exception as e:
        # Reversão / Restauração automática do backup preventivo .bak
        try:
            if os.path.exists(bak_path):
                bak_conn = sqlite3.connect(bak_path)
                with get_connection() as active_conn:
                    bak_conn.backup(active_conn)
                    active_conn.commit()
                bak_conn.close()
        except Exception:
            pass

        return False, f"Falha ao importar banco: arquivo inválido ou bloqueado por outro processo. Detalhes: {str(e)}"


# ── Produtos e Categorias ─────────────────────────────────────────────────────

def listar_categorias(incluir_extras=False):
    with get_connection() as conn:
        try:
            conn.execute("ALTER TABLE categorias ADD COLUMN ordem INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE categorias ADD COLUMN eh_bebida INTEGER DEFAULT 0")
        except Exception:
            pass
        q = "SELECT * FROM categorias"
        if not incluir_extras:
            q += " WHERE LOWER(nome) != 'extras'"
        try:
            q_order = q + " ORDER BY ordem, id"
            return [dict(r) for r in conn.execute(q_order).fetchall()]
        except sqlite3.OperationalError:
            return [dict(r) for r in conn.execute(q + " ORDER BY id").fetchall()]


def listar_produtos(categoria_id=None):
    with get_connection() as conn:
        if categoria_id:
            rows = conn.execute(
                "SELECT p.*, c.nome as categoria, COALESCE(c.eh_bebida, 0) as eh_bebida FROM produtos p "
                "JOIN categorias c ON c.id = p.categoria_id "
                "WHERE p.categoria_id=? AND p.ativo=1 ORDER BY p.nome",
                (categoria_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT p.*, c.nome as categoria, COALESCE(c.eh_bebida, 0) as eh_bebida FROM produtos p "
                "JOIN categorias c ON c.id = p.categoria_id "
                "WHERE p.ativo=1 ORDER BY c.id, p.nome"
            ).fetchall()
        return [dict(r) for r in rows]


def adicionar_produto(categoria_id, nome, descricao, preco):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO produtos (categoria_id, nome, descricao, preco) VALUES (?,?,?,?)",
            (categoria_id, nome, descricao, preco)
        )
        prod_id = cur.lastrowid

    if prod_id:
        try:
            from services.supabase_sync import sincronizar_item_supabase_async
            sincronizar_item_supabase_async("produtos", {
                "id": prod_id, "categoria_id": categoria_id, "nome": nome,
                "descricao": descricao, "preco": preco, "ativo": 1
            }, metodo="POST")
        except Exception:
            pass
    return prod_id


def atualizar_produto(produto_id, nome, descricao, preco, categoria_id, ativo=1):
    with get_connection() as conn:
        conn.execute(
            "UPDATE produtos SET nome=?, descricao=?, preco=?, categoria_id=?, ativo=? WHERE id=?",
            (nome, descricao, preco, categoria_id, ativo, produto_id)
        )
    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        sincronizar_item_supabase_async("produtos", {
            "nome": nome, "descricao": descricao, "preco": preco,
            "categoria_id": categoria_id, "ativo": ativo
        }, metodo="PATCH", query_params=f"id=eq.{produto_id}")
    except Exception:
        pass


def remover_produto(produto_id):
    with get_connection() as conn:
        conn.execute("UPDATE produtos SET ativo=0 WHERE id=?", (produto_id,))
    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        sincronizar_item_supabase_async("produtos", {"ativo": 0}, metodo="PATCH", query_params=f"id=eq.{produto_id}")
    except Exception:
        pass


def _sincronizar_mapa_categorias_bebidas(conn=None):
    """
    Sincroniza o mapa de categorias de bebidas na tabela global 'configuracoes'
    tanto localmente no SQLite quanto na nuvem Supabase via upsert.
    Isso contorna a limitação de schema da tabela remota 'categorias' (sem coluna eh_bebida)
    e propaga a classificação para todos os terminais.
    """
    import json
    def _exec(c):
        mapa = {}
        for r in c.execute("SELECT id, eh_bebida FROM categorias").fetchall():
            mapa[str(r["id"])] = int(r["eh_bebida"] or 0)
        mapa_json = json.dumps(mapa)
        c.execute("INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES ('categorias_bebidas', ?)", (mapa_json,))
        return mapa_json

    mapa_json = None
    if conn is not None:
        mapa_json = _exec(conn)
    else:
        with get_connection() as c:
            mapa_json = _exec(c)
            c.commit()

    if mapa_json is not None:
        try:
            from services.supabase_sync import sincronizar_item_supabase_async
            sincronizar_item_supabase_async(
                "configuracoes",
                {"chave": "categorias_bebidas", "valor": mapa_json},
                metodo="POST",
                query_params="on_conflict=chave",
                prefer="resolution=merge-duplicates,return=representation"
            )
        except Exception:
            pass


def adicionar_categoria(nome, ordem=0, eh_bebida=0):
    with get_connection() as conn:
        cur = conn.execute("INSERT OR IGNORE INTO categorias (nome, ordem, eh_bebida) VALUES (?, ?, ?)", (nome, ordem, int(eh_bebida)))
        cat_id = cur.lastrowid
        if not cat_id or cat_id == 0:
            r = conn.execute("SELECT id FROM categorias WHERE nome=?", (nome,)).fetchone()
            cat_id = r["id"] if r else None
        conn.commit()

    if cat_id:
        try:
            from services.supabase_sync import sincronizar_item_supabase_async
            # Supabase 'categorias' possui apenas (id, nome, ordem). NÃO enviar eh_bebida para evitar HTTP 400
            sincronizar_item_supabase_async("categorias", {"id": cat_id, "nome": nome, "ordem": ordem}, metodo="POST")
        except Exception:
            pass
        if eh_bebida:
            _sincronizar_mapa_categorias_bebidas()
    return cat_id


def atualizar_categoria(categoria_id, novo_nome, nova_ordem=None, eh_bebida=None):
    with get_connection() as conn:
        campos = ["nome=?"]
        params = [novo_nome]
        payload = {"nome": novo_nome}
        if nova_ordem is not None:
            campos.append("ordem=?")
            params.append(nova_ordem)
            payload["ordem"] = nova_ordem
        if eh_bebida is not None:
            campos.append("eh_bebida=?")
            params.append(int(eh_bebida))
            # Supabase 'categorias' NÃO possui coluna eh_bebida. Não adicionar ao payload de 'categorias'.
        params.append(categoria_id)
        sql = f"UPDATE categorias SET {', '.join(campos)} WHERE id=?"
        conn.execute(sql, tuple(params))
        conn.commit()

    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        # Sincroniza nome e ordem com a tabela categorias no Supabase
        sincronizar_item_supabase_async("categorias", payload, metodo="PATCH", query_params=f"id=eq.{categoria_id}")
    except Exception:
        pass

    if eh_bebida is not None:
        _sincronizar_mapa_categorias_bebidas()


def atualizar_categoria_eh_bebida(categoria_id: int, eh_bebida: int):
    """Atualiza se a categoria é de bebidas (1) ou lanches/comida (0) e propaga para todos os terminais."""
    with get_connection() as conn:
        conn.execute("UPDATE categorias SET eh_bebida=? WHERE id=?", (int(eh_bebida), categoria_id))
        conn.commit()
    _sincronizar_mapa_categorias_bebidas()


def contar_produtos_por_categoria(categoria_id: int, apenas_ativos: bool = False) -> int:
    with get_connection() as conn:
        q = "SELECT COUNT(*) FROM produtos WHERE categoria_id=?"
        if apenas_ativos:
            q += " AND ativo=1"
        row = conn.execute(q, (categoria_id,)).fetchone()
        return row[0] if row else 0


def remover_categoria(categoria_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM categorias WHERE id=?", (categoria_id,))
        conn.commit()
    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        sincronizar_item_supabase_async("categorias", None, metodo="DELETE", query_params=f"id=eq.{categoria_id}")
    except Exception:
        pass
    _sincronizar_mapa_categorias_bebidas()


def get_categoria_por_nome(nome):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM categorias WHERE nome=?", (nome,)
        ).fetchone()
        return row["id"] if row else None


# ── Adicionais ────────────────────────────────────────────────────────────────

def listar_adicionais(apenas_ativos=True):
    with get_connection() as conn:
        q = "SELECT * FROM adicionais"
        if apenas_ativos:
            q += " WHERE ativo=1"
        q += " ORDER BY nome"
        return [dict(r) for r in conn.execute(q).fetchall()]


def adicionar_adicional(nome, preco):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO adicionais (nome, preco) VALUES (?,?)",
            (nome, preco)
        )
        adic_id = cur.lastrowid
    if adic_id:
        try:
            from services.supabase_sync import sincronizar_item_supabase_async
            sincronizar_item_supabase_async("adicionais", {"id": adic_id, "nome": nome, "preco": preco, "ativo": 1}, metodo="POST")
        except Exception:
            pass
    return adic_id


def atualizar_adicional(adicional_id, nome, preco, ativo=1):
    with get_connection() as conn:
        conn.execute(
            "UPDATE adicionais SET nome=?, preco=?, ativo=? WHERE id=?",
            (nome, preco, ativo, adicional_id)
        )
    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        sincronizar_item_supabase_async("adicionais", {"nome": nome, "preco": preco, "ativo": ativo}, metodo="PATCH", query_params=f"id=eq.{adicional_id}")
    except Exception:
        pass


def remover_adicional(adicional_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM adicionais WHERE id=?", (adicional_id,))
    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        sincronizar_item_supabase_async("adicionais", None, metodo="DELETE", query_params=f"id=eq.{adicional_id}")
    except Exception:
        pass


# ── Taxas de Entrega ──────────────────────────────────────────────────────────

def listar_taxas(apenas_ativas=True):
    with get_connection() as conn:
        q = "SELECT * FROM taxas_entrega"
        if apenas_ativas:
            q += " WHERE ativo=1"
        q += " ORDER BY valor"
        return [dict(r) for r in conn.execute(q).fetchall()]


def adicionar_taxa(valor, label, ativo=1):
    ordem = int(valor * 100)
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO taxas_entrega (valor, label, ativo, ordem) VALUES (?,?,?,?)",
            (valor, label, ativo, ordem)
        )
        taxa_id = cur.lastrowid
    if taxa_id:
        try:
            from services.supabase_sync import sincronizar_item_supabase_async
            sincronizar_item_supabase_async("taxas_entrega", {"id": taxa_id, "valor": valor, "label": label, "ativo": ativo, "ordem": ordem}, metodo="POST")
        except Exception:
            pass
    return taxa_id


def atualizar_taxa(taxa_id, valor, label, ativo=1):
    with get_connection() as conn:
        conn.execute(
            "UPDATE taxas_entrega SET valor=?, label=?, ativo=? WHERE id=?",
            (valor, label, ativo, taxa_id)
        )
    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        sincronizar_item_supabase_async("taxas_entrega", {"valor": valor, "label": label, "ativo": ativo}, metodo="PATCH", query_params=f"id=eq.{taxa_id}")
    except Exception:
        pass


def remover_taxa(taxa_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM taxas_entrega WHERE id=?", (taxa_id,))
    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        sincronizar_item_supabase_async("taxas_entrega", None, metodo="DELETE", query_params=f"id=eq.{taxa_id}")
    except Exception:
        pass


# ── Pedidos ───────────────────────────────────────────────────────────────────

def proximo_numero_pedido():
    with get_connection() as conn:
        row = conn.execute("SELECT MAX(numero) as m FROM pedidos").fetchone()
        return (row["m"] or 0) + 1


def salvar_pedido(pedido: dict, itens: list) -> int:
    numero = proximo_numero_pedido()

    # ── Auto-cadastro inteligente de ruas não mapeadas (silencioso e assíncrono à UI) ──
    rua_raw = (pedido.get("rua") or "").strip()
    bairro = (pedido.get("bairro") or "").strip()
    try:
        taxa = float(pedido.get("taxa_entrega", 0.0) or 0.0)
    except (ValueError, TypeError):
        taxa = 0.0

    if rua_raw:
        try:
            _, rua_info = cadastrar_rua_se_inedita(rua_raw, bairro=bairro, taxa=taxa)
            if rua_info and rua_info.get("nome"):
                # Padroniza a via no pedido e no cupom com formatação Title Case e acentos
                pedido["rua"] = rua_info["nome"]
        except Exception:
            pass

    # ── Gravação/Atualização no Histórico de Endereço (Rua + Número) ──
    num_raw = (pedido.get("numero") or "").strip()
    if rua_raw and num_raw:
        try:
            salvar_historico_endereco(
                rua=pedido.get("rua", rua_raw),
                numero=num_raw,
                bairro=bairro,
                taxa_frete=taxa
            )
        except Exception:
            pass

    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO pedidos
              (numero, cliente_nome, cliente_fone, endereco_rua, endereco_num,
               endereco_comp, endereco_bairro, endereco_ref,
               subtotal, taxa_entrega, total, forma_pgto, valor_pago, troco, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'fechado')
        """, (
            numero,
            pedido.get("cliente_nome", ""),
            pedido.get("cliente_fone", ""),
            pedido.get("rua", ""),
            pedido.get("numero", ""),
            pedido.get("complemento", ""),
            pedido.get("bairro", ""),
            pedido.get("referencia", ""),
            pedido.get("subtotal", 0),
            pedido.get("taxa_entrega", 0),
            pedido.get("total", 0),
            pedido.get("forma_pgto", ""),
            pedido.get("valor_pago", 0),
            pedido.get("troco", 0),
        ))
        pedido_id = cur.lastrowid
        for item in itens:
            conn.execute("""
                INSERT INTO itens_pedido
                  (pedido_id, produto_id, nome, preco_unit, quantidade, observacao, categoria)
                VALUES (?,?,?,?,?,?,?)
            """, (
                pedido_id,
                item.get("produto_id"),
                item["nome"],
                item["preco_unit"],
                item["quantidade"],
                item.get("observacao", ""),
                item.get("categoria", ""),
            ))

    # Sincronização em segundo plano com Supabase Cloud (não bloqueia a thread do caixa)
    try:
        from services.supabase_sync import enviar_pedido_supabase_async
        pedido_sync = dict(pedido)
        pedido_sync["numero_pedido"] = numero
        pedido_sync["id_local"] = pedido_id
        pedido_sync["endereco_num"] = pedido.get("numero", "")
        enviar_pedido_supabase_async(pedido_sync, itens)
    except Exception:
        pass

    return pedido_id


def listar_pedidos(limit=100):
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pedidos ORDER BY COALESCE(datetime(criado_em), criado_em) DESC, numero DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()]


def get_pedido_com_itens(pedido_id: int):
    """Retorna (pedido_dict, [itens_dict])."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM pedidos WHERE id=?", (pedido_id,)).fetchone()
        if not row:
            return None, []
        pedido = dict(row)
        itens = [dict(r) for r in conn.execute(
            "SELECT * FROM itens_pedido WHERE pedido_id=?", (pedido_id,)
        ).fetchall()]
    return pedido, itens


def excluir_pedido(pedido_id: int) -> bool:
    """Exclui um pedido e seus itens associados (localmente e no Supabase)."""
    supabase_id = None
    with get_connection() as conn:
        try:
            row = conn.execute("SELECT supabase_id FROM pedidos WHERE id=?", (pedido_id,)).fetchone()
            if row and "supabase_id" in row.keys():
                supabase_id = row["supabase_id"]
        except Exception:
            pass
        conn.execute("DELETE FROM itens_pedido WHERE pedido_id=?", (pedido_id,))
        conn.execute("DELETE FROM pedidos WHERE id=?", (pedido_id,))

    if supabase_id:
        try:
            from services.supabase_sync import sincronizar_item_supabase_async
            sincronizar_item_supabase_async("itens_pedido", dados=None, metodo="DELETE", query_params=f"pedido_id=eq.{supabase_id}")
            sincronizar_item_supabase_async("pedidos", dados=None, metodo="DELETE", query_params=f"id=eq.{supabase_id}")
        except Exception:
            pass
    return True


# ── Balanço Geral e Fechamento ────────────────────────────────────────────────

def calcular_balanco_mensal(mes: int = None, ano: int = None) -> dict:
    """
    Calcula o faturamento e balanço consolidado de um mês/ano específico ou do ano completo.
    Retorna indicadores gerais, detalhamento por modalidade e estrutura
    preparada para custos/insumos futuros.
    """
    if mes and mes > 0:
        prefix = f"{ano:04d}-{mes:02d}%"
    else:
        prefix = f"{ano:04d}-%"
    with get_connection() as conn:
        pedidos = conn.execute("""
            SELECT id, numero, total, subtotal, taxa_entrega, forma_pgto, criado_em
            FROM pedidos
            WHERE criado_em LIKE ?
        """, (prefix,)).fetchall()

        total_pedidos = len(pedidos)
        faturamento_total = sum(p["total"] or 0.0 for p in pedidos)
        total_taxas = sum(p["taxa_entrega"] or 0.0 for p in pedidos)
        ticket_medio = (faturamento_total / total_pedidos) if total_pedidos > 0 else 0.0

        modalidades = {
            "PIX": {"total": 0.0, "qtd": 0},
            "Dinheiro": {"total": 0.0, "qtd": 0},
            "Cartão de Débito": {"total": 0.0, "qtd": 0},
            "Cartão de Crédito": {"total": 0.0, "qtd": 0},
            "Outros": {"total": 0.0, "qtd": 0},
        }

        for p in pedidos:
            fp = (p["forma_pgto"] or "").upper()
            val = p["total"] or 0.0
            if "PIX" in fp:
                modalidades["PIX"]["total"] += val
                modalidades["PIX"]["qtd"] += 1
            elif "DINHEIRO" in fp:
                modalidades["Dinheiro"]["total"] += val
                modalidades["Dinheiro"]["qtd"] += 1
            elif "DÉBITO" in fp or "DEBITO" in fp:
                modalidades["Cartão de Débito"]["total"] += val
                modalidades["Cartão de Débito"]["qtd"] += 1
            elif "CRÉDITO" in fp or "CREDITO" in fp or "CARTÃO" in fp or "CARTAO" in fp:
                modalidades["Cartão de Crédito"]["total"] += val
                modalidades["Cartão de Crédito"]["qtd"] += 1
            else:
                modalidades["Outros"]["total"] += val
                modalidades["Outros"]["qtd"] += 1

        # Custos de insumos (estrutura de backend preparada para insumos futuros)
        row_custo = conn.execute("""
            SELECT COALESCE(SUM(valor_total), 0.0) as custo
            FROM movimentacoes_insumos
            WHERE tipo='entrada' AND data LIKE ?
        """, (prefix,)).fetchone()
        custo_insumos = float(row_custo["custo"]) if row_custo else 0.0

        lucro_bruto = faturamento_total - custo_insumos

        return {
            "mes": mes,
            "ano": ano,
            "total_pedidos": total_pedidos,
            "faturamento_total": faturamento_total,
            "total_taxas": total_taxas,
            "ticket_medio": ticket_medio,
            "custo_insumos": custo_insumos,
            "lucro_bruto": lucro_bruto,
            "modalidades": modalidades,
        }


def ranking_produtos_vendidos(mes: int = None, ano: int = None) -> list[dict]:
    """
    Retorna o ranking de produtos vendidos no período (mês/ano ou ano completo),
    ordenado decrescentemente pela quantidade total vendida.
    """
    if mes and mes > 0:
        prefix = f"{ano:04d}-{mes:02d}%"
    else:
        prefix = f"{ano:04d}-%"

    with get_connection() as conn:
        q = """
            SELECT 
                ip.nome as produto_nome,
                CASE 
                    WHEN c.nome IS NOT NULL AND c.nome != '' THEN c.nome
                    WHEN ip.categoria IS NOT NULL AND ip.categoria != '' THEN ip.categoria
                    ELSE 'Lanches'
                END as categoria_nome,
                SUM(ip.quantidade) as total_qtd,
                SUM(ip.quantidade * ip.preco_unit) as total_valor
            FROM itens_pedido ip
            JOIN pedidos p ON ip.pedido_id = p.id
            LEFT JOIN produtos prod ON (ip.produto_id = prod.id OR LOWER(ip.nome) = LOWER(prod.nome))
            LEFT JOIN categorias c ON prod.categoria_id = c.id
            WHERE p.criado_em LIKE ? AND (p.status IS NULL OR p.status != 'cancelado')
            GROUP BY ip.nome
            ORDER BY total_qtd DESC, total_valor DESC
        """
        rows = conn.execute(q, (prefix,)).fetchall()
        return [dict(r) for r in rows]


def obter_estatisticas_pico(mes: int = None, ano: int = None) -> dict:
    """
    Calcula as estatísticas de horários e dias de maior pico de pedidos
    para o período informado (mês/ano ou ano completo).
    Retorna métricas consolidadas com ordenação e percentuais de participação.
    """
    if mes and mes > 0:
        prefix = f"{ano:04d}-{mes:02d}%"
    else:
        prefix = f"{ano:04d}-%"

    with get_connection() as conn:
        # Total de pedidos e faturamento no período
        row_tot = conn.execute("""
            SELECT COUNT(*) as tot, COALESCE(SUM(total), 0.0) as fat
            FROM pedidos
            WHERE criado_em LIKE ? AND (status IS NULL OR status != 'cancelado')
        """, (prefix,)).fetchone()
        tot_ped = row_tot["tot"] if row_tot else 0
        fat_ped = float(row_tot["fat"]) if row_tot else 0.0

        # 1. Picos por Horário do Dia (00h às 23h)
        rows_horas = conn.execute("""
            SELECT 
                strftime('%H', criado_em) as hora,
                COUNT(*) as qtd,
                COALESCE(SUM(total), 0.0) as total
            FROM pedidos
            WHERE criado_em LIKE ? AND (status IS NULL OR status != 'cancelado')
            GROUP BY strftime('%H', criado_em)
            ORDER BY hora ASC
        """, (prefix,)).fetchall()

        horas_dict = {f"{h:02d}": {"qtd": 0, "total": 0.0} for h in range(24)}
        for r in rows_horas:
            h_str = r["hora"]
            if h_str in horas_dict:
                horas_dict[h_str] = {"qtd": int(r["qtd"]), "total": float(r["total"])}

        horas_com_pedidos = {h: v for h, v in horas_dict.items() if v["qtd"] > 0}
        if not horas_com_pedidos:
            horas_para_exibir = [f"{h:02d}" for h in range(11, 24)]
        else:
            min_h = min(int(h) for h in horas_com_pedidos.keys())
            max_h = max(int(h) for h in horas_com_pedidos.keys())
            min_h = max(0, min(min_h, 17))
            max_h = min(23, max(max_h, 23))
            horas_para_exibir = [f"{h:02d}" for h in range(min_h, max_h + 1)]

        lista_horas = []
        max_qtd_hora = 0
        hora_pico = None
        for h_str in horas_para_exibir:
            d = horas_dict[h_str]
            h_int = int(h_str)
            h_prox = (h_int + 1) % 24
            rotulo = f"{h_str}:00 às {h_prox:02d}:00"
            part = (d["qtd"] / tot_ped * 100) if tot_ped > 0 else 0.0
            item = {
                "hora": h_str,
                "rotulo": rotulo,
                "qtd": d["qtd"],
                "total": d["total"],
                "part": part
            }
            lista_horas.append(item)
            if d["qtd"] > max_qtd_hora:
                max_qtd_hora = d["qtd"]
                hora_pico = item

        # 2. Picos por Dia da Semana (0=Dom, 1=Seg, 2=Ter, 3=Qua, 4=Qui, 5=Sex, 6=Sáb)
        nomes_dias = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"]
        icones_dias = ["☀️", "💼", "📋", "🍔", "🛵", "🍻", "🎉"]
        dias_dict = {i: {"qtd": 0, "total": 0.0} for i in range(7)}

        rows_dias = conn.execute("""
            SELECT 
                strftime('%w', criado_em) as dia_sem,
                COUNT(*) as qtd,
                COALESCE(SUM(total), 0.0) as total
            FROM pedidos
            WHERE criado_em LIKE ? AND (status IS NULL OR status != 'cancelado')
            GROUP BY strftime('%w', criado_em)
        """, (prefix,)).fetchall()

        for r in rows_dias:
            try:
                d_idx = int(r["dia_sem"])
                if d_idx in dias_dict:
                    dias_dict[d_idx] = {"qtd": int(r["qtd"]), "total": float(r["total"])}
            except Exception:
                pass

        lista_dias = []
        max_qtd_dia = 0
        dia_pico = None
        for i in range(7):
            d = dias_dict[i]
            part = (d["qtd"] / tot_ped * 100) if tot_ped > 0 else 0.0
            item = {
                "dia_idx": i,
                "nome": nomes_dias[i],
                "icone": icones_dias[i],
                "qtd": d["qtd"],
                "total": d["total"],
                "part": part
            }
            lista_dias.append(item)
            if d["qtd"] > max_qtd_dia:
                max_qtd_dia = d["qtd"]
                dia_pico = item

        # 3. Evolução Diária (se mensal) ou Mensal (se anual)
        if mes and mes > 0:
            rows_cal = conn.execute("""
                SELECT 
                    strftime('%d', criado_em) as chave,
                    COUNT(*) as qtd,
                    COALESCE(SUM(total), 0.0) as total
                FROM pedidos
                WHERE criado_em LIKE ? AND (status IS NULL OR status != 'cancelado')
                GROUP BY strftime('%d', criado_em)
                ORDER BY chave ASC
            """, (prefix,)).fetchall()
            lista_periodo = [
                {
                    "rotulo": f"Dia {r['chave']}",
                    "qtd": int(r["qtd"]),
                    "total": float(r["total"]),
                    "part": (int(r["qtd"]) / tot_ped * 100) if tot_ped > 0 else 0.0
                }
                for r in rows_cal
            ]
        else:
            meses_nomes_curtos = [
                "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
            ]
            rows_cal = conn.execute("""
                SELECT 
                    strftime('%m', criado_em) as chave,
                    COUNT(*) as qtd,
                    COALESCE(SUM(total), 0.0) as total
                FROM pedidos
                WHERE criado_em LIKE ? AND (status IS NULL OR status != 'cancelado')
                GROUP BY strftime('%m', criado_em)
                ORDER BY chave ASC
            """, (prefix,)).fetchall()
            cal_dict = {f"{m:02d}": {"qtd": 0, "total": 0.0} for m in range(1, 13)}
            for r in rows_cal:
                k = r["chave"]
                if k in cal_dict:
                    cal_dict[k] = {"qtd": int(r["qtd"]), "total": float(r["total"])}
            lista_periodo = []
            for m in range(1, 13):
                k = f"{m:02d}"
                d = cal_dict[k]
                part = (d["qtd"] / tot_ped * 100) if tot_ped > 0 else 0.0
                lista_periodo.append({
                    "rotulo": f"{meses_nomes_curtos[m-1]}/{ano}",
                    "qtd": d["qtd"],
                    "total": d["total"],
                    "part": part
                })

        return {
            "tot_pedidos": tot_ped,
            "fat_total": fat_ped,
            "horas": lista_horas,
            "hora_pico": hora_pico,
            "dias_semana": lista_dias,
            "dia_pico": dia_pico,
            "periodo": lista_periodo,
            "is_mensal": bool(mes and mes > 0)
        }



# ── Configurações ─────────────────────────────────────────────────────────────

def get_config(chave, default=None):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT valor FROM configuracoes WHERE chave=?", (chave,)
        ).fetchone()
        return row["valor"] if row else default


def set_config(chave, valor):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?,?)",
            (chave, str(valor))
        )


# ── Observações Rápidas ───────────────────────────────────────────────────────

def listar_observacoes_padrao(apenas_ativas=True):
    with get_connection() as conn:
        q = "SELECT * FROM observacoes_padrao"
        if apenas_ativas:
            q += " WHERE ativo=1"
        q += " ORDER BY texto"
        return [dict(r) for r in conn.execute(q).fetchall()]


def adicionar_observacao_padrao(texto):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO observacoes_padrao (texto) VALUES (?)",
            (texto,)
        )
        obs_id = cur.lastrowid
    if obs_id:
        try:
            from services.supabase_sync import sincronizar_item_supabase_async
            sincronizar_item_supabase_async("observacoes_padrao", {"id": obs_id, "texto": texto, "ativo": 1}, metodo="POST")
        except Exception:
            pass
    return obs_id


def atualizar_observacao_padrao(obs_id, texto, ativo=1):
    with get_connection() as conn:
        conn.execute(
            "UPDATE observacoes_padrao SET texto=?, ativo=? WHERE id=?",
            (texto, ativo, obs_id)
        )
    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        sincronizar_item_supabase_async("observacoes_padrao", {"texto": texto, "ativo": ativo}, metodo="PATCH", query_params=f"id=eq.{obs_id}")
    except Exception:
        pass


def remover_observacao_padrao(obs_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM observacoes_padrao WHERE id=?", (obs_id,))
    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        sincronizar_item_supabase_async("observacoes_padrao", None, metodo="DELETE", query_params=f"id=eq.{obs_id}")
    except Exception:
        pass


# ── Ruas de Dois Irmãos e GeoJSON ─────────────────────────────────────────────

RUAS_OFICIAIS_DOIS_IRMAOS = [
    # Avenidas Principais
    "Av. São Miguel",
    "Av. Sapiranga",
    "Av. Florestal",
    "Av. Irineu Becker",
    "Av. Central",
    "Av. das Palmeiras",
    "Av. Porto Alegre",
    "Av. 10 de Setembro",
    # Estradas e Travessões
    "Estrada Travessão",
    "Estrada Morro Reuter",
    "Estrada Picada 48",
    "Estrada Linha Imperial",
    "Estrada Campo Bom",
    "Estrada da Amizade",
    # Ruas
    "Rua 10 de Setembro",
    "Rua 25 de Julho",
    "Rua 20 de Setembro",
    "Rua 21 de Abril",
    "Rua Acre",
    "Rua Alagoas",
    "Rua Alberto Rübenich",
    "Rua Alberto Schmidt",
    "Rua Albino Wendling",
    "Rua Aloísio Herbert",
    "Rua Alvorada",
    "Rua Amapá",
    "Rua Amazonas",
    "Rua Anita Garibaldi",
    "Rua Arlindo Becker",
    "Rua Arthur Strassburger",
    "Rua Bahia",
    "Rua Barão do Rio Branco",
    "Rua Bela Vista",
    "Rua Bento Gonçalves",
    "Rua Berlim",
    "Rua Blumenau",
    "Rua Boa Vista",
    "Rua Bom Jardim",
    "Rua Brasília",
    "Rua Carlos Biehl",
    "Rua Carlos Gomes",
    "Rua Carlos Rausch",
    "Rua Ceará",
    "Rua Cecília Meireles",
    "Rua Castro Alves",
    "Rua Coronel Pedro Schneider",
    "Rua Cristiano Wolffenbüttel",
    "Rua Curitiba",
    "Rua da Paz",
    "Rua das Acácias",
    "Rua das Camélias",
    "Rua das Flores",
    "Rua das Hortênsias",
    "Rua das Palmeiras",
    "Rua das Rosas",
    "Rua Deodoro da Fonseca",
    "Rua Do Moinho",
    "Rua Dom Pedro I",
    "Rua Dom Pedro II",
    "Rua dos Imigrantes",
    "Rua dos Ipês",
    "Rua dos Jasmins",
    "Rua Duque de Caxias",
    "Rua Edgar Hoffmeister",
    "Rua Érico Veríssimo",
    "Rua Esperança",
    "Rua Espírito Santo",
    "Rua Esteio",
    "Rua Floriano Peixoto",
    "Rua Florianópolis",
    "Rua Fortaleza",
    "Rua Francisco Alves",
    "Rua Frei Caneca",
    "Rua Garibaldi",
    "Rua General Osório",
    "Rua Getúlio Vargas",
    "Rua Goiás",
    "Rua Gramado",
    "Rua Guilherme Schütz",
    "Rua Henrique Bier",
    "Rua Imigrante",
    "Rua Independência",
    "Rua Ipiranga",
    "Rua Irineu Becker",
    "Rua Jacob Walter",
    "Rua João Alfredo",
    "Rua João Pessoa",
    "Rua Joinville",
    "Rua José de Alencar",
    "Rua Júlio de Castilhos",
    "Rua Lindolfo Collor",
    "Rua Machado de Assis",
    "Rua Mal. Deodoro",
    "Rua Maranhão",
    "Rua Marechal Floriano",
    "Rua Mato Grosso",
    "Rua Minas Gerais",
    "Rua Moinho Velho",
    "Rua Monte Castelo",
    "Rua Navegantes",
    "Rua Novo Hamburgo",
    "Rua Olavo Bilac",
    "Rua Osvaldo Cruz",
    "Rua Pará",
    "Rua Paraíba",
    "Rua Paraná",
    "Rua Piauí",
    "Rua Pinheiro Machado",
    "Rua Pomerânia",
    "Rua Porto Alegre",
    "Rua Primavera",
    "Rua Princesa Isabel",
    "Rua Presidente Costa e Silva",
    "Rua Presidente Kennedy",
    "Rua Presidente Lucena",
    "Rua Presidente Vargas",
    "Rua Quinze de Novembro",
    "Rua Quintino Bocaiúva",
    "Rua Riachuelo",
    "Rua Rio de Janeiro",
    "Rua Rio Grande do Norte",
    "Rua Rio Grande do Sul",
    "Rua Rondônia",
    "Rua Roraima",
    "Rua Santa Catarina",
    "Rua Santa Cruz",
    "Rua Santa Lúcia",
    "Rua Santa Maria",
    "Rua Santos Dumont",
    "Rua São Borja",
    "Rua São Cristóvão",
    "Rua São Francisco",
    "Rua São Gabriel",
    "Rua São Jerônimo",
    "Rua São José",
    "Rua São Leopoldo",
    "Rua São Luís",
    "Rua São Mateus",
    "Rua São Miguel",
    "Rua São Paulo",
    "Rua São Pedro",
    "Rua São Roque",
    "Rua Sapiranga",
    "Rua Sete de Setembro",
    "Rua Sergipe",
    "Rua Sobradinho",
    "Rua Tiradentes",
    "Rua Tocantins",
    "Rua Três de Maio",
    "Rua União",
    "Rua Vale Verde",
    "Rua Vinte de Setembro",
    "Rua Visconde de Mauá",
    "Rua Visconde de Taunay",
    "Rua Voluntários da Pátria",
]


# ── Gerenciamento e Cache de Ruas ──────────────────────────────────────────────

_ON_RUAS_MODIFICADAS_CALLBACKS: list = []


def registrar_callback_ruas_modificadas(callback):
    """Permite que telas como ScreenDelivery se inscrevam para atualização instantânea."""
    if callback not in _ON_RUAS_MODIFICADAS_CALLBACKS:
        _ON_RUAS_MODIFICADAS_CALLBACKS.append(callback)


def desregistrar_callback_ruas_modificadas(callback):
    if callback in _ON_RUAS_MODIFICADAS_CALLBACKS:
        _ON_RUAS_MODIFICADAS_CALLBACKS.remove(callback)


def _notificar_ruas_modificadas():
    for cb in list(_ON_RUAS_MODIFICADAS_CALLBACKS):
        try:
            cb()
        except Exception:
            pass


_PREPOSICOES_PT = {'de', 'da', 'do', 'dos', 'das', 'e', 'em', 'no', 'na', 'nos', 'nas'}
_PREFIXOS_RUAS = {
    'av': 'Av.', 'av.': 'Av.', 'avenida': 'Av.',
    'r': 'Rua', 'r.': 'Rua', 'rua': 'Rua',
    'estr': 'Estrada', 'estr.': 'Estrada', 'estrada': 'Estrada',
    'trav': 'Travessa', 'trav.': 'Travessa', 'travessa': 'Travessa',
    'al': 'Alameda', 'al.': 'Alameda', 'alameda': 'Alameda',
    'rod': 'Rodovia', 'rod.': 'Rodovia', 'rodovia': 'Rodovia',
    'beco': 'Beco'
}
_TITULOS_RUAS = {
    'dr': 'Dr.', 'dr.': 'Dr.', 'dra': 'Dra.', 'dra.': 'Dra.',
    'prof': 'Prof.', 'prof.': 'Prof.', 'cel': 'Coronel', 'cel.': 'Coronel',
    'mal': 'Marechal', 'mal.': 'Marechal', 'gen': 'General', 'gen.': 'General'
}


def _strip_accents(text: str) -> str:
    """Remove acentos e converte para minúsculas."""
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


def formatar_nome_rua(nome: str) -> str:
    """
    Formata o nome da via para Title Case adequado em português:
    - Remove espaços extras
    - Normaliza prefixos comuns ('r.' -> 'Rua', 'av' -> 'Av.')
    - Mantém preposições em minúsculas ('de', 'da', 'dos')
    - Capitaliza demais palavras
    """
    if not nome or not nome.strip():
        return ""
    partes = nome.strip().split()
    palavras = []
    for i, p in enumerate(partes):
        p_low = p.lower()
        if i == 0:
            palavras.append(_PREFIXOS_RUAS.get(p_low, p.capitalize()))
        else:
            if p_low in _PREPOSICOES_PT:
                palavras.append(p_low)
            elif p_low in _TITULOS_RUAS:
                palavras.append(_TITULOS_RUAS[p_low])
            elif p_low in _PREFIXOS_RUAS:
                palavras.append(_PREFIXOS_RUAS[p_low])
            elif p.isupper() and len(p) <= 3 and p.isalpha():
                palavras.append(p)
            elif any(c.isdigit() for c in p):
                palavras.append(p.upper() if p.isalnum() and not p.isdigit() else p)
            else:
                palavras.append(p.capitalize())
    return " ".join(palavras)


def normalizar_rua_para_comparacao(nome: str) -> str:
    """
    Normaliza a rua para detecção rigorosa de duplicidade:
    - Sem acentos, minúsculas, pontuações removidas
    - Padronização de prefixos equivalentes (av / avenida -> av, r / rua -> rua)
    """
    import re
    clean = _strip_accents(nome)
    clean = re.sub(r'[^\w\s]', ' ', clean)
    tokens = clean.split()
    if not tokens:
        return ""
    if tokens[0] in ('av', 'avenida'):
        tokens[0] = 'av'
    elif tokens[0] in ('r', 'rua'):
        tokens[0] = 'rua'
    elif tokens[0] in ('estr', 'estrada'):
        tokens[0] = 'estrada'
    elif tokens[0] in ('trav', 'travessa'):
        tokens[0] = 'travessa'
    return " ".join(tokens)


def listar_ruas(apenas_ativas=True):
    with get_connection() as conn:
        q = "SELECT * FROM ruas"
        if apenas_ativas:
            q += " WHERE ativo=1"
        q += " ORDER BY nome COLLATE NOCASE"
        return [dict(r) for r in conn.execute(q).fetchall()]


def cadastrar_rua_se_inedita(nome: str, bairro: str = "", taxa: float = 0.0) -> tuple[bool, dict | None]:
    """
    Verifica se a rua já existe no SQLite local (insensível a acentos/maiúsculas).
    - Se for inédita: formata em Title Case, insere com bairro e taxa, notifica cache e retorna (True, dict).
    - Se já existir: enriquece bairro/taxa se estavam vazios e retorna (False, dict_existente).
    """
    nome_limpo = " ".join((nome or "").split()).strip()
    if not nome_limpo or len(nome_limpo) < 3 or nome_limpo.isdigit():
        return False, None

    nome_formatado = formatar_nome_rua(nome_limpo)
    norm_candidato = normalizar_rua_para_comparacao(nome_formatado)
    if not norm_candidato:
        return False, None

    bairro_str = (bairro or "").strip()
    taxa_val = float(taxa or 0.0)

    with get_connection() as conn:
        linhas = conn.execute("SELECT id, nome, bairro, taxa, ativo FROM ruas").fetchall()
        for r in linhas:
            r_dict = dict(r)
            norm_existente = normalizar_rua_para_comparacao(r_dict["nome"])
            if norm_candidato == norm_existente:
                # Já cadastrada! Atualizar bairro ou taxa se antes estavam vazios
                update_needed = False
                novo_bairro = r_dict.get("bairro") or ""
                nova_taxa = float(r_dict.get("taxa") or 0.0)

                if bairro_str and not novo_bairro:
                    novo_bairro = bairro_str
                    update_needed = True
                if taxa_val > 0 and nova_taxa == 0.0:
                    nova_taxa = taxa_val
                    update_needed = True

                if update_needed:
                    try:
                        conn.execute(
                            "UPDATE ruas SET bairro = ?, taxa = ? WHERE id = ?",
                            (novo_bairro, nova_taxa, r_dict["id"])
                        )
                        r_dict["bairro"] = novo_bairro
                        r_dict["taxa"] = nova_taxa
                    except Exception:
                        pass
                return False, r_dict

        # Se a taxa for 0, mas tivermos bairro, verificar se outras ruas do mesmo bairro têm taxa cadastrada
        if taxa_val == 0.0 and bairro_str:
            row_tx = conn.execute(
                "SELECT taxa FROM ruas WHERE bairro = ? AND taxa > 0 LIMIT 1",
                (bairro_str,)
            ).fetchone()
            if row_tx and row_tx["taxa"]:
                taxa_val = float(row_tx["taxa"])

        # Inserção de rua inédita
        try:
            cur = conn.execute(
                "INSERT INTO ruas (nome, bairro, taxa, ativo) VALUES (?, ?, ?, 1)",
                (nome_formatado, bairro_str, taxa_val)
            )
            nova_rua = {
                "id": cur.lastrowid,
                "nome": nome_formatado,
                "bairro": bairro_str,
                "taxa": taxa_val,
                "ativo": 1
            }
        except Exception:
            # Caso ocorra conflito
            row = conn.execute("SELECT * FROM ruas WHERE nome = ?", (nome_formatado,)).fetchone()
            return False, dict(row) if row else None

    # Manter sincronizado com lista de fallback em memória se existir
    try:
        from config import RUAS_DOIS_IRMAOS
        if nome_formatado not in RUAS_DOIS_IRMAOS:
            RUAS_DOIS_IRMAOS.append(nome_formatado)
            RUAS_DOIS_IRMAOS.sort()
    except Exception:
        pass

    try:
        from services.supabase_sync import sincronizar_item_supabase_async
        sincronizar_item_supabase_async("ruas", nova_rua, metodo="POST")
    except Exception:
        pass

    # Disparar atualização nos ouvintes de UI
    _notificar_ruas_modificadas()
    return True, nova_rua


def adicionar_rua(nome: str, bairro: str = "", taxa: float = 0.0, ativo: int = 1):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO ruas (nome, bairro, taxa, ativo) VALUES (?, ?, ?, ?)",
            (nome.strip(), (bairro or "").strip(), float(taxa or 0.0), ativo)
        )
    _notificar_ruas_modificadas()


def remover_rua(rua_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE ruas SET ativo=0 WHERE id=?", (rua_id,))
    _notificar_ruas_modificadas()


# ── Histórico Inteligente de Taxas por Endereço (Rua + Número) ────────────────

def _remover_prefixo_generico(norm_rua: str) -> str:
    """Descarta prefixos genéricos de via ('rua', 'av') para matching tolerante."""
    parts = norm_rua.split()
    if parts and parts[0] in ('rua', 'av', 'estrada', 'travessa', 'alameda', 'rodovia', 'beco'):
        return " ".join(parts[1:])
    return norm_rua


def obter_historico_endereco(rua: str, numero: str) -> dict | None:
    """
    Busca o histórico de taxa e bairro para a combinação exata de Rua + Número.
    Utiliza correspondência direta (COLLATE NOCASE), Title Case e normalização de via.
    """
    rua_clean = (rua or "").strip()
    num_clean = (numero or "").strip()
    if not rua_clean or not num_clean:
        return None

    with get_connection() as conn:
        # 1. Busca direta (case-insensitive via COLLATE NOCASE)
        row = conn.execute(
            "SELECT * FROM historico_enderecos WHERE rua = ? AND numero = ? ORDER BY id DESC LIMIT 1",
            (rua_clean, num_clean)
        ).fetchone()
        if row:
            return dict(row)

        # 2. Busca com Title Case formatado
        rua_fmt = formatar_nome_rua(rua_clean)
        if rua_fmt.lower() != rua_clean.lower():
            row = conn.execute(
                "SELECT * FROM historico_enderecos WHERE rua = ? AND numero = ? ORDER BY id DESC LIMIT 1",
                (rua_fmt, num_clean)
            ).fetchone()
            if row:
                return dict(row)

        # 3. Busca por equivalência normalizada (sem acentos e tolerante a omissão de prefixo)
        norm_busca = normalizar_rua_para_comparacao(rua_clean)
        norm_busca_sem_pref = _remover_prefixo_generico(norm_busca)
        rows = conn.execute(
            "SELECT * FROM historico_enderecos WHERE numero = ? ORDER BY id DESC",
            (num_clean,)
        ).fetchall()
        for r in rows:
            norm_r = normalizar_rua_para_comparacao(r["rua"])
            if norm_r == norm_busca or _remover_prefixo_generico(norm_r) == norm_busca_sem_pref:
                return dict(r)

    return None


def salvar_historico_endereco(rua: str, numero: str, bairro: str = "", taxa_frete: float = 0.0):
    """
    Grava ou atualiza a taxa de frete e bairro cobrados para o endereço (Rua + Número).
    Garante integridade e atualização de timestamp sem travar a interface.
    """
    rua_clean = formatar_nome_rua((rua or "").strip())
    num_clean = (numero or "").strip()
    bairro_clean = (bairro or "").strip()
    try:
        taxa_val = float(taxa_frete or 0.0)
    except (ValueError, TypeError):
        taxa_val = 0.0

    if not rua_clean or not num_clean:
        return

    with get_connection() as conn:
        norm_busca = normalizar_rua_para_comparacao(rua_clean)
        norm_busca_sem_pref = _remover_prefixo_generico(norm_busca)
        rows = conn.execute(
            "SELECT id, rua FROM historico_enderecos WHERE numero = ?",
            (num_clean,)
        ).fetchall()
        reg_id = None
        for r in rows:
            norm_r = normalizar_rua_para_comparacao(r["rua"])
            if norm_r == norm_busca or _remover_prefixo_generico(norm_r) == norm_busca_sem_pref:
                reg_id = r["id"]
                break

        if reg_id:
            conn.execute(
                """UPDATE historico_enderecos
                   SET rua = ?, bairro = ?, taxa_frete = ?, atualizado_em = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (rua_clean, bairro_clean, taxa_val, reg_id)
            )
        else:
            conn.execute(
                """INSERT OR REPLACE INTO historico_enderecos
                   (rua, numero, bairro, taxa_frete, atualizado_em)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (rua_clean, num_clean, bairro_clean, taxa_val)
            )


def importar_ruas_geojson(caminho: str = None) -> int:
    """
    Importa e saneia vias a partir de arquivo GeoJSON (OpenStreetMap/Overpass API).
    1. Extrai a tag 'name' de features onde 'highway' está presente.
    2. Remove duplicatas, registros vazios e normaliza espaçamentos.
    3. Popula a tabela 'ruas' no SQLite local.
    4. Se o GeoJSON estiver vazio ou ausente, usa a base oficial saneada de Dois Irmãos
       e grava o arquivo export.geojson com formato GeoJSON válido.
    Retorna o total de ruas ativas cadastradas.
    """
    import json
    import os

    candidatos = []
    if caminho:
        candidatos.append(caminho)
    # Procurar export.geojson no diretório raiz do projeto e em Downloads
    candidatos.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "export.geojson"))
    candidatos.append(os.path.join(os.path.expanduser("~"), "Downloads", "export.geojson"))

    ruas_encontradas = set()

    for p in candidatos:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                features = dados.get("features", [])
                for feat in features:
                    props = feat.get("properties", {})
                    if "highway" in props or "name" in props:
                        nome = props.get("name")
                        if nome and isinstance(nome, str):
                            nome_limpo = " ".join(nome.split()).strip()
                            if len(nome_limpo) >= 2:
                                ruas_encontradas.add(nome_limpo)
                if ruas_encontradas:
                    break
            except Exception:
                pass

    # Fallback oficial caso o GeoJSON do overpass esteja vazio
    if not ruas_encontradas:
        ruas_encontradas = set(RUAS_OFICIAIS_DOIS_IRMAOS)
        geojson_conteudo = {
            "type": "FeatureCollection",
            "generator": "PointLanches-GeoSanitizer",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": r, "highway": "residential"},
                    "geometry": None
                }
                for r in sorted(ruas_encontradas)
            ]
        }
        destinos = [p for p in candidatos if p.endswith("export.geojson")]
        for dest in destinos:
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w", encoding="utf-8") as f:
                    json.dump(geojson_conteudo, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    with get_connection() as conn:
        for r in sorted(ruas_encontradas):
            conn.execute(
                "INSERT OR IGNORE INTO ruas (nome, ativo) VALUES (?, 1)",
                (r,)
            )

    return len(ruas_encontradas)


# ── Backup e Portabilidade (Exportar / Importar JSON) ─────────────────────────

def exportar_dados_json() -> dict:
    """
    Consolida produtos, categorias, adicionais, taxas de entrega,
    observações rápidas e configurações gerais em uma estrutura JSON para backup.
    """
    from datetime import datetime
    with get_connection() as conn:
        categorias = [dict(r) for r in conn.execute("SELECT * FROM categorias ORDER BY id").fetchall()]
        produtos = [dict(r) for r in conn.execute("""
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            JOIN categorias c ON c.id = p.categoria_id
            ORDER BY c.id, p.nome
        """).fetchall()]
        adicionais = [dict(r) for r in conn.execute("SELECT * FROM adicionais ORDER BY id").fetchall()]
        taxas = [dict(r) for r in conn.execute("SELECT * FROM taxas_entrega ORDER BY ordem, valor").fetchall()]
        observacoes = [dict(r) for r in conn.execute("SELECT * FROM observacoes_padrao ORDER BY id").fetchall()]
        configuracoes = {r["chave"]: r["valor"] for r in conn.execute("SELECT * FROM configuracoes").fetchall()}
        ruas = [dict(r) for r in conn.execute("SELECT * FROM ruas ORDER BY nome").fetchall()]
        historico_enderecos = [dict(r) for r in conn.execute("SELECT * FROM historico_enderecos ORDER BY id").fetchall()]

    return {
        "versao_schema": "1.0",
        "data_exportacao": datetime.now().isoformat(),
        "sistema": "Point Lanches",
        "categorias": categorias,
        "produtos": produtos,
        "adicionais": adicionais,
        "taxas_entrega": taxas,
        "observacoes_padrao": observacoes,
        "configuracoes": configuracoes,
        "ruas": ruas,
        "historico_enderecos": historico_enderecos,
    }


def importar_dados_json(dados: dict) -> tuple[bool, str]:
    """
    Importa configurações a partir de um dicionário estruturado JSON.
    Executa a substituição das tabelas de configuração em transação única e segura.
    Retorna (True, mensagem) ou (False, mensagem_erro).
    """
    if not isinstance(dados, dict):
        return False, "Formato inválido: o conteúdo do backup deve ser um objeto JSON."

    if not any(k in dados for k in ("categorias", "produtos", "adicionais", "taxas_entrega", "observacoes_padrao", "configuracoes")):
        return False, "O arquivo selecionado não contém dados de configuração reconhecíveis do Point Lanches."

    try:
        with get_connection() as conn:
            # 1. Categorias
            if "categorias" in dados and isinstance(dados["categorias"], list):
                for cat in dados["categorias"]:
                    if "nome" in cat:
                        conn.execute("INSERT OR IGNORE INTO categorias (nome) VALUES (?)", (cat["nome"],))

            # 2. Produtos
            if "produtos" in dados and isinstance(dados["produtos"], list):
                for prod in dados["produtos"]:
                    cat_id = prod.get("categoria_id")
                    cat_nome = prod.get("categoria_nome")
                    if cat_nome and not cat_id:
                        r = conn.execute("SELECT id FROM categorias WHERE nome=?", (cat_nome,)).fetchone()
                        if r:
                            cat_id = r["id"]
                        else:
                            cur = conn.execute("INSERT INTO categorias (nome) VALUES (?)", (cat_nome,))
                            cat_id = cur.lastrowid

                    if cat_id and prod.get("nome"):
                        row_p = conn.execute("SELECT id FROM produtos WHERE nome=?", (prod["nome"],)).fetchone()
                        if row_p:
                            conn.execute("""
                                UPDATE produtos
                                SET categoria_id=?, descricao=?, preco=?, ativo=?
                                WHERE id=?
                            """, (
                                cat_id, prod.get("descricao", ""),
                                prod.get("preco", 0.0), prod.get("ativo", 1),
                                row_p["id"]
                            ))
                        else:
                            conn.execute("""
                                INSERT INTO produtos (categoria_id, nome, descricao, preco, ativo)
                                VALUES (?, ?, ?, ?, ?)
                            """, (
                                cat_id, prod["nome"],
                                prod.get("descricao", ""), prod.get("preco", 0.0),
                                prod.get("ativo", 1)
                            ))

            # 3. Adicionais
            if "adicionais" in dados and isinstance(dados["adicionais"], list):
                for ad in dados["adicionais"]:
                    if ad.get("nome"):
                        row_a = conn.execute("SELECT id FROM adicionais WHERE nome=?", (ad["nome"],)).fetchone()
                        if row_a:
                            conn.execute("UPDATE adicionais SET preco=?, ativo=? WHERE id=?",
                                         (ad.get("preco", 0.0), ad.get("ativo", 1), row_a["id"]))
                        else:
                            conn.execute("INSERT INTO adicionais (nome, preco, ativo) VALUES (?, ?, ?)",
                                         (ad["nome"], ad.get("preco", 0.0), ad.get("ativo", 1)))

            # 4. Observações Rápidas
            if "observacoes_padrao" in dados and isinstance(dados["observacoes_padrao"], list):
                for obs in dados["observacoes_padrao"]:
                    if obs.get("texto"):
                        row_o = conn.execute("SELECT id FROM observacoes_padrao WHERE texto=?", (obs["texto"],)).fetchone()
                        if row_o:
                            conn.execute("UPDATE observacoes_padrao SET ativo=? WHERE id=?",
                                         (obs.get("ativo", 1), row_o["id"]))
                        else:
                            conn.execute("INSERT INTO observacoes_padrao (texto, ativo) VALUES (?, ?)",
                                         (obs["texto"], obs.get("ativo", 1)))

            # 5. Taxas de Entrega
            if "taxas_entrega" in dados and isinstance(dados["taxas_entrega"], list):
                for taxa in dados["taxas_entrega"]:
                    if "valor" in taxa:
                        v = float(taxa["valor"])
                        lbl = taxa.get("label", f"R$ {v:.2f}")
                        ordem = taxa.get("ordem", int(v * 100))
                        ativo = taxa.get("ativo", 1)
                        row_t = conn.execute("SELECT id FROM taxas_entrega WHERE valor=?", (v,)).fetchone()
                        if row_t:
                            conn.execute("UPDATE taxas_entrega SET label=?, ativo=?, ordem=? WHERE id=?",
                                         (lbl, ativo, ordem, row_t["id"]))
                        else:
                            conn.execute("INSERT INTO taxas_entrega (valor, label, ativo, ordem) VALUES (?, ?, ?, ?)",
                                         (v, lbl, ativo, ordem))

            # 6. Configurações gerais (impressora, ip, etc.)
            if "configuracoes" in dados and isinstance(dados["configuracoes"], dict):
                for k, v in dados["configuracoes"].items():
                    conn.execute("INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)", (k, str(v)))

            # 7. Ruas
            if "ruas" in dados and isinstance(dados["ruas"], list):
                for r in dados["ruas"]:
                    if r.get("nome"):
                        conn.execute(
                            "INSERT OR IGNORE INTO ruas (nome, bairro, taxa, ativo) VALUES (?, ?, ?, ?)",
                            (r["nome"], r.get("bairro", ""), float(r.get("taxa") or 0.0), r.get("ativo", 1))
                        )
                _notificar_ruas_modificadas()

            # 8. Histórico de Endereços
            if "historico_enderecos" in dados and isinstance(dados["historico_enderecos"], list):
                for h in dados["historico_enderecos"]:
                    if h.get("rua") and h.get("numero"):
                        conn.execute("""
                            INSERT OR REPLACE INTO historico_enderecos 
                            (rua, numero, bairro, taxa_frete, atualizado_em)
                            VALUES (?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                        """, (
                            h["rua"], h["numero"], h.get("bairro", ""),
                            float(h.get("taxa_frete") or 0.0), h.get("atualizado_em")
                        ))

        return True, "Configurações importadas e aplicadas com sucesso!"
    except Exception as e:
        return False, f"Falha na importação: {str(e)}"


# ── Logs de Erros ─────────────────────────────────────────────────────────────

def registrar_log_erro(modulo: str, mensagem: str, detalhes: str = "", tipo: str = "ERRO") -> int:
    """Registra uma ocorrência de erro localmente no SQLite e agenda envio assíncrono para o Supabase."""
    from version import __version__
    log_id = 0
    try:
        with get_connection() as conn:
            cur = conn.execute("""
                INSERT INTO logs_erro (tipo, modulo, mensagem, detalhes, versao_app)
                VALUES (?, ?, ?, ?, ?)
            """, (tipo.upper(), modulo, str(mensagem), str(detalhes), __version__))
            log_id = cur.lastrowid
            conn.commit()
    except Exception as e:
        print(f"Falha ao registrar log de erro no SQLite: {e}")

    if log_id:
        try:
            from services.supabase_sync import sincronizar_log_supabase_async
            sincronizar_log_supabase_async(log_id, {
                "tipo": tipo.upper(),
                "modulo": modulo,
                "mensagem": str(mensagem),
                "detalhes": str(detalhes),
                "versao_app": __version__
            })
        except Exception:
            pass

    return log_id


def listar_logs_erro(limite: int = 300, tipo_filtro: str = None) -> list[dict]:
    """Retorna os logs de erro ordenados por data e hora decrescente (mais recentes primeiro)."""
    with get_connection() as conn:
        q = "SELECT * FROM logs_erro"
        params = []
        if tipo_filtro and tipo_filtro != "TODOS":
            q += " WHERE tipo = ?"
            params.append(tipo_filtro.upper())
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limite)
        rows = conn.execute(q, tuple(params)).fetchall()
        return [dict(r) for r in rows]


def limpar_logs_erro() -> bool:
    """Limpa todos os logs de erro registrados no banco local."""
    with get_connection() as conn:
        conn.execute("DELETE FROM logs_erro")
        conn.commit()
    return True


