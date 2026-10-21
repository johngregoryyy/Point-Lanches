# Point Lanches 🍔🍟🛵

<div align="center">

![Versão](https://img.shields.io/badge/Vers%C3%A3o-1.1.7-00C853?style=for-the-badge&logo=git)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/Interface-CustomTkinter-1f538d?style=for-the-badge)
![Supabase](https://img.shields.io/badge/Cloud-Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![Impressão](https://img.shields.io/badge/Impressora-Elgin%20i8%20(ESC%2FPOS)-FF6D00?style=for-the-badge)
![Plataforma](https://img.shields.io/badge/SO-Windows%2010%20%7C%2011-0078D6?style=for-the-badge&logo=windows)

**Sistema Comercial de Ponto de Venda (PDV) e Tele-Entrega de Alta Performance**  
*Desenvolvido sob medida para operações rápidas de lanchonete, balcão e delivery.*

[Novidades v1.1.7](https://github.com/johngregoryyy/Point-Lanches/releases/tag/v1.1.7) •
[Instalação](#-instalação-e-execução) •
[Recursos](#-principais-recursos) •
[Arquitetura](#-arquitetura-e-tecnologias) •
[Impressão](#-integração-com-impressora-elgin-i8)

</div>

---

## 📖 Visão Geral

O **Point Lanches** é uma solução desktop comercial completa para frente de caixa, lançamento ágil de pedidos e gestão de tele-entrega. Projetado com filosofia **Offline-First**, o sistema garante que o operador continue atendendo e imprimindo comandas normalmente mesmo em momentos de oscilação ou queda total da internet.

Com interface gráfica moderna em modo escuro nativo (*CustomTkinter*), o sistema é otimizado para telas sensíveis ao toque, teclados de balcão e monitores de resolução **1366×768** a **Full HD**, operando com baixíssimo consumo de memória e latência zero de resposta (0ms de travamento de UI).

---

## 🚀 Principais Recursos

### 🍔 1. Cardápio Dinâmico e Regras Inteligentes
- **Navegação por Categorias:** Filtros ágeis (Xis, Lanches, Bebidas, Porções, Extras) com contadores em tempo real.
- **Diferenciação Comida vs. Bebida:** Chave seletora por categoria que identifica automaticamente produtos do tipo bebida, suprimindo adicionais e observações rápidas para acelerar o lançamento.
- **Personalização de Itens:** Pop-up com seleção de adicionais múltiplos (+ Bacon, + Queijo, etc.) e observações rápidas dinâmicas (*"Sem Cebola"*, *"Molho à Parte"*, *"Bem Passado"*), com edição cadastral direto no painel administrativo.
- **Carrinho Lateral Fixo:** Visualização contínua dos itens adicionados, edição de quantidade, remoção rápida e cálculo dinâmico de subtotal.

### 🛵 2. Módulo de Tele-Entrega & Inteligência Geográfica
- **Base Oficial de Dois Irmãos - RS:** Mais de 60 vias mapeadas e categorizadas (avenidas, travessões, estradas e bairros).
- **Busca Preditiva com Debounce:** Digitação fluida de endereços com reconhecimento inteligente de abreviações e acrônimos comuns (`sm` → *Av. São Miguel*, `ib` → *Av. Irineu Becker*, `ar` → *Alberto Rübenich*, `poa` → *Porto Alegre*, `25` → *25 de Julho*).
- **Chips de Taxas Rápidas:** Seleção de valores pré-configurados por bairro ou entrada manual facilitada.
- **Memória de Entrega:** Preenchimento automático de cliente e telefone com isolamento rigoroso entre pedidos.

### 💳 3. Checkout e Formas de Pagamento
- **Múltiplas Modalidades:** Suporte nativo a **Dinheiro**, **PIX**, **Cartão de Débito** e **Cartão de Crédito**.
- **Calculadora Automática de Troco:** Campo interativo para inserção de valor recebido com cálculo instantâneo do troco a devolver.
- **Chave PIX Pronta:** Exibição imediata da chave Pix e instruções para o operador de caixa.
- **Seleção Estável:** Seleção persistente em destaque azul Point sem conflitos visuais de desmarque.

### 🖨️ 4. Impressão Térmica ESC/POS (Elgin i8 - 80mm)
- **Comunicação Híbrida Direta:**
  - **Rede Ethernet/Wi-Fi:** Conexão direta via TCP Socket na porta `9100`.
  - **Cabo USB / Spooler Windows:** Comunicação RAW via `winspool.drv` sem depender de drivers gráficos externos.
- **Acentuação Perfeita em Português:** Codificação via página de código **CP850** com tabela de normalização de caracteres para a Elgin i8, garantindo acentuação gráfica correta (`ç`, `ã`, `õ`, `é`, etc.) sem caracteres estranhos na bobina.
- **Detecção Real de Impressora Offline:** Consulta o status do hardware antes de enviar a impressão. Se a impressora estiver desligada, sem cabo ou sem papel, emite alerta preventivo com opção de tentar novamente ou concluir sem travar a venda.
- **Recibo de Saída Padronizado:** Cabeçalho com dados da loja e contatos atualizados, formatação clara dos itens e bebidas com preços alinhados e totais com destaque ampliado.

### ☁️ 5. Sincronização em Nuvem (Supabase REST)
- **Arquitetura Híbrida Offline-First:** Opera localmente no SQLite (`point_lanches.db`) e sincroniza com a nuvem em segundo plano sem congelar a tela.
- **Sincronização Bidirecional CRUD:** Inclusões, edições e exclusões no painel administrativo e novos pedidos são replicados em tempo real via REST API.
- **Renovação Automática de Sessão (Auto-Refresh):** Token JWT atualizado de forma invisível via refresh token, prevenindo deslogamentos ou falhas 401.
- **Sincronização de Histórico:** Envio de pedidos pendentes para o banco central na nuvem e download automático em novos terminais instalados.

### 📊 6. Balanço Geral, Métricas e Dashboard de Picos
- **Estatísticas de Vendas:** Faturamento bruto, total de taxas de entrega, ticket médio e volume de pedidos por período (diário, mensal ou anual).
- **Novo Gráfico de Horários de Pico:**
  - **Por Horário do Dia:** Gráfico interativo indicando as faixas horárias de maior demanda (destaque dourado para o horário campeão).
  - **Por Dia da Semana:** Mapeamento visual de Domingo a Sábado apontando o dia mais movimentado da operação.
  - **Evolução Histórica:** Curva comparativa de faturamento diário e mensal.
- **Exportação Rápida:** Botão para cópia do resumo executivo consolidado para o clipboard (WhatsApp/relatórios).

### 📜 7. Central de Logs de Erros e Auditoria (Novo na v1.1.6)
- **Acesso Rápido na Barra Superior:** Botão `📜` ao lado de `⚙ Ajustes` para abertura imediata pelo suporte ou operador.
- **Captura Global de Exceções:** Handlers automáticos instalados no Tkinter (`report_callback_exception`), no interpretador (`sys.excepthook`) e em threads assíncronas (`threading.excepthook`).
- **Painel de Diagnóstico em 2 Colunas:** Listagem cronológica agrupada por data/hora, badges de status por gravidade (Crítico, Erro, Exceção, Impressora, Rede, Supabase) e visualizador com cópia rápida do traceback.
- **Auditoria Remota:** Logs salvos localmente e enviados em background para o Supabase para monitoramento centralizado de problemas de hardware ou rede.

---

## 🛠 Arquitetura e Tecnologias

```
point_lanches/
├── main.py                  # Ponto de entrada, ciclo de vida e gerenciamento de telas
├── config.py                # Cores, layouts, regras de negócio e constantes de rede
├── version.py               # Controle centralizado da versão (v1.1.7)
├── point_lanches.db         # Banco de dados local SQLite (modo WAL de alto desempenho)
│
├── database/                # Camada de Persistência Local
│   ├── db.py                # Conexão thread-safe, migrações e operações CRUD
│   └── seed.py              # Carga inicial de cardápio, adicionais, taxas e ruas
│
├── services/                # Camada de Serviços e Integrações
│   ├── supabase_client.py   # Gerenciamento de autenticação e tokens JWT do Supabase
│   ├── supabase_sync.py     # Motor de sincronização em lote assíncrono
│   └── error_logger.py      # Captura global de exceções e auditoria
│
├── printer/                 # Camada de Impressão ESC/POS
│   ├── escpos_printer.py    # Drivers de comunicação via TCP 9100 e Winspool RAW
│   └── ticket_formatter.py  # Montagem binária do cupom térmico e formatação
│
├── ui/                      # Camada de Apresentação (CustomTkinter)
│   ├── screen_cart.py       # Tela 1: Cardápio, seleção de produtos e carrinho
│   ├── screen_delivery.py   # Tela 2: Dados de entrega, busca de ruas e taxas
│   ├── screen_payment.py    # Tela 3: Pagamento, troco, PIX e confirmação
│   ├── screen_admin.py      # Tela 4: Gestão do cardápio, adicionais, taxas e impressora
│   ├── screen_history.py    # Tela 5: Histórico de comandas, reimpressão e exclusão
│   ├── screen_balanco.py    # Tela 6: Balanço financeiro e gráficos de picos
│   ├── screen_logs.py       # Tela 7: Central de logs de erro e auditoria
│   ├── screen_auth.py       # Modal de login/autenticação no Supabase
│   └── components/          # Widgets reutilizáveis (TopBar, Card, ChipButton, Modais)
│
├── tools/                   # Ferramentas de Manutenção e Deploy
│   └── publish_release.py   # Publicador automático de releases no GitHub
└── installer/               # Empacotamento Comercial
    └── setup.iss            # Script de compilação do instalador oficial Inno Setup
```

---

## ⚡ Desempenho e Engenharia de Baixa Latência

Para garantir que o software execute com máxima velocidade mesmo sob alta demanda em equipamentos de balcão (testado e calibrado para processadores Intel Core i5 de 10ª geração com 16 GB de RAM):
- **SQLite em Modo WAL com 64 MB de Cache em RAM:** Operações de escrita não bloqueiam leituras e consultas ao catálogo respondem em menos de 1 milissegundo.
- **Conexões por Thread (`threading.local`):** Evita criação e destruição repetitiva de instâncias de conexão de banco.
- **Gravação em Lote Atômica (`executemany`):** Redução de até 95% do tempo de I/O de disco durante sincronizações de catálogo e pedidos.
- **Pool de Conexões Concorrente:** Requisições ao Supabase REST utilizam `ThreadPoolExecutor` com 7 threads paralelas, baixando o tempo de sincronização completa de ~2s para menos de 250ms.
- **Cache de Interface em Memória:** As telas de cardápio e busca preservam estados e índices em memória RAM, sem reconstruções pesadas de widgets entre transições de tela.

---

## 💻 Instalação e Execução

### Opção 1: Executável Instalador (Recomendado para Produção)
Baixe o instalador mais recente na página de [Releases](https://github.com/johngregoryyy/Point-Lanches/releases):
1. Execute o arquivo `PointLanches-Setup-v1.1.7.exe`.
2. Siga o assistente de instalação (cria atalho na Área de Trabalho e no Menu Iniciar).
3. O sistema já vem pronto para uso, com auto-atualizador embutido.

### Opção 2: Execução a partir do Código Fonte (Desenvolvimento)
**Pré-requisitos:** Python 3.10 ou superior instalado.

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/johngregoryyy/Point-Lanches.git
   cd Point-Lanches
   ```

2. **Crie e ative um ambiente virtual (opcional, porém recomendado):**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```
   *Ou execute o script em 1 clique:* `instalar.bat`

4. **Inicie o sistema:**
   ```bash
   python main.py
   ```
   *Ou dê um duplo clique no arquivo:* `iniciar.bat`

---

## 🖨 Integração com Impressora Elgin i8

O sistema é homologado e testado com bobinas térmicas de 80mm:

1. Acesse o painel de **⚙ Ajustes** (`ScreenAdmin`) e navegue até a aba **🖨 Impressora**.
2. Escolha o modo de conexão:
   - **Cabo USB (Spooler Windows):** Selecione a fila de impressão da Elgin i8 instalada no Windows. O sistema se comunica diretamente com a porta RAW via Winspool.
   - **Rede (TCP/IP):** Informe o IP estático da impressora na rede local (Porta padrão: `9100`).
3. Clique em **"Testar Impressão"** para validar a comunicação e o corte de papel automático da guilhotina.

---

## 🚢 Compilação e Deploy Automatizado

O repositório possui rotinas prontas para empacotamento e distribuição:

- **Compilação Local:**
  ```cmd
  build.bat
  ```
  Gera a distribuição portável e o binário em `dist/PointLanches/PointLanches.exe`.

- **Publicação de Release no GitHub (com Inno Setup):**
  ```cmd
  publicar.bat
  ```
  Executa validação, versionamento no `version.py`, compilação PyInstaller, geração do instalador `.exe` via Inno Setup, criação de tags no Git e upload dos binários na aba de Releases do GitHub através do GitHub CLI.

---

## 📄 Licença

Este projeto é desenvolvido para uso comercial e operacional interno do **Point Lanches** (Dois Irmãos - RS). Todos os direitos reservados.
