"""
Métricas exibidas na aplicação web.

Dois grupos, que NÃO devem ser confundidos:

1. Estimativas do próprio modelo (sem referência)
   Baseadas na confiança (`rec_scores`) que o PaddleOCR atribui a cada trecho. Indicam
   onde o modelo "tem dúvida", mas não medem acerto: um trecho pode ter confiança 0,99
   e estar errado.

2. Acurácia real (com referência)
   Comparação com uma transcrição correta fornecida pelo usuário, usando as MESMAS
   definições de `scripts/avaliacao.py` (CER, WER, elementos jurídicos). A distância de
   Levenshtein aqui é vetorizada com NumPy (mesmo resultado, muito mais rápida), e também
   devolve quantas substituições, inserções e remoções ocorreram.
"""

from __future__ import annotations

import difflib

import numpy as np

from scripts import avaliacao


# ---------------------------------------------------------------------------
# 1. Estimativas pela confiança do modelo
# ---------------------------------------------------------------------------

def metricas_confianca(registro: dict) -> dict:
    itens = [i for linha in registro.get("linhas_ordenadas", []) for i in linha]
    confs = np.array([i["confianca"] for i in itens if i.get("confianca") is not None], dtype=float)
    limiar = registro.get("limiar_confianca_revisao", 0.8)
    if confs.size == 0:
        return {"fragmentos": 0}

    # confiança ponderada pelo nº de caracteres: trechos longos pesam mais
    pesos = np.array([max(len(i["texto"]), 1) for i in itens if i.get("confianca") is not None], dtype=float)
    faixas = np.linspace(0, 1, 11)
    hist, _ = np.histogram(confs, bins=faixas)
    return {
        "fragmentos": int(confs.size),
        "confianca_media": round(float(confs.mean()), 4),
        "confianca_mediana": round(float(np.median(confs)), 4),
        "confianca_minima": round(float(confs.min()), 4),
        "confianca_maxima": round(float(confs.max()), 4),
        "confianca_ponderada_por_caracteres": round(float((confs * pesos).sum() / pesos.sum()), 4),
        "limiar": limiar,
        "fragmentos_acima_do_limiar": int((confs >= limiar).sum()),
        "percentual_fragmentos_acima_do_limiar": round(float((confs >= limiar).mean()), 4),
        "percentual_caracteres_acima_do_limiar": round(float(pesos[confs >= limiar].sum() / pesos.sum()), 4),
        "histograma": [{"de": round(float(faixas[k]), 1), "ate": round(float(faixas[k + 1]), 1), "quantidade": int(hist[k])}
                       for k in range(10)],
        "trechos_para_revisao": len(registro.get("revisao_humana", [])),
    }


# ---------------------------------------------------------------------------
# 2. Acurácia contra referência
# ---------------------------------------------------------------------------

def _levenshtein_ops(a: list, b: list) -> dict:
    """
    Distância de edição com contagem de operações (S, I, R) por programação dinâmica.
    Guarda a matriz para o caminho de volta; usa NumPy por linha.
    a = referência, b = hipótese (OCR).
    """
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return {"distancia": max(n, m), "substituicoes": 0, "insercoes": m, "remocoes": n}
    # mapeia símbolos para inteiros para comparar vetorialmente
    vocab: dict = {}
    va = np.array([vocab.setdefault(x, len(vocab)) for x in a], dtype=np.int64)
    vb = np.array([vocab.setdefault(x, len(vocab)) for x in b], dtype=np.int64)
    D = np.empty((n + 1, m + 1), dtype=np.int32)
    D[0] = np.arange(m + 1)
    idx = np.arange(m + 1, dtype=np.int32)
    for i in range(1, n + 1):
        custo = (vb != va[i - 1]).astype(np.int32)
        tmp = np.empty(m + 1, dtype=np.int32)
        tmp[0] = i
        tmp[1:] = np.minimum(D[i - 1, 1:] + 1, D[i - 1, :-1] + custo)  # remoção / substituição
        # inserções: D[i, j] = min_k (tmp[k] + (j - k))  ->  cummin(tmp - j) + j
        D[i] = np.minimum.accumulate(tmp - idx) + idx
    # caminho de volta
    i, j, s, ins, rem = n, m, 0, 0, 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and D[i, j] == D[i - 1, j - 1] + (va[i - 1] != vb[j - 1]):
            s += int(va[i - 1] != vb[j - 1]); i -= 1; j -= 1
        elif i > 0 and D[i, j] == D[i - 1, j] + 1:
            rem += 1; i -= 1
        else:
            ins += 1; j -= 1
    return {"distancia": int(D[n, m]), "substituicoes": s, "insercoes": ins, "remocoes": rem}


def _diff_palavras(ref: list[str], hip: list[str]) -> list[dict]:
    """Trechos para a visualização lado a lado: igual / trocado / faltou / sobrou."""
    trechos = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref, hip, autojunk=False).get_opcodes():
        tipo = {"equal": "igual", "replace": "trocado", "delete": "faltou", "insert": "sobrou"}[op]
        trechos.append({"tipo": tipo, "referencia": " ".join(ref[i1:i2]), "ocr": " ".join(hip[j1:j2])})
    return trechos


def metricas_referencia(referencia: str, hipotese: str) -> dict:
    ref_n = avaliacao.normalizar_para_metrica(referencia)
    hip_n = avaliacao.normalizar_para_metrica(hipotese)
    if not ref_n:
        return {"erro": "texto de referência vazio"}
    car = _levenshtein_ops(list(ref_n), list(hip_n))
    pal_ref, pal_hip = ref_n.split(), hip_n.split()
    pal = _levenshtein_ops(pal_ref, pal_hip)
    cer = car["distancia"] / len(ref_n)
    wer = pal["distancia"] / len(pal_ref)
    return {
        "cer": round(cer, 4),
        "wer": round(wer, 4),
        "acuracia_caracteres": round(max(0.0, 1 - cer), 4),
        "acuracia_palavras": round(max(0.0, 1 - wer), 4),
        "caracteres": {"referencia": len(ref_n), "ocr": len(hip_n), **car},
        "palavras": {"referencia": len(pal_ref), "ocr": len(pal_hip), **pal},
        "elementos_juridicos": avaliacao.comparar_elementos_juridicos(referencia, hipotese),
        "diff": _diff_palavras(pal_ref, pal_hip),
        "normalizacao": "Unicode NFC e espaços/quebras de linha colapsados; acentos, maiúsculas, "
                        "pontuação, º/° e § são preservados (igual a scripts/avaliacao.py)",
    }
