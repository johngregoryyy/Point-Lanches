# CLAUDE.md - Guia do Projeto Point Lanches
> **Instruções e diretrizes de desenvolvimento para Claude e outros assistentes de IA**
> Sistema de PDV Desktop e Gestão de Pedidos para *Point Lanches* (Dois Irmãos - RS).

---

## 1. Visão Geral do Projeto

O **Point Lanches** é um sistema desktop comercial para lançamento ágil de pedidos de delivery e balcão, com integração direta a impressoras térmicas ESC/POS (**Elgin i8** de 80mm).

- **Público-alvo:** Operadores de caixa e atendentes de lanchonete em Dois Irmãos - RS.
- **Ambiente de Produção:** Computadores de caixa rodando Windows 10/11, geralmente com monitores de resolução **1366×768** ou Full HD.
- **Modo Gráfico:** 100% gráfico via CustomTkinter (sem console de fundo).
- **Persistência:** Banco de dados local SQLite (`point_lanches.db`), mantido junto ao executável para backup simplificado.

---

## 2. Stack Tecnológica & Dependências

| Tecnologia | Finalidade | Versão Mínima |
| :--- | :--- | :--- |
| **Python** | Runtime principal | 3.10+ (Desenvolvido em 3.14) |
| **CustomTkinter** | Interface gráfica moderna com suporte nativo a Dark Mode | $\ge$ 5.2.2 |
| **Pillow (PIL)** | Manipulação e renderização de imagens e ícones | $\ge$ 10.0.0 |
| **PyInstaller** | Empacotamento em executável Windows (`.exe`) | $\ge$ 6.0.0 |
| **SQLite 3** | Banco de dados relacional embarcado (modo WAL) | Nativo do Python |
| **winspool.drv / ctypes** | Comunicação RAW direta com impressora USB/Spooler Windows | Nativo do Windows |
| **socket** | Comunicação TCP/IP na porta 9100 com impressoras de rede | Nativo do Python |

---

## 3. Estrutura de Diretórios e Arquivos

```text
point_lanches/
├── CLAUDE.md                # Este guia para futuras alterações por IA
├── config.py                # Configurações globais (cores, layout, dados da loja, ruas, auto-update)
├── version.py               # Controle centralizado de versão (__version__)
├── main.py                  # Ponto de entrada (classe App, ciclo de vida, navegação de telas)
├── requirements.txt         # Dependências pip
├── PointLanches.spec        # Especificação PyInstaller para build comercial
├── build.bat                # Script de compilação em 1 clique (PyInstaller)
├── publicar.bat             # Script de compilação + commit/tag + publicação no GitHub Releases
├── iniciar.bat              # Script de inicialização rápida em modo desenvolvimento
├── instalar.bat             # Instalador automático de dependências para novos ambientes
├── point_lanches.db         # Banco de dados SQLite persistente
│
├── database/
│   ├── __init__.py
│   ├── db.py                # Conexão SQLite, migrações, get_base_dir() e operações CRUD
│   └── seed.py              # Cardápio inicial (Tradicionais, Exclusivos, Fritas, Bebidas, etc.)
│
├── printer/
│   ├── __init__.py
│   ├── escpos_printer.py    # Driver de baixo nível (Rede TCP 9100 + USB Windows Spooler)
│   └── ticket_formatter.py  # Montador de bytes ESC/POS com regras de destaque (80mm)
│
├── services/
│   ├── __init__.py
│   └── updater.py           # Auto-updater cliente: checagem em background, download e batch restart
│
├── tools/
│   ├── __init__.py
│   └── publish_release.py   # Script de publicação automatizada (PyInstaller + Git + GitHub Releases)
│
├── ui/
│   ├── __init__.py
│   ├── screen_cart.py       # Tela 1: Cardápio, seleção de produtos e carrinho lateral
│   ├── screen_delivery.py   # Tela 2: Dados do cliente, grid de ruas de Dois Irmãos e taxa
│   ├── screen_payment.py    # Tela 3: Forma de pagamento (PIX/Dinheiro/Cartão) e impressão
│   ├── screen_history.py    # Janela: Histórico de pedidos realizados, reimpressão e exclusão
│   ├── screen_admin.py      # Janela: Configurações, cardápio, taxas, obs rápidas e impressora
│   ├── screen_balanco.py    # Janela: Balanço mensal isolado com gráficos visuais por modalidade
│   └── components/
│       ├── __init__.py
│       └── widgets.py       # Componentes reutilizáveis (TopBar, ProductCard, ChipButton, etc.)
│
└── dist/
    └── PointLanches/
        ├── PointLanches.exe # Executável final distribuível
        └── _internal/       # Bibliotecas e assets empacotados
```

---

## 4. Comandos e Procedimentos de Operação

### 4.1. Execução em Modo de Desenvolvimento
```powershell
# Execução direta via Python
python main.py

# Ou pelo script bat facilitador
.\iniciar.bat
```

### 4.2. Instalação de Dependências
```powershell
pip install -r requirements.txt
```

### 4.3. Geração do Executável (.exe)
Basta executar o script:
```powershell
.\build.bat
```
- **Modo 1 (--onedir) [RECOMENDADO]:** Gera a pasta distribuível `dist\PointLanches\PointLanches.exe`. Abertura instantânea no PDV, resistente a falsos positivos de antivírus e mantém o arquivo `point_lanches.db` na raiz da pasta para backups rápidos.
- **Modo 2 (--onefile):** Gera arquivo único `dist\PointLanches.exe`.

### 4.4. Publicação Automatizada de Releases no GitHub
Para compilar, versionar e publicar uma nova versão com 1 comando:
```powershell
# Execução interativa pelo script batch:
.\publicar.bat

# Ou especificando versão e notas direto pelo terminal:
python tools/publish_release.py 1.0.1 -m "Correções de cupom e melhorias no PDV"
```
O script atualiza `version.py`, dispara o PyInstaller, compacta os artefatos, cria o commit e a tag no Git (`vX.Y.Z`) e publica a release oficial anexando o executável via GitHub CLI (`gh`) ou REST API.

---

## 5. Diretrizes de UI & Design (REGRAS MANDATÓRIAS)

### 5.1. Resolução Alvo: 1366×768 (PDVs e Notebooks)
*Atenção extrema à altura vertical dos elementos!*
- A altura útil na tela 1366×768 com a barra de tarefas do Windows é de **~680px**.
- **Janela Principal:** Definida em `1280x680`. Se `winfo_screenheight() <= 800`, o sistema executa `self.state("zoomed")` para maximizar automaticamente.
- **Janelas Secundárias / Modais:**
  - Modal de Customização de Item (`_abrir_modal_item`): Altura máxima de **550px**. O rodapé (botão de adicionar e quantidade) deve ficar sempre fixado na parte inferior com `pack(side="bottom")`.
  - Janela de Histórico (`ScreenHistory`): Tamanho máximo `1020x560`.
  - Janela de Administração (`ScreenAdmin`): Tamanho máximo `1040x565`. A aba de impressora deve sempre usar `CTkScrollableFrame`.
- **Campos de Entrada (Entries):** Manter `height=34` para não estourar a tela.

### 5.2. Paleta de Cores (REGRA ZERO LARANJA)
**É estritamente proibido o uso de tons de laranja** (como `#F39C12` ou `#E67E22`). A identidade oficial da casa é **Dark Mode com Azul Point**:

```python
# Definidos em config.py
COR_PRIMARIA       = "#0284C7"   # Azul Point vibrante para botões principais e seleção
COR_PRIMARIA_HVR   = "#0369A1"   # Azul escuro hover
COR_SECUNDARIA     = "#1E3A5F"   # Azul marinho complementar
COR_SECUNDARIA_HVR = "#2B4C7E"
COR_AZUL_POINT     = "#38BDF8"   # Azul celeste luminoso para detalhes e destaques
COR_VERDE          = "#10B981"   # Botões de confirmação / Imprimir ("#059669" no hover)
COR_VERMELHO       = "#EF4444"   # Remover / Cancelar ("#DC2626" no hover)
COR_AMARELO        = "#38BDF8"   # Destaques visuais substituídos pelo azul suave
COR_CINZA_CARD     = "#1E2430"   # Fundo de cards de produtos
COR_CINZA_BARRA    = "#141822"   # Barras laterais e painéis estruturais
COR_FUNDO          = "#0F1218"   # Fundo geral dark profundo
COR_TEXTO          = "#FFFFFF"   # Texto principal
COR_TEXTO_SUAVE    = "#94A3B8"   # Texto secundário legível
```

---

## 6. Regras de Impressão ESC/POS (Elgin i8 - 80mm)

As rotinas de impressão ficam em `printer/escpos_printer.py` e `printer/ticket_formatter.py`.

### 6.1. Métodos de Conexão
1. **Rede TCP/IP (Porta 9100):** Envio direto via socket com timeout de 3 segundos.
2. **Cabo USB / Windows Spooler RAW:** Envio via `winspool.drv` chamando `OpenPrinterW`, `StartDocPrinterW`, `WritePrinter` com datatype `"RAW"`. Suporta também portas seriais COM virtuais (`\\.\COMx`).

### 6.2. Larguras e Colunas
- **Modo Normal:** 48 colunas (`COL = 48`). Codificação de texto em `cp850`.
- **Modo Expandido / Dobro do Tamanho (2X):** 24 colunas (`COL_2X = 24`). Comando `GS ! \x11` (`b'\x1d!\x11'`). Desativação com `GS ! \x00` (`b'\x1d!\x00\x1b!\x00'`).

### 6.3. Regras Específicas do Cupom do Point Lanches
1. **Endereço de Entrega (DOBRO DO TAMANHO - 2X):**
   - Rua, Número, Complemento, Bairro e Ponto de Referência devem ser impressos em **dupla largura e dupla altura (2X)**.
   - Usar quebra de linha inteligente (`textwrap.wrap(width=24)`) para jamais cortar palavras ao meio.
2. **Itens da Categoria "Bebidas" (DOBRO DO TAMANHO - 2X):**
   - Se o item pertencer à categoria `"Bebidas"`, ele deve ser impresso em **2X** (24 colunas) para que os atendentes não esqueçam de pegá-lo na geladeira antes de despachar a tele-entrega.
3. **Forma de Pagamento (DOBRO DO TAMANHO - 2X):**
   - Bloco de pagamento impresso em fonte expandida 2X.
4. **Regras de Status do PIX:**
   - Se selecionado **Pago**: imprime `PAGAMENTO: PIX (PAGO)`.
   - Se selecionado **Não Pago**: imprime `PAGAMENTO: PIX (NÃO PAGO)`.
   - Se deixado **Em Branco**: imprime caixas para caneta:
     ```text
     PAGAMENTO: PIX
     [  ] PAGO       [  ] NAO PAGO
     ```
5. **Itens Normais do Pedido e Observações (+30% / Altura Dupla):**
   - Itens de comida usam **Altura Dupla** (`GS ! \x01`), mantendo 48 colunas na Elgin i8 para acomodar Quantidade, Nome e Preço na mesma linha com visual ampliado para a cozinha.

---

## 7. Banco de Dados SQLite & Persistência PyInstaller

Em `database/db.py`, a função `get_base_dir()` é essencial para evitar perda de dados e permissões no Windows:
```python
def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if _can_write_to_dir(exe_dir):
            return exe_dir
        # Fallback para instalação em C:\Program Files sem privilégios de Admin:
        app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        point_data = os.path.join(app_data, "Point Lanches")
        os.makedirs(point_data, exist_ok=True)
        return point_data
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```
> [!IMPORTANT]
> **Nunca** aponte o banco de dados para `sys._MEIPASS`. O `sys._MEIPASS` é uma pasta temporária do PyInstaller que é destruída ao fechar a aplicação. O banco `point_lanches.db` deve sempre ficar no diretório do executável (modo portátil) ou em `%LOCALAPPDATA%\Point Lanches` (modo instalado em Program Files).

### Tabelas Principais:
- `categorias`: ID, Nome
- `produtos`: ID, Categoria_ID, Nome, Descrição, Preço, Ativo
- `adicionais`: ID, Nome, Preço, Ativo
- `taxas_entrega`: ID, Valor, Label, Ativo, Ordem
- `pedidos`: ID, Número sequencial, Cliente (Nome/Telefone), Endereço completo, Valores, Forma de Pagamento, Status, Data/Hora
- `itens_pedido`: ID, Pedido_ID, Produto_ID, Nome, Preço Unitário, Quantidade, Observação, Categoria
- `observacoes_padrao`: ID, Texto da observação, Ativo (carregadas dinamicamente no modal de personalização)
- `ruas`: ID, Nome, Bairro, Taxa, Ativo (base saneada via GeoJSON e enriquecida por auto-cadastro dinâmico de novas vias)
- `historico_enderecos`: ID, Rua (NOCASE), Número (NOCASE), Bairro, Taxa_Frete, Atualizado_Em (histórico inteligente de taxa de entrega por endereço exato)
- `insumos`: ID, Nome, Unidade de Medida, Custo Unitário, Estoque Atual, Ativo (preparação para custos e estoque futuros)
- `movimentacoes_insumos`: ID, Insumo_ID, Tipo (entrada/saida/perda), Quantidade, Valor Total, Data
- `configuracoes`: Chave-Valor (armazena tipo de impressora, IP e nome da impressora USB)

---

## 8. Guia para Adicionar Novas Funcionalidades

### 8.1. Adicionar Novos Produtos ou Categorias
- Para adicionar itens no cardápio de fábrica, edite a lista `CARDAPIO` em `database/seed.py`.
- Em tempo de execução, o operador pode cadastrar novos itens diretamente pela aba **Admin -> Cardápio**.

### 8.2. Base de Ruas, GeoJSON, Auto-Cadastro e Gerador Dinâmico de Acrônimos
- A base de vias fica armazenada na tabela `ruas` do SQLite e é alimentada via `importar_ruas_geojson()` (OpenStreetMap/Overpass API ou lista oficial de Dois Irmãos).
- **Algoritmo de Siglas/Acrônimos 100% Dinâmico (`gerar_acronimos_rua`):**
  - Não utiliza listas manuais fixas. Para qualquer via, descarta prefixos genéricos ("Rua", "Av.", "Estrada") e preposições ("de", "da"), gerando automaticamente as siglas de busca (`sm`, `ar`, `10s`, `nh`, `fl`, `sap`, etc.).
- **Busca de Ruas com Ranking de Relevância e Debounce:**
  - Debounce de 180ms evita travamento da UI durante digitação rápida.
  - Resultados ordenados por relevância e limitados aos 30 mais relevantes.
- **Auto-Cadastro de Ruas Não Mapeadas (`cadastrar_rua_se_inedita`):**
  - Quando o operador digita uma rua inexistente na etapa de entrega e conclui o pedido, o sistema captura o nome, aplica formatação Title Case em português (`formatar_nome_rua`) e verifica duplicidade ignorando acentuação e caixa (`normalizar_rua_para_comparacao`).
  - A nova via é gravada de forma silenciosa na tabela `ruas` vinculada ao bairro e taxa do pedido durante `salvar_pedido`, sem atrasar a impressão do cupom.
  - O barramento `_notificar_ruas_modificadas` sincroniza o cache em memória de `ScreenDelivery` em tempo real, permitindo que a nova rua já apareça nas sugestões/autocomplete dos próximos pedidos e auto-preencha bairro e taxa ao ser clicada.

### 8.3. Controles do Carrinho (CartItem) & Regras de Negócio
- `CartItem` utiliza sub-frame dedicado `qty_frame` com largura fixa de 90px (`pack_propagate(False)`), contendo botões (-) e (+) com 28×28px e label centralizada de 30px, além de preço de 75px e lixeira de 30px. O nome do item utiliza `wraplength=115` e expansão de coluna, impedindo que botões colapsem ou sumam.
- Itens da categoria `"Bebidas"` não exibem observações pré-definidas de lanches.

### 8.4. Exclusão de Pedidos (Lixeira no Histórico)
- Na janela de Histórico (`ScreenHistory`), o botão vermelho `[🗑️ Excluir Pedido]` abre diálogo modal de confirmação antes de remover os registros de `pedidos` e `itens_pedido` no SQLite, limpando o extrato e atualizando a lista instantaneamente.

### 8.5. Balanço Geral do Mês & Fechamento Financeiro (ScreenBalanco)
- Janela isolada dedicada `📊 Balanço Geral` (`ScreenBalanco`), acessada pelo botão `📊` na `TopBar` das telas principais, totalmente desacoplada das configurações administrativas.
- Filtro por Mês e Ano com atualização dinâmica instantânea.
- Cards de destaque: Faturamento Total, Total de Pedidos, Arrecadação de Taxas de Tele, Ticket Médio.
- Gráfico Visual Nativo de Meios de Pagamento (`CTkProgressBar` com proporção percentual, valor R$ e pedidos por modalidade: PIX, Dinheiro, Débito, Crédito).
- Detalhamento tabular consolidado com percentual de participação e botão para copiar o resumo financeiro para o clipboard.
- Estrutura pronta para `Lucro Bruto = Faturamento Total - Custos de Insumos` integrada com as tabelas de insumos do SQLite.

### 8.6. Backup, Restauração e Retrocompatibilidade Inteligente de Banco de Dados (.db / JSON)
- Botões `[💾 Exportar Backup]` e `[📂 Importar Backup]` no cabeçalho do painel administrativo:
  - **Exportação Consistente:** Sugere `PointLanches_Backup_YYYY-MM-DD_HHMM.db`. Realiza `PRAGMA wal_checkpoint(FULL)` e backup atômico nativo via API de backup do SQLite (ou exportação JSON estruturada caso selecionado `.json`).
  - **Importação com Auto-Upgrade e Retrocompatibilidade Total:**
    1. Permite importar bancos `.db` ou `.sqlite` de qualquer versão anterior (ex.: v1.0.2) sem qualquer perda de dados.
    2. **Backup Preventivo Automático:** Gera imediatamente uma cópia de segurança `point_lanches.db.bak` do banco ativo antes de qualquer modificação.
    3. **Substituição Segura sem Lock no Windows:** Sobrescreve as páginas do banco ativo via SQLite `backup()` API, imune a erros de arquivo travado por conexões ativas (`WinError 32`).
    4. **Migração Dinâmica de Schema (`executar_migracoes_retrocompativeis`):**
       - Cria tabelas ausentes (`historico_enderecos`, `ruas`, `observacoes_padrao`, `insumos`, `movimentacoes_insumos`, etc.).
       - Inspeciona todas as colunas existentes via `PRAGMA table_info` e adiciona dinamicamente novas colunas (ex: `taxas_entrega.ordem`, `itens_pedido.categoria`, `ruas.taxa`, etc.) com `ALTER TABLE ADD COLUMN`.
       - Backfill inteligente: popula `historico_enderecos` a partir dos pedidos históricos se estiver vazia.
       - Popula sementes padrão de `ruas` e `observacoes_padrao` se vazias.
    5. **Rollback Automático:** Caso ocorra erro de integridade ou falha no arquivo importado, o sistema restaura o arquivo `.bak` preventivo automaticamente.
    6. Atualiza todas as abas e a interface gráfica do sistema em tempo real (`on_refresh`).

### 8.7. Alterar ou Testar Impressão Térmica
- Acesse a aba **Configurações (Admin) -> Impressora**.
- É possível alternar entre conexão **Rede (TCP/IP)** e **Cabo USB (Spooler)** e disparar um cupom de teste direto da interface gráfica.

### 8.8. Recompilar após Modificações
Sempre que fizer alterações no código Python:
1. Teste localmente com `python main.py` para garantir ausência de erros de sintaxe e quebra de layout.
2. Execute `.\build.bat` e escolha a opção `1` para atualizar os arquivos em `dist\PointLanches`.

### 8.9. Sistema de Auto-Update Contínuo (services/updater.py)
- **Controle Central de Versão:** Arquivo `version.py` com `__version__ = "X.Y.Z"`, exibido discretamente no topo da UI ao lado do logo do Point Lanches e no título do painel administrativo.
- **Checagem Silenciosa em Background:** 2 segundos após iniciar a interface gráfica, uma thread separada consulta `https://api.github.com/repos/{OWNER}/{REPO}/releases/latest`. Em caso de ausência de internet ou indisponibilidade da API, a falha é tratada de forma silenciosa para não interromper o caixa.
- **Diálogo Interativo de Atualização:** Se houver versão mais recente (`is_newer_version`), exibe modal com o changelog oficial e botões `[Atualizar Agora]` e `[Lembrar Mais Tarde]`.
- **Substituição e Reinicialização sem Lock no Windows:**
  - O binário/instalador é baixado em segundo plano com barra de progresso em tempo real em `%TEMP%`.
  - Logs detalhados são registrados em `point_lanches_update.log` e `point_lanches_installer.log`.
  - Dispara processo desanexado (`updater.bat`) com auto-elevação UAC (`runas`), encerra o executável atual, executa a atualização silenciosa com `/DIR` explícito, reinicia o sistema atualizado e apaga os arquivos temporários.

### 8.10. Histórico Inteligente de Frete por Endereço (Rua + Número)
- Memoriza automaticamente a taxa de tele cobrada para a combinação exata de `Rua + Número` ao salvar o pedido (`salvar_pedido`).
- Durante o preenchimento ou seleção de endereço na tela de entrega (`ScreenDelivery`), uma rotina com debounce de 200ms consulta a tabela `historico_enderecos` e auto-preenche a taxa praticada anteriormente (e o bairro se não selecionado), exibindo um feedback visual discreto.
- Permite que o operador altere a taxa manualmente a qualquer momento, atualizando o histórico no fechamento do pedido sem burocracia.

---

## 9. Roadmap / Débito Técnico Futuro

### 9.1. Migração para Banco de Dados Online (Supabase)
- **Persistência Local Atual como Contingência:**
  A validação, persistência e contingência de banco de dados SQLite local (`%LOCALAPPDATA%/PointLanches/data/point_lanches.db`) é uma solução temporária de contingência offline/local para o PDV comercial.
- **Diretriz de Transição para o Supabase (PostgreSQL em Nuvem):**
  No momento em que for solicitada a migração para o Supabase:
  1. A rotina de validação/cópia de banco local de inicialização e migração de arquivos locais deverá ser removida ou adaptada exclusivamente como cache local offline temporário (para operação ininterrupta do caixa em caso de perda de conexão de internet).
  2. As operações de leitura e gravação de pedidos, cardápio, taxas e fechamento financeiro passarão a sincronizar diretamente com as tabelas do PostgreSQL no Supabase via API/SDK.
