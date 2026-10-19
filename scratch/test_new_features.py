import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from database.db import (
    init_db, salvar_pedido, get_pedido_com_itens, excluir_pedido,
    calcular_balanco_mensal, exportar_dados_json, importar_dados_json,
    get_connection, listar_produtos, listar_categorias
)

print("=== 1. Testando Tabelas de Insumos e Migrações ===")
init_db()

with get_connection() as conn:
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "insumos" in tables, "Tabela 'insumos' não foi criada!"
    assert "movimentacoes_insumos" in tables, "Tabela 'movimentacoes_insumos' não foi criada!"
    print(f"Tabelas no SQLite: {len(tables)} encontradas. 'insumos' e 'movimentacoes_insumos' presentes.")

print("\n=== 2. Testando Exclusão de Pedido (Lixeira) ===")
pedido_teste = {
    "cliente_nome": "Cliente Teste Exclusão",
    "cliente_fone": "5199999999",
    "rua": "Av. São Miguel",
    "numero": "100",
    "complemento": "",
    "bairro": "Centro",
    "referencia": "",
    "subtotal": 50.0,
    "taxa_entrega": 5.0,
    "total": 55.0,
    "forma_pgto": "PIX",
    "valor_pago": 55.0,
    "troco": 0.0,
}
itens_teste = [
    {"produto_id": 1, "nome": "X-Salada Teste", "preco_unit": 25.0, "quantidade": 2, "observacao": "Sem Cebola", "categoria": "Lanches"}
]

pid = salvar_pedido(pedido_teste, itens_teste)
print(f"Pedido de teste criado com ID #{pid}")

ped_db, itens_db = get_pedido_com_itens(pid)
assert ped_db is not None, "Pedido não encontrado após criação"
assert len(itens_db) == 1, "Itens do pedido não encontrados"

# Excluir pedido
ok = excluir_pedido(pid)
assert ok is True, "Falha na chamada de excluir_pedido"

ped_removido, itens_removidos = get_pedido_com_itens(pid)
assert ped_removido is None, "Pedido ainda existe após exclusão!"
assert len(itens_removidos) == 0, "Itens do pedido ainda existem após exclusão!"
print(f"Pedido #{pid} e seus itens excluídos com sucesso do SQLite!")

print("\n=== 3. Testando Balanço Geral Mensal & Arquitetura de Insumos ===")
# Cria pedidos para o mês atual
from datetime import datetime
now = datetime.now()

p1 = salvar_pedido({
    "cliente_nome": "Cliente Balanço 1",
    "subtotal": 30.0, "taxa_entrega": 5.0, "total": 35.0,
    "forma_pgto": "PIX",
}, [{"nome": "Item 1", "preco_unit": 30.0, "quantidade": 1}])

p2 = salvar_pedido({
    "cliente_nome": "Cliente Balanço 2",
    "subtotal": 40.0, "taxa_entrega": 7.0, "total": 47.0,
    "forma_pgto": "Dinheiro",
}, [{"nome": "Item 2", "preco_unit": 40.0, "quantidade": 1}])

p3 = salvar_pedido({
    "cliente_nome": "Cliente Balanço 3",
    "subtotal": 50.0, "taxa_entrega": 0.0, "total": 50.0,
    "forma_pgto": "Cartão de Débito",
}, [{"nome": "Item 3", "preco_unit": 50.0, "quantidade": 1}])

balanco = calcular_balanco_mensal(now.month, now.year)
print(f"Balanço de {now.month:02d}/{now.year}:")
print(f"  Faturamento Total: R$ {balanco['faturamento_total']:.2f}")
print(f"  Total de Pedidos: {balanco['total_pedidos']}")
print(f"  Total de Taxas: R$ {balanco['total_taxas']:.2f}")
print(f"  Ticket Médio: R$ {balanco['ticket_medio']:.2f}")
print(f"  Custos Insumos: R$ {balanco['custo_insumos']:.2f}")
print(f"  Lucro Bruto: R$ {balanco['lucro_bruto']:.2f}")
print("  Modalidades:")
for mod, info in balanco["modalidades"].items():
    print(f"    - {mod:18}: R$ {info['total']:>7.2f} ({info['qtd']} pedidos)")

assert balanco["total_pedidos"] >= 3, "Esperado ao menos 3 pedidos no mês"
assert balanco["faturamento_total"] >= 132.0, "Faturamento incorreto"
assert balanco["lucro_bruto"] == balanco["faturamento_total"] - balanco["custo_insumos"], "Cálculo de lucro bruto incorreto"
assert balanco["modalidades"]["PIX"]["qtd"] >= 1, "PIX não registrado"
assert balanco["modalidades"]["Dinheiro"]["qtd"] >= 1, "Dinheiro não registrado"
assert balanco["modalidades"]["Cartão de Débito"]["qtd"] >= 1, "Débito não registrado"

# Limpa pedidos de teste
excluir_pedido(p1)
excluir_pedido(p2)
excluir_pedido(p3)

print("\n=== 4. Testando Exportação e Importação de Configurações (JSON) ===")
backup_data = exportar_dados_json()
print("Backup gerado com sucesso!")
print(f"  Versão: {backup_data.get('versao_schema')}")
print(f"  Categorias: {len(backup_data.get('categorias', []))}")
print(f"  Produtos: {len(backup_data.get('produtos', []))}")
print(f"  Adicionais: {len(backup_data.get('adicionais', []))}")
print(f"  Observações Rápidas: {len(backup_data.get('observacoes_padrao', []))}")
print(f"  Taxas de Entrega: {len(backup_data.get('taxas_entrega', []))}")

assert len(backup_data.get("produtos", [])) > 0, "Nenhum produto exportado"
assert len(backup_data.get("categorias", [])) > 0, "Nenhuma categoria exportada"

# Teste de importação com adição de um produto novo de teste
backup_data["produtos"].append({
    "nome": "Produto Teste Backup JSON",
    "descricao": "Criado para teste de portabilidade",
    "preco": 99.90,
    "ativo": 1,
    "categoria_nome": "Lanches Tradicionais"
})

sucesso, msg = importar_dados_json(backup_data)
assert sucesso is True, f"Falha na importação: {msg}"
print(f"Resultado da importação: {msg}")

# Verificar se o produto importado está no banco
prods = listar_produtos()
prod_nomes = [p["nome"] for p in prods]
assert "Produto Teste Backup JSON" in prod_nomes, "Produto importado não encontrado no banco!"
print("Produto de teste importado encontrado com sucesso no banco!")

# Limpar produto de teste
with get_connection() as conn:
    conn.execute("DELETE FROM produtos WHERE nome='Produto Teste Backup JSON'")

# Teste com JSON inválido
ok_inv, msg_inv = importar_dados_json("isso nao e um dicionario")
assert ok_inv is False, "Deveria falhar para formato não dicionário"
ok_inv2, msg_inv2 = importar_dados_json({"chave_aleatoria": 123})
assert ok_inv2 is False, "Deveria falhar para dicionário sem estrutura reconhecível"
print("Validação de integridade rejeitou corretamente formatos inválidos.")

print("\n=== TODOS OS TESTES PASSARAM COM 100% DE SUCESSO! ===")
