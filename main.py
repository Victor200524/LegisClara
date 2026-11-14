"""
Ponto de entrada do experimento de OCR com PaddleOCR em documentos jurídicos.

Exemplos:
    python main.py                                   # OCR na imagem original, todos os documentos
    python main.py --perfis original binarizado      # compara original x binarizado
    python main.py --comparar                        # executa todos os perfis de pré-processamento
    python main.py --documento 02_estatuto_idoso     # apenas um documento
    python main.py --somente-avaliacao               # recalcula relatórios (ex.: após adicionar referências)
    python main.py --listar-perfis
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Todos os caminhos são relativos à pasta do projeto, independentemente de onde o comando é executado.
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from scripts import avaliacao  # noqa: E402
from scripts.preprocessamento import PERFIS  # noqa: E402

PASTA_IMAGENS = RAIZ / "imagens"
PASTA_RESULTADOS = RAIZ / "resultados"
PASTA_REFERENCIAS = RAIZ / "referencias"


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Testes de OCR (PaddleOCR 3.x) em documentos jurídicos brasileiros.")
    p.add_argument("--documento", nargs="*", help="Nome(s) da(s) pasta(s) em imagens/ (padrão: todas)")
    p.add_argument("--perfis", nargs="*", default=["original"], choices=list(PERFIS),
                   help="Perfis de pré-processamento a executar (padrão: original)")
    p.add_argument("--comparar", action="store_true", help="Executa todos os perfis de pré-processamento")
    p.add_argument("--limiar-confianca", type=float, default=0.80,
                   help="Fragmentos com confiança abaixo deste valor são marcados para revisão humana (padrão: 0.80)")
    p.add_argument("--uma-coluna", action="store_true",
                   help="Desativa a detecção de duas colunas na ordem de leitura")
    p.add_argument("--salvar-imagens-processadas", action="store_true",
                   help="Grava a imagem pré-processada entregue ao OCR (pagina_NNN_entrada.png)")
    p.add_argument("--somente-avaliacao", action="store_true",
                   help="Não executa o OCR; apenas regenera relatórios a partir dos resultados existentes")
    p.add_argument("--listar-perfis", action="store_true", help="Mostra os perfis de pré-processamento e sai")
    return p.parse_args()


def _pastas_de_resultado(pasta_doc: Path) -> list[tuple[str, Path]]:
    """Encontra as pastas de resultado já existentes de um documento (uma por perfil)."""
    pastas = []
    if any(pasta_doc.glob("pagina_*.json")):
        pastas.append(("original", pasta_doc))
    for sub in sorted(pasta_doc.glob("preprocessado_*")):
        if sub.is_dir() and any(sub.glob("pagina_*.json")):
            pastas.append((sub.name.removeprefix("preprocessado_"), sub))
    return pastas


def gerar_comparativo(documento: str) -> None:
    """Gera relatórios de cada perfil e um comparativo entre perfis do mesmo documento."""
    pasta_doc = PASTA_RESULTADOS / documento
    pasta_ref = PASTA_REFERENCIAS / documento
    linhas = []
    for perfil, pasta in _pastas_de_resultado(pasta_doc):
        rel = avaliacao.gerar_relatorio(pasta, pasta_ref)
        print(f"\n### {documento} — perfil: {perfil}  ({pasta.relative_to(RAIZ).as_posix()})")
        print(avaliacao.tabela_markdown(rel["paginas"], rel["resumo"]))
        paginas_ok = [p for p in rel["paginas"] if p["status"] == "ok"]
        confs = [p["confianca_media"] for p in paginas_ok if p["confianca_media"] is not None]
        linhas.append({
            "perfil": perfil,
            "etapas": PERFIS.get(perfil),
            **rel["resumo"],
            "confianca_media": round(sum(confs) / len(confs), 4) if confs else None,
            "trechos_para_revisao": sum(p["trechos_para_revisao"] for p in paginas_ok),
            "caracteres_total": sum(p["quantidade_caracteres"] or 0 for p in paginas_ok),
        })

    if len(linhas) > 1:
        (pasta_doc / "comparativo_perfis.json").write_text(
            json.dumps(linhas, ensure_ascii=False, indent=2), encoding="utf-8")
        md = ("| Perfil | Etapas | Páginas avaliadas | CER médio | WER médio | Confiança média | "
              "Trechos p/ revisão | Caracteres | Tempo OCR (s) |\n|---|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for l in linhas:
            md += (f"| {l['perfil']} | {', '.join(l['etapas'] or []) or '—'} | {l['paginas_avaliadas']} | "
                   f"{avaliacao._fmt(l['cer_medio'])} | {avaliacao._fmt(l['wer_medio'])} | "
                   f"{avaliacao._fmt(l['confianca_media'])} | {l['trechos_para_revisao']} | "
                   f"{l['caracteres_total']} | {l['tempo_ocr_total_s']} |\n")
        (pasta_doc / "comparativo_perfis.md").write_text(md, encoding="utf-8")
        print(f"\n### Comparativo de perfis — {documento}\n{md}")


def main() -> int:
    args = _argumentos()

    if args.listar_perfis:
        for nome, etapas in PERFIS.items():
            print(f"{nome:16s} {' -> '.join(etapas) or '(imagem sem alteração)'}")
        return 0

    documentos = ocr_listar_documentos()
    if args.documento:
        desconhecidos = set(args.documento) - {d.name for d in documentos}
        if desconhecidos:
            print(f"Documento(s) não encontrado(s) em imagens/: {', '.join(sorted(desconhecidos))}")
            return 1
        documentos = [d for d in documentos if d.name in args.documento]

    if not args.somente_avaliacao:
        perfis = list(PERFIS) if args.comparar else args.perfis
        from scripts import ocr  # importa o PaddleOCR somente quando o OCR será executado

        motor = None
        for pasta_doc in documentos:
            paginas = ocr.listar_paginas(pasta_doc)
            if not paginas:
                print(f"\n[{pasta_doc.name}] Nenhuma imagem encontrada em "
                      f"{(pasta_doc / ocr.SUBPASTA_IMAGENS).relative_to(RAIZ).as_posix()} — documento ignorado.")
                continue
            if motor is None:
                print("Carregando modelos do PaddleOCR (lang=pt, CPU)...")
                motor = ocr.MotorOCR(idioma="pt", dispositivo="cpu")
            for perfil in perfis:
                print(f"\n[{pasta_doc.name}] perfil '{perfil}': {len(paginas)} página(s)")
                for reg in ocr.processar_documento(
                    motor, pasta_doc, PASTA_RESULTADOS, perfil, args.limiar_confianca,
                    detectar_colunas=not args.uma_coluna,
                    salvar_imagem_processada=args.salvar_imagens_processadas,
                ):
                    if reg["status"] == "ok":
                        print(f"  página {reg['pagina']:>3} ({reg['imagem_origem']}): "
                              f"{reg['quantidade_palavras']} palavras, {reg['tempo_ocr_s']:.2f}s, "
                              f"{reg['layout']['colunas']} coluna(s), "
                              f"{len(reg['revisao_humana'])} trecho(s) p/ revisão")
                    else:
                        print(f"  página {reg['pagina']:>3} ({reg['imagem_origem']}): ERRO — {reg['erro']}")

    for pasta_doc in documentos:
        gerar_comparativo(pasta_doc.name)
    return 0


def ocr_listar_documentos() -> list[Path]:
    """Lista documentos sem importar o PaddleOCR (útil para --somente-avaliacao)."""
    if not PASTA_IMAGENS.is_dir():
        return []
    return sorted(p for p in PASTA_IMAGENS.iterdir() if p.is_dir() and not p.name.startswith("."))


if __name__ == "__main__":
    sys.exit(main())
