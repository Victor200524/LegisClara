"""
Módulo de OCR baseado no PaddleOCR 3.x (API `PaddleOCR(...).predict(...)`).

Responsabilidades:
- localizar documentos e páginas (imagens ou PDFs) nas pastas de entrada;
- executar o PaddleOCR em português, na CPU;
- reconstruir a ordem de leitura (inclusive em páginas com duas colunas);
- sinalizar trechos que precisam de revisão humana, SEM corrigir o texto;
- gravar TXT, JSON por página e o texto consolidado do documento.

Princípio fundamental: o texto gravado é exatamente o que o modelo reconheceu.
Nenhuma correção ortográfica, normalização ou reescrita é aplicada.
"""

from __future__ import annotations

import json
import os
import re
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

import numpy as np

from scripts import preprocessamento as pre

# Evita a verificação de conectividade com os servidores de modelos a cada
# execução (os modelos ficam em cache em ~/.paddlex após o primeiro download).
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
EXTENSOES_PDF = {".pdf"}
SUBPASTA_IMAGENS = "imagens_do_documento"
DPI_PDF = int(os.environ.get("OCR_DPI_PDF", "300"))  # resolução para rasterizar PDFs (menor = menos memória)


# ---------------------------------------------------------------------------
# Descoberta de documentos e páginas
# ---------------------------------------------------------------------------

def _chave_ordenacao_natural(nome: str) -> list:
    """Ordena 'pagina_2' antes de 'pagina_10' (ordenação natural)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", nome)]


@dataclass
class Pagina:
    """Uma página a ser processada (uma imagem ou uma página de PDF)."""
    numero: int                          # posição no documento (1, 2, 3...)
    origem: str                          # nome do arquivo (e página do PDF, se for o caso)
    carregar: Callable[[], np.ndarray]   # função que devolve a imagem BGR


def _rasterizar_pagina_pdf(caminho: Path, indice: int) -> np.ndarray:
    """Converte uma página de PDF em imagem BGR usando PyMuPDF."""
    import fitz  # PyMuPDF; importado sob demanda

    with fitz.open(caminho) as pdf:
        pix = pdf[indice].get_pixmap(dpi=DPI_PDF, colorspace=fitz.csRGB, alpha=False)
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        return rgb[:, :, ::-1].copy()  # RGB -> BGR


def listar_paginas(pasta_documento: Path) -> list[Pagina]:
    """
    Lista as páginas de um documento em ordem natural de nome de arquivo.
    PDFs são expandidos em uma página por folha.
    """
    pasta = pasta_documento / SUBPASTA_IMAGENS
    if not pasta.is_dir():
        pasta = pasta_documento  # tolera imagens colocadas diretamente na pasta do documento

    arquivos = sorted(
        (a for a in pasta.iterdir() if a.is_file() and a.suffix.lower() in EXTENSOES_IMAGEM | EXTENSOES_PDF),
        key=lambda a: _chave_ordenacao_natural(a.name),
    )

    paginas: list[Pagina] = []
    for arquivo in arquivos:
        if arquivo.suffix.lower() in EXTENSOES_PDF:
            import fitz

            try:
                with fitz.open(arquivo) as pdf:
                    total = pdf.page_count
            except Exception as erro:  # PDF corrompido ou protegido
                print(f"  [ERRO] Não foi possível abrir o PDF {arquivo.name}: {erro}")
                continue
            for i in range(total):
                paginas.append(Pagina(
                    numero=len(paginas) + 1,
                    origem=f"{arquivo.name}#pagina={i + 1}",
                    carregar=lambda a=arquivo, i=i: _rasterizar_pagina_pdf(a, i),
                ))
        else:
            paginas.append(Pagina(
                numero=len(paginas) + 1,
                origem=arquivo.name,
                carregar=lambda a=arquivo: pre.carregar_imagem(a),
            ))
    return paginas


# ---------------------------------------------------------------------------
# Motor de OCR
# ---------------------------------------------------------------------------

class MotorOCR:
    """
    Encapsula o pipeline PaddleOCR 3.x. O modelo é carregado uma única vez e
    reutilizado para todas as páginas.

    Configuração padrão:
    - lang="pt": seleciona o reconhecedor latino (latin_PP-OCRv5_mobile_rec),
      que cobre os caracteres do português (á, ç, õ, º, ª, § ...);
    - device="cpu": não exige GPU;
    - classificação de orientação e "unwarping" desativados: as páginas
      já estão na orientação correta e o unwarping pode deformar o texto.
    """

    def __init__(self, idioma: str = "pt", dispositivo: str = "cpu", **parametros_extras):
        from paddleocr import PaddleOCR  # import pesado; feito apenas quando necessário

        self.parametros = {
            "lang": idioma,
            "device": dispositivo,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
            **parametros_extras,
        }
        self._ocr = PaddleOCR(**self.parametros)
        self._versoes = None

    def versoes(self) -> dict:
        """Versões das bibliotecas, para rastreabilidade dos experimentos."""
        if self._versoes is None:
            import paddle
            import paddleocr

            self._versoes = {"paddleocr": paddleocr.__version__, "paddlepaddle": paddle.__version__}
        return self._versoes

    def reconhecer(self, imagem: np.ndarray) -> dict:
        """Executa detecção + reconhecimento e devolve o resultado bruto (dict serializável)."""
        resultados = self._ocr.predict(imagem)
        if not resultados:
            return {}
        return resultados[0].json.get("res", {})


# ---------------------------------------------------------------------------
# Ordem de leitura
# ---------------------------------------------------------------------------

def _detectar_divisoria_colunas(caixas: list[list[float]], largura: int) -> tuple[float, float] | None:
    """
    Procura um "corredor" vertical vazio entre 30% e 70% da largura da página,
    considerando apenas caixas estreitas (linhas que não ocupam a página inteira).
    Retorna (x_inicio, x_fim) do corredor ou None se a página tiver uma coluna.
    """
    estreitas = [c for c in caixas if (c[2] - c[0]) < 0.55 * largura]
    if len(estreitas) < 6:
        return None

    ocupacao = np.zeros(largura + 1, dtype=np.int32)
    for x1, _, x2, _ in estreitas:
        ocupacao[max(0, int(x1)):min(largura, int(x2)) + 1] += 1

    # Cabeçalhos centralizados e números de página podem atravessar o corredor entre as
    # colunas; por isso tolera-se um pequeno número de caixas cruzando a divisória.
    # Esses elementos são tratados depois como "largura total" em ordenar_leitura().
    tolerancia = max(2, int(0.03 * len(estreitas)))
    inicio_busca, fim_busca = int(0.30 * largura), int(0.70 * largura)
    melhor, atual_inicio = (0, None, None), None
    for x in range(inicio_busca, fim_busca + 1):
        if ocupacao[x] <= tolerancia:
            atual_inicio = x if atual_inicio is None else atual_inicio
            comprimento = x - atual_inicio + 1
            if comprimento > melhor[0]:
                melhor = (comprimento, atual_inicio, x)
        else:
            atual_inicio = None

    if melhor[1] is None:
        return None
    x_ini, x_fim = melhor[1], melhor[2]
    esquerda = sum(1 for c in estreitas if c[2] <= x_ini)
    direita = sum(1 for c in estreitas if c[0] >= x_fim)
    # Exige quantidade relevante de linhas em ambos os lados para evitar falsos positivos
    if esquerda < 3 or direita < 3 or min(esquerda, direita) < 0.2 * len(estreitas):
        return None
    return float(x_ini), float(x_fim)


def _agrupar_em_linhas(itens: list[dict]) -> list[list[dict]]:
    """Agrupa caixas que estão na mesma altura (mesma linha visual) e ordena da esquerda para a direita."""
    linhas: list[list[dict]] = []
    for item in sorted(itens, key=lambda i: (i["caixa"][1] + i["caixa"][3]) / 2):
        y1, y2 = item["caixa"][1], item["caixa"][3]
        if linhas:
            ref = linhas[-1]
            ry1 = min(i["caixa"][1] for i in ref)
            ry2 = max(i["caixa"][3] for i in ref)
            sobreposicao = min(y2, ry2) - max(y1, ry1)
            if sobreposicao > 0.5 * min(y2 - y1, ry2 - ry1):
                ref.append(item)
                continue
        linhas.append([item])
    return [sorted(linha, key=lambda i: i["caixa"][0]) for linha in linhas]


def ordenar_leitura(itens: list[dict], largura: int, detectar_colunas: bool = True) -> tuple[list[list[dict]], dict]:
    """
    Reconstrói a sequência de leitura.

    Página de uma coluna: de cima para baixo, da esquerda para a direita.
    Página de duas colunas: a página é dividida em faixas horizontais
    separadas por elementos que atravessam a divisória (títulos, cabeçalhos);
    em cada faixa lê-se toda a coluna esquerda e depois toda a direita.
    """
    if not itens:
        return [], {"colunas": 0}

    divisoria = _detectar_divisoria_colunas([i["caixa"] for i in itens], largura) if detectar_colunas else None
    if divisoria is None:
        for item in itens:
            item["coluna"] = 1
        return _agrupar_em_linhas(itens), {"colunas": 1}

    x_ini, x_fim = divisoria
    ordenados = sorted(itens, key=lambda i: i["caixa"][1])
    resultado: list[list[dict]] = []
    esquerda: list[dict] = []
    direita: list[dict] = []

    def descarregar_faixa():
        resultado.extend(_agrupar_em_linhas(esquerda))
        resultado.extend(_agrupar_em_linhas(direita))
        esquerda.clear()
        direita.clear()

    for item in ordenados:
        x1, _, x2, _ = item["caixa"]
        if x1 < x_ini and x2 > x_fim:  # atravessa a divisória: elemento de largura total
            item["coluna"] = 0
            descarregar_faixa()
            resultado.append([item])
        elif (x1 + x2) / 2 < (x_ini + x_fim) / 2:
            item["coluna"] = 1
            esquerda.append(item)
        else:
            item["coluna"] = 2
            direita.append(item)
    descarregar_faixa()
    return resultado, {"colunas": 2, "divisoria_x": [x_ini, x_fim]}


# ---------------------------------------------------------------------------
# Sinalização para revisão humana (nunca altera o texto)
# ---------------------------------------------------------------------------

# Token com letras e dígitos misturados (ex.: "0UTUBRO", "Art.l0"), exceto ordinais
# legítimos como "1º", "2ª", "nº" e numerações como "10.741".
_RE_TOKEN = re.compile(r"\S+")
_RE_ORDINAL_OK = re.compile(r"^\(?\d+[ºª°]?[.,;:)]*$|^n[ºo°]\.?\d*[.,;:]*$", re.IGNORECASE)


def sinais_de_ambiguidade(texto: str) -> list[str]:
    """
    Heurísticas de caracteres possivelmente confundidos em textos jurídicos.
    Apenas APONTA o problema para revisão humana; não corrige nada.
    """
    sinais = []
    for token in _RE_TOKEN.findall(texto):
        limpo = token.strip("()[]{}\"'“”.,;:!?")
        if not limpo or _RE_ORDINAL_OK.match(limpo):
            continue
        tem_letra = any(c.isalpha() and c not in "ºª" for c in limpo)
        tem_digito = any(c.isdigit() for c in limpo)
        if tem_letra and tem_digito and not re.fullmatch(r"\d+[ºª°]?-?[A-Z]", limpo):
            sinais.append(f"mistura de letras e dígitos em '{token}' (ex.: O/0, l/1, S/5)")
    # Símbolo de grau (°, U+00B0) onde normalmente se usa o ordinal (º, U+00BA)
    if re.search(r"(?:Art\.?|§|n|N|\d)\s*°", texto):
        sinais.append("símbolo de grau '°' em possível posição de ordinal 'º' (Art. 1º, nº, § 1º)")
    return sinais


# ---------------------------------------------------------------------------
# Processamento de uma página e de um documento
# ---------------------------------------------------------------------------

def nome_pagina(numero: int) -> str:
    return f"pagina_{numero:03d}"


def processar_pagina(
    motor: MotorOCR,
    pagina: Pagina,
    documento: str,
    perfil: str,
    pasta_saida: Path,
    limiar_confianca: float,
    detectar_colunas: bool = True,
    salvar_imagem_processada: bool = False,
) -> dict:
    """
    Processa uma página e grava `pagina_NNN.txt` e `pagina_NNN.json`.
    Em caso de erro grava apenas o JSON com a descrição do erro e retorna normalmente,
    para que o restante do lote continue sendo processado.
    """
    base = nome_pagina(pagina.numero)
    registro: dict = {
        "documento": documento,
        "pagina": pagina.numero,
        "imagem_origem": pagina.origem,
        "perfil_preprocessamento": perfil,
        "etapas_preprocessamento": pre.PERFIS[perfil],
        "limiar_confianca_revisao": limiar_confianca,
        "parametros_paddleocr": motor.parametros,
        "versoes": motor.versoes(),
    }
    try:
        inicio = time.perf_counter()
        imagem = pagina.carregar()
        imagem = pre.aplicar_perfil(imagem, perfil)
        registro["tempo_preprocessamento_s"] = round(time.perf_counter() - inicio, 4)
        registro["dimensoes_imagem"] = {"largura": int(imagem.shape[1]), "altura": int(imagem.shape[0])}
        if salvar_imagem_processada and perfil != "original":
            pre.salvar_imagem(imagem, pasta_saida / f"{base}_entrada.png")

        inicio = time.perf_counter()
        bruto = motor.reconhecer(imagem)
        registro["tempo_ocr_s"] = round(time.perf_counter() - inicio, 4)

        textos = bruto.get("rec_texts", []) or []
        confiancas = bruto.get("rec_scores", []) or []
        caixas = bruto.get("rec_boxes", []) or []
        poligonos = bruto.get("rec_polys", []) or []

        itens = [
            {
                "indice_paddleocr": i,
                "texto": texto,
                "confianca": float(confiancas[i]) if i < len(confiancas) else None,
                "caixa": [float(v) for v in caixas[i]] if i < len(caixas) else [0, 0, 0, 0],
                "poligono": poligonos[i] if i < len(poligonos) else None,
            }
            for i, texto in enumerate(textos)
        ]
        linhas_visuais, layout = ordenar_leitura(itens, imagem.shape[1], detectar_colunas)

        # Texto final: cada linha visual vira uma linha do TXT; os fragmentos de uma
        # mesma linha são unidos por espaço. O conteúdo de cada fragmento é o bruto do modelo.
        linhas_texto = [" ".join(item["texto"] for item in linha) for linha in linhas_visuais]
        texto = "\n".join(linhas_texto)

        revisao = []
        for n_linha, linha in enumerate(linhas_visuais, start=1):
            for item in linha:
                motivos = []
                if item["confianca"] is not None and item["confianca"] < limiar_confianca:
                    motivos.append(f"confiança {item['confianca']:.3f} abaixo do limiar {limiar_confianca}")
                motivos.extend(sinais_de_ambiguidade(item["texto"]))
                if motivos:
                    revisao.append({
                        "linha_txt": n_linha,
                        "indice_paddleocr": item["indice_paddleocr"],
                        "texto_bruto": item["texto"],
                        "confianca": item["confianca"],
                        "motivos": motivos,
                    })

        confs = [i["confianca"] for i in itens if i["confianca"] is not None]
        registro.update({
            "status": "ok",
            "layout": layout,
            "quantidade_caracteres": len(texto),
            "quantidade_palavras": len(texto.split()),
            "quantidade_fragmentos": len(itens),
            "confianca_media": round(float(np.mean(confs)), 4) if confs else None,
            "confianca_minima": round(float(np.min(confs)), 4) if confs else None,
            "necessita_revisao_humana": bool(revisao),
            "revisao_humana": revisao,
            "texto": texto,
            "linhas_ordenadas": [
                [{k: item[k] for k in ("indice_paddleocr", "texto", "confianca", "caixa", "coluna")} for item in linha]
                for linha in linhas_visuais
            ],
            "resultado_bruto_paddleocr": bruto,
        })
        (pasta_saida / f"{base}.txt").write_text(texto + "\n", encoding="utf-8")

    except Exception as erro:
        registro.update({
            "status": "erro",
            "erro": f"{type(erro).__name__}: {erro}",
            "detalhes_erro": traceback.format_exc(),
        })
        # Remove TXT antigo para não misturar resultado de execuções anteriores
        (pasta_saida / f"{base}.txt").unlink(missing_ok=True)

    with open(pasta_saida / f"{base}.json", "w", encoding="utf-8") as arq:
        json.dump(registro, arq, ensure_ascii=False, indent=2, default=_serializar)
    return registro


def _serializar(valor):
    """Converte tipos do NumPy para tipos nativos ao gravar JSON."""
    if isinstance(valor, np.ndarray):
        return valor.tolist()
    if isinstance(valor, np.generic):
        return valor.item()
    raise TypeError(f"Tipo não serializável: {type(valor)}")


def gravar_consolidado(registros: list[dict], pasta_saida: Path) -> Path:
    """
    Gera `documento_completo.txt` com o texto de todas as páginas, na ordem das páginas.
    Cada página é precedida por um separador identificando a origem; páginas com erro
    são indicadas explicitamente (nunca preenchidas com texto inventado).
    """
    partes = []
    for reg in sorted(registros, key=lambda r: r["pagina"]):
        cabecalho = f"===== Página {reg['pagina']} — {reg['imagem_origem']} ====="
        if reg.get("status") == "ok":
            partes.append(f"{cabecalho}\n{reg['texto']}")
        else:
            partes.append(f"{cabecalho}\n[PÁGINA NÃO PROCESSADA: {reg.get('erro', 'erro desconhecido')}]")
    destino = pasta_saida / "documento_completo.txt"
    destino.write_text("\n\n".join(partes) + "\n", encoding="utf-8")
    return destino


def pasta_saida_para(pasta_resultados_doc: Path, perfil: str) -> Path:
    """
    O perfil 'original' grava diretamente em resultados/<documento>/;
    os perfis com pré-processamento gravam em resultados/<documento>/preprocessado_<perfil>/.
    """
    return pasta_resultados_doc if perfil == "original" else pasta_resultados_doc / f"preprocessado_{perfil}"


def processar_documento(
    motor: MotorOCR,
    pasta_documento: Path,
    pasta_resultados: Path,
    perfil: str,
    limiar_confianca: float,
    detectar_colunas: bool = True,
    salvar_imagem_processada: bool = False,
) -> Iterator[dict]:
    """Processa todas as páginas de um documento com um perfil, gerando um registro por página."""
    documento = pasta_documento.name
    paginas = listar_paginas(pasta_documento)
    pasta_saida = pasta_saida_para(pasta_resultados / documento, perfil)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    # Remove páginas de execuções anteriores (evita misturar resultados antigos no relatório)
    for antigo in pasta_saida.glob("pagina_*"):
        if antigo.is_file():
            antigo.unlink()

    registros = []
    for pagina in paginas:
        reg = processar_pagina(
            motor, pagina, documento, perfil, pasta_saida, limiar_confianca,
            detectar_colunas, salvar_imagem_processada,
        )
        registros.append(reg)
        yield reg
    if registros:
        gravar_consolidado(registros, pasta_saida)
