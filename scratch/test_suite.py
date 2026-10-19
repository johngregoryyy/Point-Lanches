import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from database.db import init_db, listar_ruas, listar_observacoes_padrao, importar_ruas_geojson
from database.seed import run_all_seeds
from ui.screen_delivery import gerar_acronimos_rua, _strip_accents

print("--- 1. Inicializando DB e Seeds ---")
init_db()
run_all_seeds()

ruas = listar_ruas()
print(f"Ruas cadastradas no SQLite: {len(ruas)}")
assert len(ruas) >= 50, f"Esperado mais de 50 ruas, obtido {len(ruas)}"

obs = listar_observacoes_padrao()
print(f"Observações rápidas no SQLite: {len(obs)}")
assert len(obs) >= 5, f"Esperado ao menos 5 observações, obtido {len(obs)}"

print("\n--- 2. Validando Algoritmo Dinâmico de Acrônimos ---")
test_cases = {
    "Avenida São Miguel": ["sm", "asm"],
    "Rua Alberto Rübenich": ["ar"],
    "Rua 10 de Setembro": ["10", "10s"],
    "Rua Novo Hamburgo": ["nh"],
    "Rua São Leopoldo": ["sl"],
    "Avenida Florestal": ["fl", "flo", "af"],
    "Avenida Sapiranga": ["sap", "as"],
    "Estrada Travessão": ["tr", "tra"],
    "Rua 25 de Julho": ["25", "25j"],
}

for rua, expected_subsets in test_cases.items():
    acrs = gerar_acronimos_rua(rua)
    print(f"  {rua:25} -> {sorted(list(acrs))}")
    for exp in expected_subsets:
        assert exp in acrs, f"Esperava '{exp}' nos acrônimos de '{rua}', obtido: {acrs}"

print("\n--- 3. Verificando export.geojson ---")
downloads_path = r"C:\Users\Herval\Downloads\export.geojson"
assert os.path.exists(downloads_path), f"Arquivo não encontrado: {downloads_path}"
with open(downloads_path, "r", encoding="utf-8") as f:
    geo = json.load(f)
feats = geo.get("features", [])
print(f"Features em export.geojson: {len(feats)}")
assert len(feats) >= 50, f"export.geojson vazio ou incompleto: {len(feats)}"
print(f"Exemplo de feature: {feats[0]}")

print("\n--- 4. Testando Matching de Busca ---")
indices = [(r["nome"], _strip_accents(r["nome"]), gerar_acronimos_rua(r["nome"])) for r in ruas]

def simular_busca(termo):
    termo_norm = _strip_accents(termo)
    encontradas = []
    for r_nome, r_norm, r_acrs in indices:
        if termo_norm in r_norm or termo_norm in r_acrs:
            encontradas.append(r_nome)
    return encontradas

buscas = {
    "nh": "Novo Hamburgo",
    "sl": "São Leopoldo",
    "sm": "São Miguel",
    "ar": "Alberto Rübenich",
    "10": "10 de Setembro",
    "25": "25 de Julho",
    "fl": "Florestal",
    "sap": "Sapiranga",
    "tra": "Travessão",
    "sao": "São",
}

for termo, esperado_contem in buscas.items():
    res = simular_busca(termo)
    assert any(esperado_contem.lower() in x.lower() for x in res), f"Busca por '{termo}' não retornou '{esperado_contem}'. Resultados: {res[:5]}"
    print(f"  Busca '{termo:4}' -> {len(res)} resultados encontrados. Primeiro: '{res[0]}'")

print("\n=== TODOS OS TESTES PASSARAM COM 100% DE SUCESSO! ===")
