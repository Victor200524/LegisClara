"""
Extração de metadados jurídicos a partir dos resultados do OCR.

Lê os `pagina_NNN.json` de uma pasta de resultados e monta um JSON estruturado com:
- identificação da norma (tipo, número, data, apelido, ementa);
- estrutura (títulos, capítulos, seções) e dispositivos (artigos, parágrafos,
  incisos, alíneas) com o texto de cada um;
- leis e datas citadas, notas de rodapé e número de página impresso;
- rastreabilidade (imagem de origem, página, linha, confiança, perfil, versões).

Princípios (os mesmos do OCR):
- Todo texto é o BRUTO reconhecido pelo modelo (campos `*_bruto`/`texto`).
- Campos `*_normalizado` só são preenchidos quando o texto bruto é inequívoco
  (ex.: "OUTUBRO" é um mês; "0UTUBRO" não é). Caso contrário ficam `null` e o
  motivo vai para `pendencias`. Nada é adivinhado ou corrigido.
- Dispositivos que contêm trechos marcados para revisão humana carregam esses trechos.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
_ROMANO_VALIDO = re.compile(r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")

# --- Padrões de linha (aplicados ao início de cada linha do TXT) -------------
RE_NORMA = re.compile(
    r"^(?P<tipo>LEI COMPLEMENTAR|LEI|DECRETO-LEI|DECRETO|MEDIDA PROVIS[ÓO]RIA|EMENDA CONSTITUCIONAL|RESOLU[ÇC][ÃA]O|PORTARIA)"
    r"\s+N\S{0,2}\s*(?P<numero>\d[\d.\s]*\d|\d)\s*,?\s*DE\s+(?P<data>.+?\d{4})",
    re.IGNORECASE,
)
RE_EMENTA = re.compile(r"^(Disp[õo]e|Institui|Altera|Estabelece|Regulamenta|Cria|Revoga|Acrescenta|Aprova)\b")
RE_DIVISAO = re.compile(r"^(?P<tipo>T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O|LIVRO|PARTE)\s+(?P<rotulo>\S+)\s*[-–—]?\s*(?P<nome>.*)$")
RE_ARTIGO = re.compile(r"^Art\.?\s*(?P<rotulo>\d+(?:\.\d+)*\s*[º°ºo]?(?:-[A-Z])?)\.?\s*(?P<texto>.*)$")
RE_PARAGRAFO = re.compile(r"^(?:§\s*(?P<rotulo>\d+\s*[º°o]?)|(?P<unico>Par[áa]grafo\s*[úu]nico))\.?\s*(?P<texto>.*)$", re.IGNORECASE)
RE_INCISO = re.compile(r"^(?P<rotulo>[IVXLCl1-9]*[IVXLC][IVXLCl]*)\s*[-–—]\s*(?P<texto>.*)$")
RE_ALINEA = re.compile(r"^(?P<rotulo>[a-z])\)\s*(?P<texto>.*)$")
RE_NOTA = re.compile(r"^(?P<rotulo>\d{1,2})\.\s+(?P<texto>[A-ZÁÉÍÓÚÂÊÔÃÕÇ].*)$")
RE_NUM_PAGINA = re.compile(r"^\d{1,4}$")

# --- Padrões de citação (aplicados ao texto todo) ----------------------------
RE_LEI_CITADA = re.compile(
    r"\bLei\s*(?:Complementar\s*)?n\S{0,2}\s*\d[\d.\s]*\d(?:\s*,?\s*de\s+[^,;]+?\d{4})?", re.IGNORECASE)
RE_DATA = re.compile(r"\b\d{1,2}\s*[º°]?\s+de\s+\S+\s+de\s+\d{4}\b|\b\d{1,2}-\d{1,2}-\d{4}\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Normalizações conservadoras (só quando o bruto é inequívoco)
# ---------------------------------------------------------------------------

def normalizar_numero(bruto: str) -> tuple[str | None, str | None]:
    """'10.741' -> '10741'. Retorna (valor, pendência)."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})*|\d+", bruto.strip()):
        return bruto.replace(".", "").strip(), None
    return None, f"número '{bruto}' contém caracteres inesperados (ex.: espaço no lugar do ponto)"


def normalizar_data_extenso(bruto: str) -> tuple[str | None, str | None]:
    """'1º DE OUTUBRO DE 2003' -> '2003-10-01'. Exige mês escrito exatamente como um mês."""
    m = re.fullmatch(r"(\d{1,2})\s*[º°o]?\s+de\s+(\S+)\s+de\s+(\d{4})", bruto.strip(), re.IGNORECASE)
    if not m:
        return None, f"data '{bruto}' fora do padrão 'D de MÊS de AAAA'"
    dia, mes_txt, ano = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    if mes_txt not in MESES:
        return None, f"mês '{m.group(2)}' não é um nome de mês válido (possível erro de OCR)"
    try:
        return date(ano, MESES[mes_txt], dia).isoformat(), None
    except ValueError:
        return None, f"data '{bruto}' inexistente no calendário"


def normalizar_ordinal(rotulo: str) -> tuple[int | None, str | None]:
    """'1°' / '10' -> 1 / 10 (o símbolo usado fica registrado no rótulo bruto)."""
    m = re.fullmatch(r"(\d+)\s*[º°o]?", rotulo.strip())
    if not m:
        return None, f"rótulo '{rotulo}' não numérico"
    return int(m.group(1)), None


def verificar_ordinal(rotulo: str, numero: int | None, tipo: str) -> str | None:
    """
    Técnica legislativa (LC 95/1998, art. 10): artigos e parágrafos de 1 a 9 usam ordinal
    (Art. 1º, § 2º); a partir de 10, cardinal (Art. 10). Apenas sinaliza a divergência.
    """
    if numero is None or numero > 9 or "º" in rotulo:
        return None
    if "°" in rotulo:
        return f"{tipo} '{rotulo}' usa o símbolo de grau '°' em vez do ordinal 'º'"
    return f"{tipo} '{rotulo}' sem indicador ordinal 'º' (esperado para 1 a 9; possível perda no OCR)"


def validar_romano(rotulo: str) -> str | None:
    if _ROMANO_VALIDO.fullmatch(rotulo) and rotulo:
        return None
    return f"rótulo de inciso '{rotulo}' não é algarismo romano válido (ex.: l/I, 1/I, marca de nota de rodapé)"


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------

def _carregar_paginas(pasta_resultado: Path) -> list[dict]:
    paginas = []
    for arq in sorted(pasta_resultado.glob("pagina_[0-9][0-9][0-9].json")):
        reg = json.loads(arq.read_text(encoding="utf-8"))
        paginas.append(reg)
    return sorted(paginas, key=lambda r: r["pagina"])


def _novo_dispositivo(tipo, rotulo, texto, pagina, linha):
    return {"tipo": tipo, "rotulo_bruto": rotulo, "pagina": pagina, "linha_inicio": linha,
            "linhas": [texto] if texto else [], "pendencias": [], "revisao_humana": []}


def extrair_metadados(pasta_resultado: Path) -> dict:
    """Monta o dicionário de metadados de um documento a partir de uma pasta de resultados."""
    paginas = _carregar_paginas(pasta_resultado)
    if not paginas:
        raise FileNotFoundError(f"Nenhum pagina_NNN.json em {pasta_resultado}")

    identificacoes, ementas, apelidos = [], [], []
    divisoes, artigos, notas, outros, numeros_pagina = [], [], [], [], []
    leis_citadas, datas_citadas = [], []
    contexto = {}            # título/capítulo/seção vigentes
    artigo = None            # artigo corrente
    atual = None             # dispositivo corrente (recebe as linhas de continuação)
    pai_alinea = None        # inciso/parágrafo que recebe alíneas
    ementa_aberta = None

    for reg in paginas:
        if reg.get("status") != "ok":
            continue
        n_pag = reg["pagina"]
        revisoes = {}
        for r in reg.get("revisao_humana", []):
            revisoes.setdefault(r["linha_txt"], []).append(
                {"texto_bruto": r["texto_bruto"], "confianca": r["confianca"], "motivos": r["motivos"]})
        linhas = reg.get("texto", "").split("\n")

        for n_lin, linha in enumerate(linhas, start=1):
            texto = linha.strip()
            if not texto:
                continue
            # A linha de identificação da própria norma não é uma citação
            for lei in ([] if RE_NORMA.match(texto) else RE_LEI_CITADA.findall(texto)):
                leis_citadas.append({"texto_bruto": lei.strip(), "pagina": n_pag, "linha": n_lin})
            for dt in RE_DATA.findall(texto):
                datas_citadas.append({"texto_bruto": dt, "pagina": n_pag, "linha": n_lin})

            destino = None  # objeto que recebe as marcações de revisão desta linha

            if (m := RE_NORMA.match(texto)):
                numero, p1 = normalizar_numero(m["numero"])
                data_iso, p2 = normalizar_data_extenso(m["data"])
                ident = {"tipo_bruto": m["tipo"], "numero_bruto": m["numero"], "data_bruta": m["data"],
                         "numero_normalizado": numero, "data_normalizada": data_iso,
                         "pagina": n_pag, "linha": n_lin, "texto_bruto": texto,
                         "pendencias": [p for p in (p1, p2) if p], "revisao_humana": []}
                identificacoes.append(ident)
                # Nova ocorrência do cabeçalho da norma (ex.: outra edição): reinicia o contexto
                destino, atual, ementa_aberta = ident, None, None
                artigo, pai_alinea, contexto = None, None, {}
            elif artigo is None and re.fullmatch(r"\(.+\)", texto) and identificacoes:
                apelidos.append({"texto_bruto": texto.strip("()"), "pagina": n_pag, "linha": n_lin})
            elif artigo is None and (RE_EMENTA.match(texto) or ementa_aberta is not None):
                if ementa_aberta is None:
                    ementa_aberta = {"texto_bruto": texto, "pagina": n_pag, "linha": n_lin, "revisao_humana": []}
                    ementas.append(ementa_aberta)
                else:
                    ementa_aberta["texto_bruto"] += "\n" + texto
                destino = ementa_aberta
                if texto.endswith("."):
                    ementa_aberta = None
            elif (m := RE_DIVISAO.match(texto)):
                div = {"tipo": m["tipo"].upper(), "rotulo_bruto": m["rotulo"], "nome_bruto": m["nome"],
                       "pagina": n_pag, "linha": n_lin, "revisao_humana": []}
                divisoes.append(div)
                chave = div["tipo"].replace("Í", "I").replace("Ç", "C").replace("Ã", "A")
                niveis = ["LIVRO", "PARTE", "TITULO", "CAPITULO", "SECAO", "SUBSECAO"]
                if chave in niveis:  # ao abrir um nível, fecha os inferiores
                    for inferior in niveis[niveis.index(chave):]:
                        contexto.pop(inferior, None)
                    contexto[chave] = div
                destino, atual = div, div
            elif (m := RE_ARTIGO.match(texto)):
                artigo = _novo_dispositivo("artigo", m["rotulo"].strip(), m["texto"], n_pag, n_lin)
                artigo["numero"], p = normalizar_ordinal(re.sub(r"[.\-A-Z]", "", m["rotulo"]))
                p = p or verificar_ordinal(artigo["rotulo_bruto"], artigo["numero"], "artigo")
                if p:
                    artigo["pendencias"].append(p)
                artigo["localizacao"] = {k: f"{d['tipo']} {d['rotulo_bruto']} - {d['nome_bruto']}".strip(" -")
                                         for k, d in contexto.items()}
                artigo["paragrafos"], artigo["incisos"] = [], []
                artigos.append(artigo)
                destino = atual = artigo
                pai_alinea = None
            elif artigo is not None and (m := RE_PARAGRAFO.match(texto)):
                par = _novo_dispositivo("paragrafo", m["rotulo"] or m["unico"], m["texto"], n_pag, n_lin)
                par["unico"] = bool(m["unico"])
                par["numero"] = None if m["unico"] else normalizar_ordinal(m["rotulo"])[0]
                par["incisos"] = []
                if not m["unico"] and (p := verificar_ordinal(m["rotulo"], par["numero"], "parágrafo")):
                    par["pendencias"].append(p)
                artigo["paragrafos"].append(par)
                destino = atual = pai_alinea = par
            elif artigo is not None and (m := RE_INCISO.match(texto)):
                inc = _novo_dispositivo("inciso", m["rotulo"], m["texto"], n_pag, n_lin)
                if (p := validar_romano(m["rotulo"])):
                    inc["pendencias"].append(p)
                inc["alineas"] = []
                # Inciso pertence ao último parágrafo aberto do artigo, se houver; senão ao caput
                (artigo["paragrafos"][-1]["incisos"] if artigo["paragrafos"] else artigo["incisos"]).append(inc)
                destino = atual = pai_alinea = inc
            elif artigo is not None and pai_alinea is not None and (m := RE_ALINEA.match(texto)):
                ali = _novo_dispositivo("alinea", m["rotulo"], m["texto"], n_pag, n_lin)
                pai_alinea.setdefault("alineas", []).append(ali)
                destino = atual = ali
            elif (m := RE_NOTA.match(texto)):
                notas.append({"rotulo": m["rotulo"], "texto_bruto": m["texto"], "pagina": n_pag, "linha": n_lin})
            elif RE_NUM_PAGINA.match(texto) and n_lin == len(linhas):
                numeros_pagina.append({"pagina": n_pag, "numero_impresso_bruto": texto})
            elif atual is not None and atual.get("tipo") in ("artigo", "paragrafo", "inciso", "alinea"):
                atual["linhas"].append(texto)       # continuação do dispositivo
                destino = atual
            elif atual is not None and "nome_bruto" in atual and texto.isupper():
                atual["nome_bruto"] += " " + texto  # título/capítulo quebrado em duas linhas
                destino = atual
            else:
                outros.append({"texto_bruto": texto, "pagina": n_pag, "linha": n_lin})

            if destino is not None and n_lin in revisoes:
                destino["revisao_humana"].extend(revisoes[n_lin])

    # Texto de cada dispositivo: linhas brutas unidas por "\n" (hifenização preservada)
    def finalizar(d):
        if "linhas" in d:
            d["texto_bruto"] = "\n".join(d.pop("linhas"))
        for chave in ("paragrafos", "incisos", "alineas"):
            for filho in d.get(chave, []):
                finalizar(filho)
    for a in artigos:
        finalizar(a)

    pendencias = [
        {"onde": f"{i['tipo_bruto']} (pág. {i['pagina']}, linha {i['linha']})", "motivo": p}
        for i in identificacoes for p in i["pendencias"]
    ]
    def coletar(d, caminho):
        for p in d.get("pendencias", []):
            pendencias.append({"onde": f"{caminho} (pág. {d['pagina']}, linha {d['linha_inicio']})", "motivo": p})
        for chave in ("paragrafos", "incisos", "alineas"):
            for filho in d.get(chave, []):
                coletar(filho, f"{caminho} > {filho['tipo']} {filho['rotulo_bruto']}")
    for a in artigos:
        coletar(a, f"Art. {a['rotulo_bruto']}")

    # Divergências entre ocorrências da identificação da norma (ex.: duas edições)
    divergencias = {}
    for campo in ("numero_bruto", "data_bruta"):
        valores = sorted({i[campo] for i in identificacoes})
        if len(valores) > 1:
            divergencias[campo] = valores

    primeira = paginas[0]
    return {
        "documento": primeira.get("documento"),
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "aviso": ("Textos são a saída bruta do OCR. Campos *_normalizado só são preenchidos quando o bruto é "
                  "inequívoco; caso contrário ficam null e o motivo aparece em 'pendencias'."),
        "processamento": {
            "perfil_preprocessamento": primeira.get("perfil_preprocessamento"),
            "versoes": primeira.get("versoes"),
            "parametros_paddleocr": primeira.get("parametros_paddleocr"),
            "paginas": [{
                "pagina": r["pagina"], "imagem_origem": r.get("imagem_origem"), "status": r.get("status"),
                "colunas": (r.get("layout") or {}).get("colunas"), "confianca_media": r.get("confianca_media"),
                "trechos_para_revisao": len(r.get("revisao_humana", [])), "tempo_ocr_s": r.get("tempo_ocr_s"),
            } for r in paginas],
        },
        "norma": {
            "identificacoes": identificacoes,
            "divergencias_entre_ocorrencias": divergencias,
            "apelidos": apelidos,
            "ementas": ementas,
        },
        "estrutura": divisoes,
        "artigos": artigos,
        "leis_citadas": leis_citadas,
        "datas_citadas": datas_citadas,
        "notas_rodape": notas,
        "numeros_pagina_impressos": numeros_pagina,
        "textos_nao_classificados": outros,
        "pendencias": pendencias,
        "estatisticas": {
            "artigos": len(artigos),
            "paragrafos": sum(len(a["paragrafos"]) for a in artigos),
            "incisos": sum(len(a["incisos"]) + sum(len(p["incisos"]) for p in a["paragrafos"]) for a in artigos),
            "divisoes": len(divisoes),
            "artigos_com_revisao_humana": sum(1 for a in artigos if _tem_revisao(a)),
            "pendencias": len(pendencias),
        },
    }


def _tem_revisao(d: dict) -> bool:
    """Verdadeiro se o dispositivo ou algum subordinado tem trecho marcado para revisão."""
    return bool(d.get("revisao_humana")) or any(
        _tem_revisao(f) for chave in ("paragrafos", "incisos", "alineas") for f in d.get(chave, []))


def salvar_metadados(pasta_resultado: Path) -> tuple[dict, Path]:
    """Extrai e grava `metadados.json` na própria pasta de resultados."""
    metadados = extrair_metadados(pasta_resultado)
    destino = pasta_resultado / "metadados.json"
    destino.write_text(json.dumps(metadados, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadados, destino
