# database/seed.py - Populador do banco de dados (v2)
# =============================================================================

from database.db import get_connection, get_categoria_por_nome

CARDAPIO = [
    {
        "categoria": "Tradicionais",
        "itens": [
            ("Salada",    "Hamburguer, Queijo, Ovo, Milho, Tomate, Alface, Maionese, Catchup", 20.50),
            ("Calabresa", "Hamburguer, Calabresa, Queijo, Ovo, Milho, Tomate, Alface, Maionese, Catchup", 23.50),
            ("Bacon",     "Hamburguer, Bacon, Queijo, Ovo, Milho, Tomate, Alface, Maionese, Catchup", 24.00),
            ("Coração",   "Coração de Frango, Queijo, Ovo, Milho, Tomate, Alface, Maionese, Catchup", 23.50),
            ("Frango",    "Frango desfiado, Queijo, Ovo, Milho, Tomate, Alface, Maionese, Catchup", 20.50),
            ("Filé",      "Iscas de Filé, Queijo, Ovo, Milho, Tomate, Alface, Maionese, Catchup", 24.50),
        ]
    },
    {
        "categoria": "Exclusivos",
        "itens": [
            ("Portuguesa",            "Hamburguer, Queijo, Ovo, Presunto, Tomate, Cebola, Pimentão, Maionese, Catchup", 24.50),
            ("Fricassê",              "Frango Desfiado, Milho, Creme especial, Queijo, Batata Palha", 24.00),
            ("Frango com Catupiry",   "Frango Desfiado, Catupiry, Queijo, Batata Palha", 24.50),
            ("Strogonoff",            "Iscas de Filé, Creme Especial, Queijo, Batata Palha", 24.00),
            ("Moda da Casa (Bagunça)","Hamburguer, Coração, Calabresa, Bacon, Frango, Queijo, Ovo, Milho, Tomate, Alface, Maionese, Catchup, Batata Palha", 26.00),
        ]
    },
    {
        "categoria": "Fritas",
        "itens": [
            ("Porção de Batata Frita",             "Batata Frita crocante", 20.50),
            ("Batata Frita c/ Calabresa e Queijo", "Porção com Calabresa e Queijo Derretido", 30.00),
        ]
    },
    {
        "categoria": "Cachorro Quente",
        "itens": [
            ("Cachorro Quente 2 Salsichas", "Molho Vermelho, Milho, Queijo, Batata Palha, Maionese e Catchup", 17.00),
            ("Cachorro Quente 3 Salsichas", "Molho Vermelho, Milho, Queijo, Batata Palha, Maionese e Catchup", 18.00),
            ("Cachorro Quente Calabresa",   "Molho Vermelho, Milho, Queijo, Batata Palha, Maionese e Catchup", 19.00),
        ]
    },
    {
        "categoria": "Torrada",
        "itens": [
            ("Torrada Pão de Xis", "2 Fatias De Queijo, 2 Fatias de Presunto, Ovo, Tomate, Alface, Maionese e Catchup", 15.50),
        ]
    },
    {
        "categoria": "Pratos Feitos",
        "itens": [
            ("Picadinho de Carne", "Picadinho de Carne, Arroz, Fritas, Ovo e Salada", 27.00),
            ("Fricasse PF",        "Fricasse, Arroz, Fritas e Salada", 27.00),
            ("Strogonoff PF",      "Strogonoff, Arroz, Fritas e Salada", 27.00),
        ]
    },
    {
        "categoria": "Bebidas",
        "itens": [
            ("Coca-Cola Lata 350ml",  "Gelada",      6.00),
            ("Pepsi Lata 350ml",      "Gelada",      5.50),
            ("Guaraná Antarctica 2L", "Garrafa",     12.00),
            ("Coca-Cola 2L",          "Garrafa",     13.00),
            ("Água Mineral 500ml",    "Sem gás",     3.00),
            ("Cerveja Lata 350ml",    "Gelada",      6.00),
            ("Suco de Laranja 500ml", "Natural",     8.00),
            ("Refrigerante Lata",     "Vários sabores", 5.50),
        ]
    },
]

ADICIONAIS_PADRAO = [
    ("Fritas",       5.00),
    ("Ovo",          2.00),
    ("Catupiry",     5.00),
    ("Bacon",        3.00),
    ("Queijo Extra", 2.00),
    ("Calabresa",    3.50),
    ("Maionese Extra", 1.00),
]

TAXAS_PADRAO = [
    (0.00,  "Grátis"),
    (5.00,  "R$ 5"),
    (7.00,  "R$ 7"),
    (8.00,  "R$ 8"),
    (10.00, "R$ 10"),
]

OBS_PADRAO = [
    "Sem Cebola",
    "Sem Milho",
    "Sem Maionese",
    "Sem Tomate",
    "Molho à Parte",
    "Sem Catchup",
    "Sem Alface",
    "Sem Queijo",
    "Sem Ovo",
]


def _upsert_categoria(conn, nome) -> int:
    eh_bebida = 1 if "bebida" in nome.lower() else 0
    conn.execute("INSERT OR IGNORE INTO categorias (nome, eh_bebida) VALUES (?, ?)", (nome, eh_bebida))
    return conn.execute("SELECT id FROM categorias WHERE nome=?", (nome,)).fetchone()[0]


def seed_if_empty():
    """Popula o cardápio se não houver produtos."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0]
        if count > 0:
            return

        for bloco in CARDAPIO:
            cat_id = _upsert_categoria(conn, bloco["categoria"])
            for nome, desc, preco in bloco["itens"]:
                conn.execute(
                    "INSERT INTO produtos (categoria_id, nome, descricao, preco) VALUES (?,?,?,?)",
                    (cat_id, nome, desc, preco)
                )

        # Desativar categoria "Extras" legada se existir
        conn.execute(
            "UPDATE produtos SET ativo=0 WHERE categoria_id IN "
            "(SELECT id FROM categorias WHERE nome='Extras')"
        )


def seed_bebidas_if_missing():
    """Adiciona a categoria Bebidas e seus produtos se ainda não existir."""
    with get_connection() as conn:
        existe = conn.execute(
            "SELECT COUNT(*) FROM categorias WHERE nome='Bebidas'"
        ).fetchone()[0]
        if existe:
            return

        cat_id = _upsert_categoria(conn, "Bebidas")
        for nome, desc, preco in next(
            b["itens"] for b in CARDAPIO if b["categoria"] == "Bebidas"
        ):
            conn.execute(
                "INSERT INTO produtos (categoria_id, nome, descricao, preco) VALUES (?,?,?,?)",
                (cat_id, nome, desc, preco)
            )


def seed_adicionais_if_empty():
    """Popula a tabela de adicionais se vazia."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM adicionais").fetchone()[0]
        if count > 0:
            return
        for nome, preco in ADICIONAIS_PADRAO:
            conn.execute(
                "INSERT INTO adicionais (nome, preco) VALUES (?,?)",
                (nome, preco)
            )


def seed_taxas_if_empty():
    """Popula taxas de entrega padrão se vazia."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM taxas_entrega").fetchone()[0]
        if count > 0:
            return
        for i, (valor, label) in enumerate(TAXAS_PADRAO):
            conn.execute(
                "INSERT INTO taxas_entrega (valor, label, ativo, ordem) VALUES (?,?,1,?)",
                (valor, label, i)
            )


def seed_observacoes_if_empty():
    """Popula observações rápidas padrão se a tabela estiver vazia."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM observacoes_padrao").fetchone()[0]
        if count > 0:
            return
        for texto in OBS_PADRAO:
            conn.execute(
                "INSERT INTO observacoes_padrao (texto) VALUES (?)",
                (texto,)
            )


def seed_ruas_if_empty():
    """Popula ruas padrão/GeoJSON de Dois Irmãos se a tabela estiver vazia."""
    from database.db import importar_ruas_geojson
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM ruas").fetchone()[0]
        if count > 0:
            return
    importar_ruas_geojson()


def run_all_seeds():
    """Ponto único de chamada para popular tudo."""
    seed_if_empty()
    seed_bebidas_if_missing()
    seed_adicionais_if_empty()
    seed_taxas_if_empty()
    seed_observacoes_if_empty()
    seed_ruas_if_empty()
    with get_connection() as conn:
        conn.execute(
            "UPDATE produtos SET ativo=0 WHERE categoria_id IN "
            "(SELECT id FROM categorias WHERE LOWER(nome)='extras')"
        )

