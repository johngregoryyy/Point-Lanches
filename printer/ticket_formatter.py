# printer/ticket_formatter.py - Formatação ESC/POS Elgin i8 (80mm / 48 colunas / Destaque 2X)
# =============================================================================

import textwrap
from datetime import datetime
from printer.escpos_printer import (
    _encode, CMD_INIT, CMD_ALIGN_LEFT, CMD_ALIGN_CENTER,
    CMD_BOLD_ON, CMD_BOLD_OFF, CMD_FEED_LINE, CMD_CUT,
    CMD_CODEPAGE_CP850
)
from config import ESTABELECIMENTO, TELEFONES, CIDADE, PRINTER_COLUMNS

COL     = PRINTER_COLUMNS          # 48 colunas (modo normal)
COL_2X  = COL // 2                 # 24 colunas (modo dupla largura/altura)

# Comandos ESC/POS de fonte expandida
CMD_2X_ON   = b'\x1d!\x11'         # GS ! \x11 (dupla altura e dupla largura)
CMD_2X_OFF  = b'\x1d!\x00\x1b!\x00' # GS ! \x00 + ESC ! \x00 (retorno à fonte padrão)

# Comandos ESC/POS de fonte aumentada para Itens do Pedido e Observações
# Utiliza Altura Dupla (GS ! \x01), aumentando a altura do caractere em 100% com
# largura de 48 colunas mantida para perfeita legibilidade na comanda da cozinha.
CMD_ITEM_ON  = b'\x1d!\x01\x1bE\x01'          # GS ! \x01 (Altura Dupla) + Negrito
CMD_OBS_ON   = b'\x1d!\x01\x1bE\x00'          # GS ! \x01 (Altura Dupla)
CMD_ITEM_OFF = b'\x1d!\x00\x1b!\x00\x1bE\x00' # Retorno à fonte padrão


def _linha(char="=") -> bytes:
    return _encode(char * COL) + CMD_FEED_LINE


def _centro(text: str, bold=False) -> bytes:
    text = text[:COL]
    data = CMD_ALIGN_CENTER
    if bold:
        data += CMD_BOLD_ON
    data += _encode(text.center(COL)) + CMD_FEED_LINE
    if bold:
        data += CMD_BOLD_OFF
    return data


def _esquerda(text: str, bold=False) -> bytes:
    text = text[:COL]
    data = CMD_ALIGN_LEFT
    if bold:
        data += CMD_BOLD_ON
    data += _encode(text) + CMD_FEED_LINE
    if bold:
        data += CMD_BOLD_OFF
    return data


def _col2(left: str, right: str, bold=False) -> bytes:
    right = right[-COL:]
    left  = left[:COL - len(right)]
    line  = left.ljust(COL - len(right)) + right
    data  = CMD_ALIGN_LEFT
    if bold:
        data += CMD_BOLD_ON
    data += _encode(line[:COL]) + CMD_FEED_LINE
    if bold:
        data += CMD_BOLD_OFF
    return data


def _col2_item(left: str, right: str, bold: bool = True) -> bytes:
    """
    Imprime 2 colunas com o mesmo tamanho aumentado dos itens de comida
    (GS ! \x01: Altura Dupla + Negrito em 48 colunas).
    """
    right = right[-COL:]
    left  = left[:COL - len(right)]
    line  = left.ljust(COL - len(right)) + right
    cmd_bold = CMD_BOLD_ON if bold else CMD_BOLD_OFF
    return CMD_ALIGN_LEFT + CMD_ITEM_ON + cmd_bold + _encode(line[:COL]) + CMD_FEED_LINE + CMD_ITEM_OFF


def _col3(qty: str, name: str, val: str) -> bytes:
    """4 + (COL-12) + 8 = COL colunas."""
    qty_w  = 4
    val_w  = 8
    name_w = COL - qty_w - val_w
    line   = qty[:qty_w].ljust(qty_w) + name[:name_w].ljust(name_w) + val[:val_w].rjust(val_w)
    return CMD_ALIGN_LEFT + _encode(line[:COL]) + CMD_FEED_LINE


def _imprimir_2x(linhas: list[str]) -> bytes:
    """
    Imprime lista de linhas em fonte expandida / dobro do tamanho (GS ! \x11),
    quebrando em no máximo 24 caracteres por linha sem cortar palavras.
    Desativa o modo expandido imediatamente após o término.
    """
    buf = CMD_2X_ON + CMD_ALIGN_LEFT
    for texto in linhas:
        if not texto:
            continue
        partes = textwrap.wrap(texto, width=COL_2X)
        if not partes:
            partes = [texto]
        for p in partes:
            buf += _encode(p[:COL_2X]) + CMD_FEED_LINE
    buf += CMD_2X_OFF + CMD_ALIGN_LEFT
    return buf


def _formatar_item_aumentado(qtd_str: str, nome: str, val_str: str, obs: str = "") -> bytes:
    """
    Formata o item do pedido e suas observações em fonte aumentada (Altura Dupla GS ! \x01).
    A largura se mantém em 48 colunas na Elgin i8, permitindo que a linha inteira
    (Qtd, Nome do Item, Valor) apareça em tamanho aumentado e perfeitamente legível na cozinha.
    Nomes longos e observações são quebrados de forma inteligente sem cortar palavras.
    """
    qty_w  = 4
    val_w  = 8
    name_w = COL - qty_w - val_w  # 36 colunas

    buf = b""

    # Quebra inteligente do nome caso ultrapasse 36 colunas
    partes_nome = textwrap.wrap(nome, width=name_w)
    if not partes_nome:
        partes_nome = [nome[:name_w]]

    # Primeira linha: [QTD ] + [NOME (parte 1)] + [   VALOR]
    primeira_linha = qtd_str[:qty_w].ljust(qty_w) + partes_nome[0].ljust(name_w) + val_str[:val_w].rjust(val_w)
    buf += CMD_ALIGN_LEFT + CMD_ITEM_ON + _encode(primeira_linha[:COL]) + CMD_FEED_LINE

    # Linhas seguintes do nome (se o nome foi quebrado)
    for sobra in partes_nome[1:]:
        linha_sobra = (" " * qty_w) + sobra.ljust(name_w)
        buf += CMD_ITEM_ON + _encode(linha_sobra[:COL]) + CMD_FEED_LINE

    # Observações (em fonte aumentada também)
    if obs:
        prefixo = "  >> Obs: "
        largura_obs = COL - len(prefixo)
        partes_obs = textwrap.wrap(obs, width=largura_obs)
        if not partes_obs:
            partes_obs = [obs]

        for idx, p_obs in enumerate(partes_obs):
            prefix = prefixo if idx == 0 else (" " * len(prefixo))
            l_obs = prefix + p_obs
            buf += CMD_OBS_ON + _encode(l_obs[:COL]) + CMD_FEED_LINE

    buf += CMD_ITEM_OFF
    return buf


def _is_bebida(item: dict) -> bool:
    """Identifica se o item é da categoria Bebidas."""
    if item.get("eh_bebida"):
        return True
    cat = str(item.get("categoria", "")).lower().strip()
    if any(k in cat for k in ["bebida", "refrigerante", "cerveja", "suco", "agua", "água"]):
        return True
    nome = str(item.get("nome", "")).lower()
    palavras = ["coca", "pepsi", "guaraná", "guarana", "refrigerante", "água", "agua", "cerveja", "suco", "lata 350ml", "lata 475ml", "2 litros", "600 ml"]
    return any(p in nome for p in palavras)


def formatar_ticket(pedido: dict, itens: list, numero: int) -> bytes:
    """
    Gera os bytes ESC/POS completos com:
    - Bloco de Endereço em fonte expandida 2X (GS ! \x11)
    - Itens da categoria Bebidas em fonte expandida 2X (GS ! \x11)
    - Bloco de Pagamento (e status PIX) em fonte expandida 2X (GS ! \x11)
    - Retorno imediato à fonte padrão antes das demais seções
    - Corte final com guilhotina (GS V 0)
    """
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Separar bebidas e outros produtos
    bebidas = [i for i in itens if _is_bebida(i)]
    outros  = [i for i in itens if not _is_bebida(i)]

    buf = b""

    # ── 1. Inicialização + Seleção de Code Page para acentuação correta ──
    buf += CMD_INIT
    buf += CMD_CODEPAGE_CP850  # Garante ç, ã, õ, é, ê, ü na Elgin i8

    # ── 2. Cabeçalho do Estabelecimento ──
    buf += _linha("=")
    buf += CMD_ALIGN_CENTER + CMD_BOLD_ON
    # Nome em destaque 2X centralizado (COL_2X = 24 chars)
    buf += CMD_2X_ON
    buf += _encode(ESTABELECIMENTO.center(COL_2X)) + CMD_FEED_LINE
    buf += CMD_2X_OFF + CMD_BOLD_OFF
    buf += _centro(TELEFONES)
    buf += _linha("=")

    # ── 3. Número e Hora do Pedido ──
    buf += _col2(f"PEDIDO: #{numero:03d}", f"HORA: {agora}")
    buf += _linha("-")

    # ── 4. Dados Básicos do Cliente ──
    nome_cli = pedido.get("cliente_nome", "").strip().upper() or "NÃO INFORMADO"
    fone_cli = pedido.get("cliente_fone", "").strip() or "—"

    buf += _esquerda(f"CLIENTE: {nome_cli}", bold=True)
    buf += _esquerda(f"FONE:    {fone_cli}")
    buf += _linha("-")

    # ── 5. BLOCO DE ENDEREÇO DE ENTREGA EM 2X (GS ! \x11) ──
    rua    = pedido.get("rua", "").strip()
    num    = pedido.get("numero", "").strip()
    comp   = pedido.get("complemento", "").strip()
    bairro = pedido.get("bairro", "").strip()
    ref    = pedido.get("referencia", "").strip()

    endereco = rua
    if num:
        endereco += f", {num}"
    if comp:
        endereco += f" - {comp}"

    linhas_entrega = []
    if endereco.strip():
        linhas_entrega.append(f"ENTREGA: {endereco.upper()}")
    if bairro:
        linhas_entrega.append(f"BAIRRO: {bairro.upper()} - {CIDADE.upper()}")
    if ref:
        linhas_entrega.append(f"REF: {ref.upper()}")

    if linhas_entrega:
        buf += _imprimir_2x(linhas_entrega)
        buf += _linha("-")

    # ── 6. Itens do Pedido (Tradicionais, Lanches, etc.) ──
    if outros:
        buf += CMD_ALIGN_LEFT + CMD_BOLD_ON
        buf += _col3("QTD", "ITEM", "VALOR")
        buf += CMD_BOLD_OFF
        buf += _linha("-")

        for item in outros:
            nome_i = item.get("nome", "")
            qtd    = item.get("quantidade", 1)
            preco  = item.get("preco_unit", 0.0)
            obs    = item.get("observacao", "").strip()
            total_item = qtd * preco
            val_formatado = f"{total_item:.2f}".replace(".", ",")

            buf += _formatar_item_aumentado(
                qtd_str=f"{qtd}x",
                nome=nome_i,
                val_str=val_formatado,
                obs=obs
            )
        buf += _linha("-")

    # ── 7. SEÇÃO BEBIDAS / GELADEIRA (COM VALORES) ──
    if bebidas:
        buf += _linha("=")
        buf += _centro("*** BEBIDAS / GELADEIRA ***", bold=True)
        buf += _linha("-")
        buf += CMD_ALIGN_LEFT + CMD_BOLD_ON
        buf += _col3("QTD", "ITEM", "VALOR")
        buf += CMD_BOLD_OFF
        buf += _linha("-")

        for b in bebidas:
            qtd = b.get("quantidade", 1)
            nome_b = b.get("nome", "").upper()
            preco_b = b.get("preco_unit", 0.0)
            obs_b = b.get("observacao", "").strip()
            total_b = qtd * preco_b
            val_formatado = f"{total_b:.2f}".replace(".", ",")

            buf += _formatar_item_aumentado(
                qtd_str=f"{qtd}x",
                nome=nome_b,
                val_str=val_formatado,
                obs=obs_b
            )
        buf += _linha("=")

    # ── 8. Totais do Pedido (Mesmo tamanho aumentado dos itens de comida) ──
    subtotal     = pedido.get("subtotal", 0)
    taxa_entrega = pedido.get("taxa_entrega", 0)
    total        = pedido.get("total", 0)

    sub_str   = f"R$ {subtotal:.2f}".replace(".", ",")
    taxa_str  = f"R$ {taxa_entrega:.2f}".replace(".", ",")
    total_str = f"R$ {total:.2f}".replace(".", ",")

    buf += _col2_item("Subtotal:", sub_str, bold=True)
    buf += _col2_item("Taxa de Entrega:", taxa_str, bold=True)
    buf += _linha("-")
    buf += _col2_item("TOTAL:", total_str, bold=True)
    buf += _linha("-")

    # ── 9. FORMA DE PAGAMENTO EM 2X (GS ! \x11) ──
    forma_pgto = str(pedido.get("forma_pgto", "")).strip()
    valor_pago = pedido.get("valor_pago", 0)
    troco      = pedido.get("troco", 0)
    pix_status = str(pedido.get("pix_status", "")).strip()

    linhas_pgto = []
    forma_upper = forma_pgto.upper()

    if "PIX" in forma_upper:
        # Se operador marcou 'Pago'
        if "PAGO" in forma_upper and "NÃO" not in forma_upper and "NAO" not in forma_upper or pix_status.lower() == "pago":
            linhas_pgto.append("PAGAMENTO: PIX (PAGO)")
        # Se operador marcou 'Não Pago'
        elif "NÃO PAGO" in forma_upper or "NAO PAGO" in forma_upper or pix_status.lower() in ["não pago", "nao pago"]:
            linhas_pgto.append("PAGAMENTO: PIX")
            linhas_pgto.append("(NAO PAGO)")
        else:
            # Em branco: imprimir caixas para marcação manual com caneta
            linhas_pgto.append("PAGAMENTO: PIX")
            linhas_pgto.append("[  ] PAGO  [  ] NAO PAGO")
    elif "DINHEIRO" in forma_upper:
        linhas_pgto.append("PAGAMENTO: DINHEIRO")
        if valor_pago > 0:
            linhas_pgto.append(f"LEVAR P/ R$ {valor_pago:.2f}")
        if troco > 0:
            linhas_pgto.append(f"TROCO: R$ {troco:.2f}")
    else:
        linhas_pgto.append(f"PAGTO: {forma_upper}")

    buf += _imprimir_2x(linhas_pgto)

    # ── 10. Rodapé e Corte Guilhotina ──
    buf += _linha("=")
    buf += _centro("Obrigado pela preferência!")
    buf += _linha("=")
    buf += CMD_FEED_LINE * 4
    buf += CMD_CUT

    return buf
