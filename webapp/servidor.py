"""
Aplicação web do OCR de documentos jurídicos (PaddleOCR 3.x).

Executa exatamente o mesmo pipeline do notebook / main.py:
  pré-processamento (scripts/preprocessamento.py)
  -> OCR + ordem de leitura + sinalização de revisão (scripts/ocr.py)
  -> metadados jurídicos (scripts/metadados.py)
  -> métricas (webapp/metricas.py, com as definições de scripts/avaliacao.py)

Cada envio vira uma "execução" gravada em resultados_web/<id>/ com os mesmos arquivos do
main.py (pagina_NNN.json, pagina_NNN.txt, documento_completo.txt, metadados.json) mais a
imagem efetivamente entregue ao OCR (as coordenadas das caixas se referem a ela).

Rodar:  .venv/bin/python -m uvicorn webapp.servidor:app --port 8000
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts import ocr, metadados as meta, preprocessamento as pre  # noqa: E402
from webapp import metricas  # noqa: E402

PASTA_EXECUCOES = RAIZ / "resultados_web"
PASTA_ESTATICA = Path(__file__).parent / "static"
LIMITE_BYTES = 30 * 1024 * 1024
MAX_PAGINAS_PDF = 20
USAR_CONTEXTO = os.environ.get("LEGIS_CONTEXTO", "1") != "0"  # 0 = sem BERTimbau (economiza ~1 GB de RAM)

_motor: ocr.MotorOCR | None = None
_trava = threading.Lock()  # o PaddleOCR não é thread-safe: uma página por vez
_trava_corretor = threading.Lock()  # carregar/usar o corretor não pode bloquear o OCR


def motor() -> ocr.MotorOCR:
    global _motor
    if _motor is None:
        extras = {}
        # máquinas com pouca memória: OCR_MODELO_DETECCAO=PP-OCRv5_mobile_det
        if os.environ.get("OCR_MODELO_DETECCAO"):
            extras["text_detection_model_name"] = os.environ["OCR_MODELO_DETECCAO"]
        _motor = ocr.MotorOCR(**extras)
    return _motor


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    PASTA_EXECUCOES.mkdir(exist_ok=True)
    print("[webapp] carregando o PaddleOCR (alguns segundos)...", flush=True)
    t = time.perf_counter()
    motor()
    print(f"[webapp] modelo pronto em {time.perf_counter() - t:.1f}s", flush=True)

    def _carregar_corretor():
        from scripts import correcao
        with _trava_corretor:
            correcao.obter_corretor(usar_contexto=USAR_CONTEXTO)
        print("[webapp] corretor (dicionário + BERTimbau) pronto", flush=True)

    threading.Thread(target=_carregar_corretor, daemon=True).start()
    yield


app = FastAPI(title="OCR de Leis — PaddleOCR", lifespan=ciclo_de_vida)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _pasta_execucao(id_execucao: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{12}", id_execucao):
        raise HTTPException(404, "execução inexistente")
    pasta = PASTA_EXECUCOES / id_execucao
    if not pasta.is_dir():
        raise HTTPException(404, "execução inexistente")
    return pasta


def _registros(pasta: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(pasta.glob("pagina_[0-9][0-9][0-9].json"))]


def _resumo_pagina(reg: dict, id_execucao: str, referencia: str | None = None) -> dict:
    """Visão enxuta de uma página para a interface (o JSON completo fica disponível para download)."""
    base = ocr.nome_pagina(reg["pagina"])
    resumo = {k: reg.get(k) for k in (
        "pagina", "imagem_origem", "status", "erro", "perfil_preprocessamento", "etapas_preprocessamento",
        "dimensoes_imagem", "layout", "tempo_preprocessamento_s", "tempo_ocr_s", "quantidade_caracteres",
        "quantidade_palavras", "quantidade_fragmentos", "necessita_revisao_humana", "revisao_humana", "texto",
        "linhas_ordenadas")}
    resumo["imagem_url"] = f"/api/execucoes/{id_execucao}/arquivos/{base}_entrada.png"
    resumo["json_url"] = f"/api/execucoes/{id_execucao}/arquivos/{base}.json"
    resumo["txt_url"] = f"/api/execucoes/{id_execucao}/arquivos/{base}.txt"
    if reg.get("status") == "ok":
        resumo["metricas_confianca"] = metricas.metricas_confianca(reg)
        arq_cor = PASTA_EXECUCOES / id_execucao / f"{base}_correcao.json"
        if arq_cor.exists():
            resumo["correcao"] = json.loads(arq_cor.read_text(encoding="utf-8"))
        if referencia:
            resumo["metricas_referencia"] = metricas.metricas_referencia(referencia, reg["texto"])
            if resumo.get("correcao"):
                resumo["metricas_referencia_corrigido"] = metricas.metricas_referencia(
                    referencia, resumo["correcao"]["texto_corrigido"])
    return resumo


def _montar_resposta(pasta: Path) -> dict:
    from scripts import avaliacao

    info = json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))
    refs = info.get("referencias", {})
    paginas = []
    for reg in _registros(pasta):
        p = _resumo_pagina(reg, info["id"], refs.get(str(reg["pagina"])))
        if reg.get("status") == "ok":
            p["elementos_juridicos"] = avaliacao.extrair_elementos_juridicos(reg["texto"])
        paginas.append(p)

    ok = [p for p in paginas if p["status"] == "ok"]
    com_ref = [p for p in ok if p.get("metricas_referencia") and "cer" in p["metricas_referencia"]]
    conf_total = [i["confianca"] for p in ok for l in p["linhas_ordenadas"] for i in l if i["confianca"] is not None]
    documento = {
        "paginas": len(paginas),
        "paginas_com_erro": len(paginas) - len(ok),
        "caracteres": sum(p["quantidade_caracteres"] or 0 for p in ok),
        "palavras": sum(p["quantidade_palavras"] or 0 for p in ok),
        "fragmentos": len(conf_total),
        "confianca_media": round(sum(conf_total) / len(conf_total), 4) if conf_total else None,
        "trechos_para_revisao": sum(len(p["revisao_humana"] or []) for p in ok),
        "tempo_ocr_total_s": round(sum(p["tempo_ocr_s"] or 0 for p in ok), 3),
        "paginas_avaliadas_com_referencia": len(com_ref),
    }
    if com_ref:  # médias ponderadas pelo tamanho da referência (equivale ao CER do documento)
        car = sum(p["metricas_referencia"]["caracteres"]["referencia"] for p in com_ref)
        pal = sum(p["metricas_referencia"]["palavras"]["referencia"] for p in com_ref)
        documento["cer"] = round(sum(p["metricas_referencia"]["caracteres"]["distancia"] for p in com_ref) / car, 4)
        documento["wer"] = round(sum(p["metricas_referencia"]["palavras"]["distancia"] for p in com_ref) / pal, 4)
        documento["acuracia_caracteres"] = round(max(0, 1 - documento["cer"]), 4)
        documento["acuracia_palavras"] = round(max(0, 1 - documento["wer"]), 4)

    com_ref_c = [p for p in com_ref if p.get("metricas_referencia_corrigido")]
    if com_ref_c:
        car = sum(p["metricas_referencia_corrigido"]["caracteres"]["referencia"] for p in com_ref_c)
        pal = sum(p["metricas_referencia_corrigido"]["palavras"]["referencia"] for p in com_ref_c)
        documento["cer_corrigido"] = round(sum(p["metricas_referencia_corrigido"]["caracteres"]["distancia"] for p in com_ref_c) / car, 4)
        documento["wer_corrigido"] = round(sum(p["metricas_referencia_corrigido"]["palavras"]["distancia"] for p in com_ref_c) / pal, 4)
        documento["acuracia_caracteres_corrigido"] = round(max(0, 1 - documento["cer_corrigido"]), 4)
        documento["acuracia_palavras_corrigido"] = round(max(0, 1 - documento["wer_corrigido"]), 4)
    documento["correcoes_aplicadas"] = sum((p.get("correcao") or {}).get("estatisticas", {}).get("aplicadas", 0) for p in ok)
    documento["correcoes_sugeridas"] = sum((p.get("correcao") or {}).get("estatisticas", {}).get("sugestoes", 0) for p in ok)
    metadados = None
    if (pasta / "metadados.json").exists():
        metadados = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    return {
        **info,
        "documento": documento,
        "paginas": paginas,
        "metadados": metadados,
        "downloads": {
            "pacote_json": f"/api/execucoes/{info['id']}/json",
            "documento_txt": f"/api/execucoes/{info['id']}/arquivos/documento_completo.txt",
            "metadados_json": f"/api/execucoes/{info['id']}/arquivos/metadados.json",
        },
    }


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/api/info")
def info():
    m = motor()
    return {
        "perfis": pre.PERFIS,
        "limiar_padrao": 0.80,
        "parametros_paddleocr": m.parametros,
        "versoes": m.versoes(),
        "formatos": sorted(ocr.EXTENSOES_IMAGEM | ocr.EXTENSOES_PDF),
    }


@app.post("/api/ocr")
def executar_ocr(
    arquivo: UploadFile = File(...),
    perfil: str = Form("original"),
    limiar: float = Form(0.80),
    detectar_colunas: bool = Form(True),
    referencia: str = Form(""),
    corrigir: bool = Form(True),
):
    nome = Path(arquivo.filename or "imagem").name
    ext = Path(nome).suffix.lower()
    if ext not in ocr.EXTENSOES_IMAGEM | ocr.EXTENSOES_PDF:
        raise HTTPException(400, f"formato não suportado: {ext or '(sem extensão)'}")
    if perfil not in pre.PERFIS:
        raise HTTPException(400, f"perfil desconhecido: {perfil}")
    if not 0 <= limiar <= 1:
        raise HTTPException(400, "o limiar deve estar entre 0 e 1")
    dados = arquivo.file.read(LIMITE_BYTES + 1)
    if len(dados) > LIMITE_BYTES:
        raise HTTPException(413, "arquivo maior que 30 MB")

    id_execucao = uuid.uuid4().hex[:12]
    pasta = PASTA_EXECUCOES / id_execucao
    entrada = pasta / "entrada" / ocr.SUBPASTA_IMAGENS
    entrada.mkdir(parents=True)
    (entrada / nome).write_bytes(dados)

    try:
        paginas = ocr.listar_paginas(pasta / "entrada")
        if not paginas:
            raise HTTPException(400, "não foi possível ler o arquivo (imagem ou PDF inválido)")
        if len(paginas) > MAX_PAGINAS_PDF:
            raise HTTPException(400, f"o PDF tem {len(paginas)} páginas; o limite da aplicação web é {MAX_PAGINAS_PDF}")

        info_exec = {
            "id": id_execucao, "arquivo": nome, "criado_em": datetime.now().isoformat(timespec="seconds"),
            "perfil": perfil, "limiar": limiar, "detectar_colunas": detectar_colunas, "referencias": {},
        }
        if referencia.strip():  # referência enviada junto vale para a 1ª página
            info_exec["referencias"]["1"] = referencia
        elif len(paginas) == 1:
            # referência automática: referencias/**/<nome do arquivo>.txt (ex.: lei_14300_p01.txt)
            for ref in sorted((RAIZ / "referencias").glob(f"*/{Path(nome).stem}.txt")):
                texto_ref = ref.read_text(encoding="utf-8")
                if texto_ref.strip():
                    info_exec["referencias"]["1"] = texto_ref
                    info_exec["referencia_automatica"] = str(ref.relative_to(RAIZ))
                    break
        (pasta / "execucao.json").write_text(json.dumps(info_exec, ensure_ascii=False, indent=2), encoding="utf-8")

        registros = []
        with _trava:
            for pagina in paginas:
                # força salvar a imagem que entrou no OCR (inclusive no perfil "original"),
                # pois as caixas da interface são desenhadas sobre ela
                imagem = pre.aplicar_perfil(pagina.carregar(), perfil)
                pre.salvar_imagem(imagem, pasta / f"{ocr.nome_pagina(pagina.numero)}_entrada.png")
                reg = ocr.processar_pagina(
                    motor(), pagina, documento=Path(nome).stem, perfil=perfil, pasta_saida=pasta,
                    limiar_confianca=limiar, detectar_colunas=detectar_colunas, salvar_imagem_processada=False)
                registros.append(reg)
        ocr.gravar_consolidado(registros, pasta)
        if corrigir and any(r.get("status") == "ok" for r in registros):
            from scripts import correcao
            ok = [r for r in registros if r.get("status") == "ok"]
            with _trava_corretor:
                resultados = correcao.obter_corretor(usar_contexto=USAR_CONTEXTO).corrigir_documento(ok)
            for reg, cor in zip(ok, resultados):
                (pasta / f"{ocr.nome_pagina(reg['pagina'])}_correcao.json").write_text(
                    json.dumps(cor, ensure_ascii=False, indent=2), encoding="utf-8")
        if any(r.get("status") == "ok" for r in registros):
            try:
                meta.salvar_metadados(pasta)
            except Exception as e:  # metadados são complementares; o OCR continua válido
                (pasta / "metadados_erro.txt").write_text(f"{type(e).__name__}: {e}", encoding="utf-8")
    except HTTPException:
        shutil.rmtree(pasta, ignore_errors=True)
        raise
    return _montar_resposta(pasta)


class Referencia(BaseModel):
    pagina: int
    texto: str


@app.post("/api/execucoes/{id_execucao}/referencia")
def definir_referencia(id_execucao: str, ref: Referencia):
    """Grava (ou apaga, se vazio) a transcrição correta de uma página e recalcula as métricas."""
    pasta = _pasta_execucao(id_execucao)
    arq = pasta / "execucao.json"
    info_exec = json.loads(arq.read_text(encoding="utf-8"))
    if ref.texto.strip():
        info_exec["referencias"][str(ref.pagina)] = ref.texto
    else:
        info_exec["referencias"].pop(str(ref.pagina), None)
    arq.write_text(json.dumps(info_exec, ensure_ascii=False, indent=2), encoding="utf-8")
    return _montar_resposta(pasta)


@app.get("/api/execucoes")
def listar_execucoes():
    itens = []
    for p in sorted(PASTA_EXECUCOES.glob("*/execucao.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        i = json.loads(p.read_text(encoding="utf-8"))
        itens.append({k: i[k] for k in ("id", "arquivo", "criado_em", "perfil")})
    return itens


@app.get("/api/execucoes/{id_execucao}")
def obter_execucao(id_execucao: str):
    return _montar_resposta(_pasta_execucao(id_execucao))


@app.get("/api/execucoes/{id_execucao}/json")
def pacote_json(id_execucao: str):
    """JSON completo: as páginas exatamente como gravadas (com o resultado bruto do PaddleOCR) + metadados + métricas."""
    pasta = _pasta_execucao(id_execucao)
    resposta = _montar_resposta(pasta)
    corpo = {
        "execucao": {k: resposta[k] for k in ("id", "arquivo", "criado_em", "perfil", "limiar", "detectar_colunas")},
        "documento": resposta["documento"],
        "paginas": _registros(pasta),
        "correcoes": {p["pagina"]: p.get("correcao") for p in resposta["paginas"] if p.get("correcao")},
        "metricas_por_pagina": [{"pagina": p["pagina"], "confianca": p.get("metricas_confianca"),
                                 "referencia": {k: v for k, v in (p.get("metricas_referencia") or {}).items() if k != "diff"} or None}
                                for p in resposta["paginas"]],
        "metadados": resposta["metadados"],
    }
    return JSONResponse(corpo, headers={"Content-Disposition": f'attachment; filename="ocr_{id_execucao}.json"'})


@app.get("/api/execucoes/{id_execucao}/arquivos/{nome}")
def arquivo(id_execucao: str, nome: str):
    pasta = _pasta_execucao(id_execucao)
    if not re.fullmatch(r"(pagina_\d{3}(_entrada\.png|_correcao\.json|\.json|\.txt)|documento_completo\.txt|metadados\.json)", nome):
        raise HTTPException(404, "arquivo inexistente")
    caminho = pasta / nome
    if not caminho.is_file():
        raise HTTPException(404, "arquivo inexistente")
    return FileResponse(caminho)


@app.delete("/api/execucoes/{id_execucao}")
def apagar_execucao(id_execucao: str):
    shutil.rmtree(_pasta_execucao(id_execucao))
    return {"apagado": id_execucao}


app.mount("/", StaticFiles(directory=PASTA_ESTATICA, html=True), name="estatico")
