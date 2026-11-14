"""
Avaliação da qualidade do OCR: CER, WER e preservação de elementos jurídicos.

- CER (Character Error Rate) = distância de Levenshtein entre caracteres / nº de caracteres da referência.
- WER (Word Error Rate)      = distância de Levenshtein entre palavras    / nº de palavras da referência.

As métricas só são calculadas quando existe uma transcrição de referência
revisada por humanos em `referencias/<documento>/pagina_NNN.txt`.
Sem referência, CER e WER ficam como `null` no relatório (nunca são estimados).

Uso avulso (compara dois arquivos quaisquer):
    python -m scripts.avaliacao --referencia ref.txt --hipotese ocr.txt
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


# ---------------------------------------------------------------------------
# Normalização usada SOMENTE para o cálculo das métricas
# ---------------------------------------------------------------------------

def normalizar_para_metrica(texto: str) -> str:
    """
    Normalização mínima para comparar textos de forma justa:
    - Unicode NFC (o mesmo "á" pode ser 1 ou 2 códigos; isso não é erro de OCR);
    - espaços e quebras de linha consecutivos viram um único espaço
      (a quebra de linha depende do layout, não do reconhecimento).
    Acentos, maiúsculas/minúsculas, pontuação, º/°, § etc. são PRESERVADOS:
    trocá-los é erro de OCR relevante em textos jurídicos.
    Esta normalização nunca é aplicada aos arquivos de saída do OCR.
    """
    texto = unicodedata.normalize("NFC", texto)
    return re.sub(r"\s+", " ", texto).strip()


# ---------------------------------------------------------------------------
# Distância de edição
# ---------------------------------------------------------------------------

def distancia_levenshtein(a: list | str, b: list | str) -> int:
    """Número mínimo de inserções, remoções e substituições para transformar `a` em `b`."""
    if len(a) < len(b):
        a, b = b, a
    anterior = list(range(len(b) + 1))
    for i, elem_a in enumerate(a, start=1):
        atual = [i]
        for j, elem_b in enumerate(b, start=1):
            atual.append(min(
                anterior[j] + 1,                       # remoção
                atual[j - 1] + 1,                      # inserção
                anterior[j - 1] + (elem_a != elem_b),  # substituição
            ))
        anterior = atual
    return anterior[-1]


def calcular_cer(referencia: str, hipotese: str) -> float | None:
    ref, hip = normalizar_para_metrica(referencia), normalizar_para_metrica(hipotese)
    if not ref:
        return None
    return distancia_levenshtein(ref, hip) / len(ref)


def calcular_wer(referencia: str, hipotese: str) -> float | None:
    ref = normalizar_para_metrica(referencia).split()
    hip = normalizar_para_metrica(hipotese).split()
    if not ref:
        return None
    return distancia_levenshtein(ref, hip) / len(ref)


# ---------------------------------------------------------------------------
# Elementos jurídicos
# ---------------------------------------------------------------------------

PADROES_JURIDICOS = {
    "artigos": re.compile(r"\bArt\.\s*\d+(?:\.\d+)*\s*[ºo°]?(?:-[A-Z])?", re.IGNORECASE),
    "paragrafos": re.compile(r"§\s*\d+\s*[ºo°]?|\bpar[áa]grafo\s+[úu]nico", re.IGNORECASE),
    "incisos": re.compile(r"^\s*[IVXLC]+\s*[-–—]", re.MULTILINE),
    "alineas": re.compile(r"^\s*[a-z]\)", re.MULTILINE),
    "leis": re.compile(r"\bLei(?:\s+Complementar)?\s+n\.?\s*[ºo°]?\s*[\d.]+", re.IGNORECASE),
    "datas": re.compile(
        r"\b\d{1,2}\s*[ºo°]?\s+de\s+[a-zç]+\s+de\s+\d{4}\b|\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b",
        re.IGNORECASE,
    ),
}


def extrair_elementos_juridicos(texto: str) -> dict[str, list[str]]:
    """Lista as marcações jurídicas encontradas (exatamente como escritas)."""
    texto = unicodedata.normalize("NFC", texto)
    return {nome: [re.sub(r"\s+", " ", m.strip()) for m in padrao.findall(texto)]
            for nome, padrao in PADROES_JURIDICOS.items()}


def comparar_elementos_juridicos(referencia: str, hipotese: str) -> dict:
    """
    Para cada categoria, verifica quantas marcações da referência aparecem
    idênticas no OCR (ex.: 'Art. 4º' reconhecido como 'Art. 4°' conta como perdido).
    """
    ref = extrair_elementos_juridicos(referencia)
    hip = extrair_elementos_juridicos(hipotese)
    resultado = {}
    for categoria, itens_ref in ref.items():
        disponiveis = list(hip[categoria])
        encontrados, ausentes = 0, []
        for item in itens_ref:
            if item in disponiveis:
                disponiveis.remove(item)
                encontrados += 1
            else:
                ausentes.append(item)
        resultado[categoria] = {
            "na_referencia": len(itens_ref),
            "preservados_no_ocr": encontrados,
            "taxa_preservacao": round(encontrados / len(itens_ref), 4) if itens_ref else None,
            "ausentes_ou_divergentes": ausentes,
        }
    return resultado


# ---------------------------------------------------------------------------
# Relatório por pasta de resultados
# ---------------------------------------------------------------------------

def avaliar_texto(referencia: str, hipotese: str) -> dict:
    cer, wer = calcular_cer(referencia, hipotese), calcular_wer(referencia, hipotese)
    return {
        "cer": round(cer, 4) if cer is not None else None,
        "wer": round(wer, 4) if wer is not None else None,
        "elementos_juridicos": comparar_elementos_juridicos(referencia, hipotese),
    }


def gerar_relatorio(pasta_resultado: Path, pasta_referencia: Path) -> dict:
    """
    Lê os `pagina_NNN.json` de uma pasta de resultados, compara com as referências
    disponíveis e grava `relatorio.json` e `relatorio.md` na mesma pasta.
    """
    linhas = []
    for arq_json in sorted(pasta_resultado.glob("pagina_[0-9][0-9][0-9].json")):
        reg = json.loads(arq_json.read_text(encoding="utf-8"))
        nome = arq_json.stem
        linha = {
            "documento": reg.get("documento"),
            "pagina": reg.get("pagina"),
            "imagem": reg.get("imagem_origem"),
            "perfil": reg.get("perfil_preprocessamento"),
            "status": reg.get("status"),
            "quantidade_caracteres": reg.get("quantidade_caracteres"),
            "quantidade_palavras": reg.get("quantidade_palavras"),
            "tempo_ocr_s": reg.get("tempo_ocr_s"),
            "tempo_preprocessamento_s": reg.get("tempo_preprocessamento_s"),
            "confianca_media": reg.get("confianca_media"),
            "trechos_para_revisao": len(reg.get("revisao_humana", [])),
            "cer": None,
            "wer": None,
            "referencia": None,
        }
        if reg.get("status") != "ok":
            linha["erro"] = reg.get("erro")
        else:
            arq_ref = pasta_referencia / f"{nome}.txt"
            if arq_ref.is_file() and arq_ref.read_text(encoding="utf-8").strip():
                avaliacao = avaliar_texto(arq_ref.read_text(encoding="utf-8"), reg.get("texto", ""))
                linha.update(avaliacao)
                linha["referencia"] = str(arq_ref.as_posix())
            else:
                linha["observacao"] = "sem transcrição de referência: CER/WER não calculados"
        linhas.append(linha)

    avaliadas = [l for l in linhas if l["cer"] is not None]
    resumo = {
        "paginas": len(linhas),
        "paginas_com_erro": sum(1 for l in linhas if l["status"] != "ok"),
        "paginas_avaliadas": len(avaliadas),
        "cer_medio": round(sum(l["cer"] for l in avaliadas) / len(avaliadas), 4) if avaliadas else None,
        "wer_medio": round(sum(l["wer"] for l in avaliadas) / len(avaliadas), 4) if avaliadas else None,
        "tempo_ocr_total_s": round(sum(l["tempo_ocr_s"] or 0 for l in linhas), 3),
    }
    relatorio = {"resumo": resumo, "paginas": linhas}
    (pasta_resultado / "relatorio.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta_resultado / "relatorio.md").write_text(tabela_markdown(linhas, resumo), encoding="utf-8")
    return relatorio


def _fmt(valor, casas: int = 4) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, float):
        return f"{valor:.{casas}f}"
    return str(valor)


def tabela_markdown(linhas: list[dict], resumo: dict) -> str:
    """Tabela legível do relatório (também usada na saída do terminal)."""
    cab = "| Documento | Imagem | Perfil | Caracteres | Palavras | Tempo OCR (s) | CER | WER | Revisão |\n"
    cab += "|---|---|---|---:|---:|---:|---:|---:|---:|\n"
    corpo = ""
    for l in linhas:
        if l["status"] != "ok":
            corpo += f"| {l['documento']} | {l['imagem']} | {l['perfil']} | ERRO: {l.get('erro')} | | | | | |\n"
            continue
        corpo += (f"| {l['documento']} | {l['imagem']} | {l['perfil']} | {l['quantidade_caracteres']} | "
                  f"{l['quantidade_palavras']} | {_fmt(l['tempo_ocr_s'], 2)} | {_fmt(l['cer'])} | "
                  f"{_fmt(l['wer'])} | {l['trechos_para_revisao']} |\n")
    rodape = (f"\nPáginas: {resumo['paginas']} · com erro: {resumo['paginas_com_erro']} · "
              f"avaliadas (com referência): {resumo['paginas_avaliadas']} · "
              f"CER médio: {_fmt(resumo['cer_medio'])} · WER médio: {_fmt(resumo['wer_medio'])}\n")
    if resumo["paginas_avaliadas"] == 0:
        rodape += "\nCER/WER = — : nenhuma transcrição de referência disponível; métricas não calculadas.\n"
    return cab + corpo + rodape


def _main() -> None:
    parser = argparse.ArgumentParser(description="Compara uma transcrição de referência com a saída do OCR.")
    parser.add_argument("--referencia", required=True, type=Path, help="TXT revisado por humanos")
    parser.add_argument("--hipotese", required=True, type=Path, help="TXT gerado pelo OCR")
    args = parser.parse_args()
    resultado = avaliar_texto(args.referencia.read_text(encoding="utf-8"),
                              args.hipotese.read_text(encoding="utf-8"))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
