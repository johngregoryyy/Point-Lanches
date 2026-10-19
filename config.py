# config.py - Configurações globais do Point Lanches
# =============================================================================

# --- Dados do Estabelecimento ---
ESTABELECIMENTO = "POINT LANCHES"
TELEFONES = "(51) 3564-1305 | (51) 99919-1721 | (51) 98034-8622"
CIDADE = "Dois Irmãos - RS"

# --- Configurações de Auto-Update (GitHub Releases) ---
GITHUB_OWNER = "johngregoryyy"       # Dono ou organização do repositório no GitHub
GITHUB_REPO  = "Point-Lanches"       # Nome do repositório no GitHub
CHECK_UPDATES_ON_STARTUP = True      # Verifica atualizações automaticamente ao iniciar
UPDATE_CHECK_TIMEOUT = 5             # Timeout em segundos para requisições à API

# --- Impressora Elgin i8 ---
PRINTER_TIPO_DEFAULT = "rede"       # "rede" (TCP/IP porta 9100) ou "usb" (Cabo USB Spooler)
PRINTER_IP_DEFAULT   = "192.168.1.100"
PRINTER_PORT         = 9100
PRINTER_TIMEOUT      = 3            # segundos
PRINTER_USB_DEFAULT  = "Elgin i8"   # Nome da impressora instalada no Windows
PRINTER_COLUMNS      = 48           # 80mm = ~48 colunas

# --- Aparência (CustomTkinter) ---
APPEARANCE_MODE = "Dark"
COLOR_THEME = "blue"

# Paleta personalizada (Azul Oficial Point Lanches + Dark Mode Elegante - ZERO LARANJA)
COR_PRIMARIA     = "#0284C7"   # Azul Point vibrante oficial para botões e seleção
COR_PRIMARIA_HVR = "#0369A1"   # Azul Point escuro hover
COR_SECUNDARIA   = "#1E3A5F"   # Azul marinho complementar
COR_SECUNDARIA_HVR = "#2B4C7E"
COR_AZUL_POINT   = "#38BDF8"   # Azul celeste luminoso para detalhes e logo
COR_VERDE        = "#10B981"   # Confirmar / Imprimir
COR_VERDE_HVR    = "#059669"
COR_VERMELHO     = "#EF4444"   # Remover / Cancelar / Alertas
COR_VERMELHO_HVR = "#DC2626"
COR_AMARELO      = "#38BDF8"   # Destaques informativos em azul suave (sem laranja)
COR_CINZA_CARD   = "#1E2430"   # Cards de produtos (dark slate azulado elegante)
COR_CINZA_BARRA  = "#141822"   # Barra lateral e painéis estruturais
COR_TEXTO        = "#FFFFFF"   # Texto principal
COR_TEXTO_SUAVE  = "#94A3B8"   # Texto secundário legível
COR_FUNDO        = "#0F1218"   # Fundo geral dark profundo e confortável
COR_SELECAO      = "#273142"   # Hover em cards e itens neutros


# --- Layout (Otimizado para Monitores 1366x768 e Full HD) ---
LARGURA_JANELA  = 1280
ALTURA_JANELA   = 680
TITULO_APP      = "Point Lanches – Sistema de Pedidos"

# --- Ruas de Dois Irmãos (lista saneada e ampliada) ---
RUAS_DOIS_IRMAOS = [
    # ── Avenidas Principais ──
    "Av. São Miguel",
    "Av. Sapiranga",
    "Av. Florestal",
    "Av. Irineu Becker",
    "Av. Central",
    "Av. das Palmeiras",
    # ── Estradas e Travessões ──
    "Estrada Travessão",
    "Estrada Morro Reuter",
    "Estrada Picada 48",
    "Estrada Linha Imperial",
    # ── Ruas (ordem alfabética) ──
    "Rua 10 de Setembro",
    "Rua 25 de Julho",
    "Rua Acre",
    "Rua Alagoas",
    "Rua Alberto Rübenich",
    "Rua Amazonas",
    "Rua Anita Garibaldi",
    "Rua Bahia",
    "Rua Berlim",
    "Rua Bom Jardim",
    "Rua Carlos Biehl",
    "Rua Ceará",
    "Rua Coronel Pedro Schneider",
    "Rua das Acácias",
    "Rua das Hortênsias",
    "Rua Deodoro da Fonseca",
    "Rua Dom Pedro II",
    "Rua dos Jasmins",
    "Rua Duque de Caxias",
    "Rua Esteio",
    "Rua Floriano Peixoto",
    "Rua Garibaldi",
    "Rua General Osório",
    "Rua Getúlio Vargas",
    "Rua Gramado",
    "Rua Guilherme Schütz",
    "Rua Independência",
    "Rua Ipiranga",
    "Rua João Pessoa",
    "Rua Marechal Deodoro",
    "Rua Maranhão",
    "Rua Minas Gerais",
    "Rua Novo Hamburgo",
    "Rua Olavo Bilac",
    "Rua Osvaldo Cruz",
    "Rua Pará",
    "Rua Paraná",
    "Rua Piauí",
    "Rua Pinheiro Machado",
    "Rua Porto Alegre",
    "Rua Presidente Vargas",
    "Rua Rio Grande do Sul",
    "Rua Santa Catarina",
    "Rua Santa Cruz",
    "Rua São Leopoldo",
    "Rua São Paulo",
    "Rua Sapiranga",
    "Rua Sergipe",
    "Rua Tiradentes",
    "Rua Voluntários da Pátria",
]

# --- Bairros de Dois Irmãos ---
BAIRROS_DOIS_IRMAOS = [
    "Centro",
    "Bela Vista",
    "Floresta",
    "São João",
    "União",
    "Vale Verde",
    "Travessão",
    "Primavera",
    "Navegantes",
    "Portal da Serra",
]

# --- Taxas de Entrega Rápidas ---
TAXAS_RAPIDAS = [5.00, 7.00, 8.00, 10.00]

# --- Observações Rápidas para Lanche ---
OBS_RAPIDAS = [
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

# --- Valores Rápidos de Troco ---
TROCOS_RAPIDOS = [50.00, 100.00, 150.00, 200.00]
