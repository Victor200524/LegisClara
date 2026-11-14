"""
Benchmark de acurácia REAL do OCR em leis da Câmara Municipal de Londrina.

Por que é possível medir acurácia real aqui: os PDFs oficiais assinados são documentos
digitais com camada de texto. Esse texto é a referência exata de cada página — não é
preciso transcrever nada à mão.

Fluxo:
1. Para cada página dos PDFs em Leis_Londrina/documentos/*/*/lei.pdf:
   - referência = texto HORIZONTAL da camada de texto do PDF (ordem de leitura do PyMuPDF).
     O carimbo vertical da assinatura digital (margem direita) é excluído da referência,
     porque o pipeline não lê texto vertical (use_textline_orientation=False) — isso é
     registrado no relatório, não escondido;
   - imagem gerada em 3 condições:
       digital   : renderização limpa a 300 dpi (o que o main.py faz com PDFs);
       escaneado : 150 dpi, cinza, inclinação 1,2°, leve desfoque, ruído, JPEG q=70;
       foto      : ~110 dpi, inclinação 3°, perspectiva leve, iluminação irregular,
                   desfoque, ruído, JPEG q=55.
2. Cada imagem passa pelo OCR com vários perfis de pré-processamento
   (o mesmo ocr.processar_pagina do main.py / notebook / aplicação web).
3. Métricas por execução: CER, WER, acurácia, F1 de palavras (independe da ordem de
   leitura), preservação de elementos jurídicos, confiança média e tempo.

As imagens geradas ficam em imagens/03_leis_londrina_<condicao>/ e as referências em
referencias/03_leis_londrina/, para serem testadas também na aplicação web.

Uso:
    python -m scripts.benchmark_londrina                    # tudo (retomável)
    python -m scripts.benchmark_londrina --perfis original deskew --condicoes digital foto
    python -m scripts.benchmark_londrina --somente-relatorio
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts import avaliacao, ocr, preprocessamento as pre  # noqa: E402
from webapp.metricas import metricas_referencia  # noqa: E402

# leis de Londrina: dentro do repositório (Leis_Londrina/) ou ao lado do projeto
PASTA_LEIS = next((p for p in (RAIZ / "Leis_Londrina" / "documentos", RAIZ.parent / "Leis_Londrina" / "documentos") if p.exists()), RAIZ / "Leis_Londrina" / "documentos")
PASTA_REF = RAIZ / "referencias" / "03_leis_londrina"
PASTA_SAIDA = RAIZ / "resultados" / "benchmark_londrina"
CONDICOES = ["digital", "escaneado", "foto"]
PERFIS_PADRAO = ["original", "ampliado", "deskew", "completo"]
SEMENTE = 42


# ---------------------------------------------------------------------------
# Referência e imagens
# ---------------------------------------------------------------------------

def referencia_da_pagina(pagina) -> tuple[str, str]:
    """(texto horizontal, texto vertical excluído) da camada de texto do PDF."""
    horiz, vert = [], []
    for b in pagina.get_text("dict", sort=True)["blocks"]:
        if not b.get("lines"):
            continue
        for linha in b["lines"]:
            txt = "".join(s["text"] for s in linha["spans"]).strip()
            if not txt:
                continue
            (horiz if tuple(round(v) for v in linha["dir"]) == (1, 0) else vert).append(txt)
    return "\n".join(horiz), "\n".join(vert)


def renderizar(pagina, dpi: int) -> np.ndarray:
    import pymupdf

    pix = pagina.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return rgb[:, :, ::-1].copy()


def _girar(img: np.ndarray, graus: float) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), graus, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(255, 255, 255))


def _jpeg(img: np.ndarray, q: int) -> np.ndarray:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def degradar(pagina, condicao: str, rng: np.random.Generator) -> np.ndarray:
    if condicao == "digital":
        return renderizar(pagina, 300)
    if condicao == "escaneado":
        img = cv2.cvtColor(cv2.cvtColor(renderizar(pagina, 150), cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
        img = _girar(img, 1.2)
        img = cv2.GaussianBlur(img, (3, 3), 0.6)
        img = np.clip(img.astype(np.float32) + rng.normal(0, 8, img.shape), 0, 255).astype(np.uint8)
        return _jpeg(img, 70)
    if condicao == "foto":
        img = renderizar(pagina, 110)
        h, w = img.shape[:2]
        # perspectiva leve (celular não perfeitamente paralelo à folha)
        d = 0.025
        orig = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dest = np.float32([[w * d, h * d * 0.5], [w * (1 - d * 0.4), 0], [w, h], [0, h * (1 - d * 0.3)]])
        img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(orig, dest), (w, h),
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=(235, 235, 235))
        img = _girar(img, 3.0)
        # iluminação irregular: gradiente diagonal + sombra suave
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        luz = 0.72 + 0.28 * (xx / w * 0.6 + (1 - yy / h) * 0.4)
        img = np.clip(img.astype(np.float32) * luz[..., None] * np.array([0.97, 1.0, 1.03]), 0, 255)
        img = cv2.GaussianBlur(img, (0, 0), 0.9)
        img = np.clip(img + rng.normal(0, 6, img.shape), 0, 255).astype(np.uint8)
        return _jpeg(img, 55)
    raise ValueError(condicao)


def preparar(condicoes: list[str]) -> list[dict]:
    """Gera referências e imagens (idempotente). Devolve a lista de páginas."""
    import pymupdf

    PASTA_REF.mkdir(parents=True, exist_ok=True)
    paginas = []
    rng = np.random.default_rng(SEMENTE)
    for pdf in sorted(PASTA_LEIS.glob("*/*/lei.pdf")):
        lei = pdf.parent.name  # ex.: lei_14300
        with pymupdf.open(pdf) as doc:
            for i, pg in enumerate(doc, 1):
                nome = f"{lei}_p{i:02d}"
                ref, vert = referencia_da_pagina(pg)
                (PASTA_REF / f"{nome}.txt").write_text(ref + "\n", encoding="utf-8")
                for cond in condicoes:
                    destino = RAIZ / "imagens" / f"03_leis_londrina_{cond}" / ocr.SUBPASTA_IMAGENS / f"{nome}.{'png' if cond == 'digital' else 'jpg'}"
                    if not destino.exists():
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        pre.salvar_imagem(degradar(pg, cond, rng), destino)
                paginas.append({"lei": lei, "ano": pdf.parent.parent.name, "pagina": i, "nome": nome,
                                "referencia": ref, "vertical_excluido": vert})
    return paginas


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def f1_palavras(ref: str, hip: str) -> dict:
    """Precisão/revocação do multiconjunto de palavras: não penaliza ordem de leitura diferente."""
    r = Counter(avaliacao.normalizar_para_metrica(ref).split())
    h = Counter(avaliacao.normalizar_para_metrica(hip).split())
    comuns = sum((r & h).values())
    p = comuns / max(1, sum(h.values()))
    c = comuns / max(1, sum(r.values()))
    return {"precisao": round(p, 4), "revocacao": round(c, 4), "f1": round(2 * p * c / (p + c), 4) if p + c else 0.0}


def executar(paginas: list[dict], condicoes: list[str], perfis: list[str]) -> None:
    motor = ocr.MotorOCR()
    total = len(paginas) * len(condicoes) * len(perfis)
    feito = 0
    for cond in condicoes:
        for perfil in perfis:
            pasta = PASTA_SAIDA / cond / perfil
            pasta.mkdir(parents=True, exist_ok=True)
            for pg in paginas:
                feito += 1
                destino = pasta / f"{pg['nome']}.json"
                if destino.exists():
                    continue
                ext = "png" if cond == "digital" else "jpg"
                img_path = RAIZ / "imagens" / f"03_leis_londrina_{cond}" / ocr.SUBPASTA_IMAGENS / f"{pg['nome']}.{ext}"
                pagina = ocr.Pagina(numero=1, origem=img_path.name, carregar=lambda p=img_path: pre.carregar_imagem(p))
                t = time.perf_counter()
                # processar_pagina grava pagina_001.json/.txt; renomeamos para o nome da página
                reg = ocr.processar_pagina(motor, pagina, f"{pg['lei']}_{cond}", perfil, pasta, 0.80)
                (pasta / "pagina_001.json").replace(destino)
                if (pasta / "pagina_001.txt").exists():
                    (pasta / "pagina_001.txt").replace(pasta / f"{pg['nome']}.txt")
                print(f"[{feito:>3}/{total}] {cond:<9} {perfil:<9} {pg['nome']:<18} "
                      f"{reg.get('status')} {time.perf_counter() - t:5.1f}s", flush=True)


def relatorio(paginas: list[dict], condicoes: list[str], perfis: list[str]) -> dict:
    linhas = []
    for cond in condicoes:
        for perfil in perfis:
            for pg in paginas:
                arq = PASTA_SAIDA / cond / perfil / f"{pg['nome']}.json"
                if not arq.exists():
                    continue
                reg = json.loads(arq.read_text(encoding="utf-8"))
                base = {"condicao": cond, "perfil": perfil, "pagina": pg["nome"], "status": reg.get("status")}
                if reg.get("status") != "ok":
                    linhas.append({**base, "erro": reg.get("erro")})
                    continue
                m = metricas_referencia(pg["referencia"], reg["texto"])
                ej = m["elementos_juridicos"]
                linhas.append({
                    **base,
                    "caracteres_ref": m["caracteres"]["referencia"], "dist_car": m["caracteres"]["distancia"],
                    "palavras_ref": m["palavras"]["referencia"], "dist_pal": m["palavras"]["distancia"],
                    "cer": m["cer"], "wer": m["wer"], **{f"palavras_{k}": v for k, v in f1_palavras(pg["referencia"], reg["texto"]).items()},
                    "artigos": [ej["artigos"]["na_referencia"], ej["artigos"]["preservados_no_ocr"]],
                    "leis": [ej["leis"]["na_referencia"], ej["leis"]["preservados_no_ocr"]],
                    "datas": [ej["datas"]["na_referencia"], ej["datas"]["preservados_no_ocr"]],
                    "confianca_media": reg.get("confianca_media"), "tempo_ocr_s": reg.get("tempo_ocr_s"),
                    "trechos_revisao": len(reg.get("revisao_humana", [])),
                    "erros_exemplo": [d for d in m["diff"] if d["tipo"] != "igual"][:12],
                })

    def agregar(sel: list[dict]) -> dict:
        ok = [l for l in sel if l["status"] == "ok"]
        if not ok:
            return {}
        soma = lambda k: sum(l[k] for l in ok)
        el = lambda k: (sum(l[k][1] for l in ok), sum(l[k][0] for l in ok))
        cer = soma("dist_car") / soma("caracteres_ref")
        wer = soma("dist_pal") / soma("palavras_ref")
        a, la, d = el("artigos"), el("leis"), el("datas")
        return {
            "paginas": len(ok), "falhas": len(sel) - len(ok),
            "cer": round(cer, 4), "wer": round(wer, 4),
            "acuracia_caracteres": round(max(0, 1 - cer), 4), "acuracia_palavras": round(max(0, 1 - wer), 4),
            "f1_palavras": round(float(np.mean([l["palavras_f1"] for l in ok])), 4),
            "artigos_preservados": f"{a[0]}/{a[1]}", "leis_preservadas": f"{la[0]}/{la[1]}",
            "datas_preservadas": f"{d[0]}/{d[1]}",
            "confianca_media": round(float(np.mean([l["confianca_media"] for l in ok if l["confianca_media"] is not None])), 4),
            "tempo_medio_s": round(float(np.mean([l["tempo_ocr_s"] for l in ok])), 2),
        }

    resumo = {f"{c}/{p}": agregar([l for l in linhas if l["condicao"] == c and l["perfil"] == p])
              for c in condicoes for p in perfis}
    resumo = {k: v for k, v in resumo.items() if v}
    rel = {
        "descricao": "Acurácia real do PaddleOCR em leis de Londrina; referência = camada de texto do PDF oficial "
                     "(texto horizontal; carimbo vertical da assinatura excluído).",
        "paginas": [{k: p[k] for k in ("lei", "ano", "pagina", "nome")} | {"caracteres_referencia": len(p["referencia"]),
                     "vertical_excluido": p["vertical_excluido"]} for p in paginas],
        "resumo": resumo,
        "execucoes": linhas,
    }
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    (PASTA_SAIDA / "benchmark.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    (PASTA_SAIDA / "benchmark.md").write_text(_markdown(rel, condicoes, perfis), encoding="utf-8")
    return rel


def _markdown(rel: dict, condicoes: list[str], perfis: list[str]) -> str:
    pct = lambda v: f"{v * 100:.2f}%".replace(".", ",")
    s = ["# Benchmark de OCR — leis de Londrina (acurácia real)\n", rel["descricao"] + "\n",
         f"Páginas: {len(rel['paginas'])} (de {len({p['lei'] for p in rel['paginas']})} leis).\n",
         "| Condição | Perfil | Acurácia caracteres | Acurácia palavras | CER | WER | F1 palavras (sem ordem) | Art. | Leis | Datas | Confiança média | Tempo médio |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in condicoes:
        for p in perfis:
            r = rel["resumo"].get(f"{c}/{p}")
            if r:
                s.append(f"| {c} | {p} | {pct(r['acuracia_caracteres'])} | {pct(r['acuracia_palavras'])} | {r['cer']:.4f} | "
                         f"{r['wer']:.4f} | {pct(r['f1_palavras'])} | {r['artigos_preservados']} | {r['leis_preservadas']} | "
                         f"{r['datas_preservadas']} | {pct(r['confianca_media'])} | {r['tempo_medio_s']} s |")
    s.append("\nCER/WER agregados = soma das distâncias ÷ soma do tamanho das referências. "
             "Art./Leis/Datas = elementos idênticos no OCR ÷ elementos na referência (\"Art. 1°\" no lugar de \"Art. 1º\" conta como erro).\n")
    return "\n".join(s)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--condicoes", nargs="*", default=CONDICOES, choices=CONDICOES)
    ap.add_argument("--perfis", nargs="*", default=PERFIS_PADRAO, choices=list(pre.PERFIS))
    ap.add_argument("--somente-relatorio", action="store_true")
    a = ap.parse_args()
    paginas = preparar(a.condicoes)
    print(f"{len(paginas)} páginas; referências em {PASTA_REF}")
    if not a.somente_relatorio:
        executar(paginas, a.condicoes, a.perfis)
    rel = relatorio(paginas, a.condicoes, a.perfis)
    print((PASTA_SAIDA / "benchmark.md").read_text(encoding="utf-8"))
    print(f"Detalhes: {PASTA_SAIDA / 'benchmark.json'}  ({len(rel['execucoes'])} execuções)")


if __name__ == "__main__":
    main()
