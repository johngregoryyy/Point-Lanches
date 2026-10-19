# Point Lanches 🍔🍕

Sistema PDV e de tele-entrega offline-first em Python e CustomTkinter para lanchonetes e tele-entregas.

## 🚀 Principais Recursos
- **Catálogo Ágil**: Seleção rápida de categorias, adicionais e observações personalizadas salvas em banco.
- **Busca Rápida de Ruas**: Base oficial de logradouros de Dois Irmãos - RS com debounce e busca por abreviações.
- **Impressão Térmica Elgin i8**: Cupom ESC/POS formatado via TCP Socket (porta 9100) e Spooler USB, com suporte completo a caracteres especiais e acentuação (CP850).
- **Histórico de Comandas**: Visualização em tempo real de extratos, reimpressão e exclusão de pedidos.
- **Balanço Geral / Fechamento**: Relatório mensal com indicadores financeiros, detalhamento por modalidade (PIX, Dinheiro, Débito, Crédito) e gráficos nativos embutidos.
- **Distribuição Contínua & Auto-Update**: Verificação automática de versões mais recentes via GitHub Releases e publicação com 1 clique (`publicar.bat`).

## 🛠 Tecnologias
- Python 3.12+ / 3.14
- CustomTkinter
- SQLite
- Matplotlib
- PyInstaller

## 📦 Como Executar
1. Instale as dependências:
   ```cmd
   pip install -r requirements.txt
   ```
2. Inicie o sistema:
   ```cmd
   python main.py
   ```
   Ou clique duas vezes em `iniciar.bat`.

## 🚢 Publicação de Nova Versão
Para compilar e publicar automaticamente uma nova release no GitHub:
```cmd
publicar.bat
```
