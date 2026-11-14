"""
Base de leis pesquisável: análise de contexto, palavras-chave e busca semântica.

Para cada lei (do portal da Câmara de Londrina ou vinda do OCR):
- tipo do ato (o que a lei FAZ) por regras sobre a súmula, com explicação em linguagem simples;
- temas (saúde, educação, trânsito…) por regras de vocabulário + similaridade semântica;
- palavras-chave: candidatos por TF-IDF no acervo (o que distingue a lei das demais),
  escolhidos por similaridade semântica com a lei + MMR (diversidade);
- embeddings da lei e de cada artigo (multilingual-e5-small).

Banco: SQLite (dados/leis.db) com FTS5 (busca textual sem acentos) e vetores em BLOB.
Busca híbrida: semântica (lei e artigo) + textual + palavras-chave, fundidas por RRF.

Uso:
    python -m scripts.busca_leis --indexar            # (re)constrói a base com Leis_Londrina/
    python -m scripts.busca_leis "cachorro de rua"    # busca pelo terminal
Variável LEGIS_BUSCA_SEMANTICA=0 desliga o modelo (só busca textual; para máquinas com pouca RAM).
"""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import sqlite3
import sys
import threading
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "dados" / "leis.db"
PASTA_LEIS = next((p for p in (RAIZ / "Leis_Londrina" / "documentos", RAIZ.parent / "Leis_Londrina" / "documentos")
                   if p.exists()), RAIZ / "Leis_Londrina" / "documentos")
MODELO = "intfloat/multilingual-e5-small"
USAR_SEMANTICA = os.environ.get("LEGIS_BUSCA_SEMANTICA", "1") != "0"

# ---------------------------------------------------------------------------
# Vocabulário
# ---------------------------------------------------------------------------
STOP = set("""a à às ao aos as até com como da das de dela dele do dos e é em entre era essa esse esta este
foi há isso já lhe mais mas me mesmo na não nas nem no nos o os ou para pela pelas pelo pelos por qual
quando que quem se sem ser seu seus sua suas só também um uma umas uns será serão sendo seja sejam
está estão onde cada outro outra outros outras qualquer todo toda todos todas sobre sob após contra desde
deste desta neste nesta desse dessa nesse nessa tal tais ii iii iv vi vii viii ix""".split())
STOP_JUR = set("""lei leis art arts artigo artigos parágrafo paragrafo único unico inciso incisos alínea caput
fica ficam vigor vigência publicação disposições contrário revogadas revogam município municipio municipal
municipais londrina câmara camara prefeito prefeita estado paraná parana seguinte sanciono aprovou decretou
promulgo dispõe providências presente poder executivo legislativo nº ref autoria projeto substitutivo emenda
data referida referido conforme termos forma passa passam vigorar acrescido acrescida redação dada dá nova
novo seguintes ano anos dia dias janeiro fevereiro março abril maio junho julho agosto setembro outubro
novembro dezembro institui cria altera acrescenta inclui denomina declara confere concede autoriza revoga
estabelece regulamenta deverá deverão poderá poderão sede foro demais âmbito finalidade objetivo
outras dá vereador vereadora presidente secretário secretária cr cz ncr""".split())

TIPOS = [  # (rótulo, explicação para o cidadão, padrão sobre a súmula sem acento)
    ("homenagem", "Homenageia uma pessoa ou empresa (título, medalha ou honraria)",
     r"\b(confere|concede|outorga)\b.*\b(titulo|medalha|comenda|diploma|honra|cidada)|\bcidada[o]? honorari|\bmedalha\b"),
    ("utilidade_publica", "Reconhece uma entidade como de utilidade pública", r"utilidade publica"),
    ("denominacao", "Dá nome a uma rua, praça, escola ou outro espaço público",
     r"\b(denomina|da denominacao|denominacao|da o nome|da nome)\b"),
    ("calendario", "Cria uma data comemorativa no calendário oficial",
     r"\bcalendario\b|\b(dia|semana|mes) (municipal|do|da|de)\b"),
    ("orcamento", "Trata de dinheiro público: orçamento ou crédito extra para gastos",
     r"credito (adicional|especial|suplementar)|\borcament|\borca a receita|diretrizes orcamentarias|plano plurianual|\babre\b.*credito"),
    ("imovel", "Trata de terreno ou imóvel público (doação, permuta, desafetação, venda)",
     r"\bdesafeta|\bdoacao\b|\bdoa\b|\bpermuta|concessao de (direito real de )?uso|\balienacao|\bimove(l|is)\b|\bterreno|\barea de terra"),
    ("revogacao", "Cancela (revoga) uma lei anterior", r"^revoga\b"),
    ("alteracao", "Muda uma lei que já existia",
     r"^(altera|acresce|acrescenta|modifica|introduz|da nova redacao|suprime)\b|\baltera (a|o|os|as|dispositivos)\b"),
    ("autorizacao", "Autoriza a prefeitura a fazer algo (convênio, contrato, empréstimo…)", r"^autoriza\b"),
    ("pessoal", "Trata de servidores públicos, cargos ou salários",
     r"\bcargo|\bservidor|\bvencimento|\bsubsidio|\bquadro de pessoal|\bremunera"),
    ("zoneamento", "Trata de uso do solo, zoneamento ou loteamento",
     r"zoneamento|uso e ocupacao|\bzona\b|loteamento|perimetro urbano|parcelamento do solo"),
    ("criacao", "Cria um programa, órgão, conselho ou política pública", r"^(institui|cria)\b"),
    ("regulamentacao", "Estabelece regras sobre um assunto", r"^(dispoe|regulamenta|estabelece|define|disciplina|proibe|obriga)\b"),
]

TEMAS = {  # rótulo: (descrição para o modelo, padrão de vocabulário sem acento)
    "saúde": ("saúde pública, hospitais, unidades de saúde, doenças, vacinação, medicamentos",
              r"\bsaude\b|hospita|\bsus\b|doenc|vacin|medicament|enferm|\bmedic[oa]s?\b|\bubs\b|sanitari"),
    "educação": ("educação, escolas, ensino, alunos, professores, creches", r"\beduca|escola|\bensino|alun|professor|creche|\bcmei\b"),
    "meio ambiente": ("meio ambiente, árvores, resíduos, reciclagem, poluição, fundos de vale",
                      r"ambient|arvore|arboriza|residu|recicl|poluic|fundo de vale|nascente|florest"),
    "animais": ("proteção animal, cães, gatos, maus-tratos, castração", r"\banima(l|is)\b|\bcaes\b|\bgatos?\b|maus.tratos|castrac|zoonos"),
    "trânsito e transporte": ("trânsito, ônibus, transporte coletivo, estacionamento, ciclovias",
                              r"\btransito\b|transporte|onibus|estacionament|mobilidade|ciclovi|veicul|\btaxi"),
    "urbanismo e obras": ("zoneamento, loteamentos, obras, edificações, ruas e calçadas",
                          r"zoneament|uso e ocupacao|loteament|edifica|\bobras?\b|plano diretor|calcad|pavimenta"),
    "tributos e finanças": ("impostos, IPTU, ISS, taxas, isenções, orçamento, créditos",
                            r"tribut|impost|\biptu\b|\biss\b|\btaxas?\b|isenc|orcament|credito|fiscal|receita|despesa"),
    "servidores e administração": ("servidores públicos, cargos, salários, secretarias, estrutura da prefeitura",
                                   r"servidor|\bcargos?\b|carreira|vencimento|remunera|secretaria|previdenc|concurso|subsidio"),
    "assistência social": ("assistência social, pessoas em vulnerabilidade, população de rua, fome",
                           r"assistencia social|vulnerab|situacao de rua|\bfome\b|cesta basica"),
    "cultura e esporte": ("cultura, arte, música, teatro, esporte, lazer, eventos", r"\bcultur|\bartes?\b|music|teatr|festival|museu|esport|lazer|atleta"),
    "segurança": ("segurança pública, guarda municipal, violência, defesa civil", r"seguranca publica|guarda municipal|violenc|defesa civil"),
    "pessoas com deficiência": ("pessoas com deficiência, acessibilidade, autismo, inclusão", r"deficien|acessibil|autis|\btea\b|inclusao|libras|atipic"),
    "crianças e jovens": ("crianças, adolescentes, juventude, conselho tutelar", r"crianc|adolescen|infan|juventude|jovens|tutelar"),
    "idosos": ("pessoas idosas, terceira idade", r"\bidos[oa]s?\b|terceira idade"),
    "mulheres": ("direitos das mulheres, violência contra a mulher, mães", r"mulher|feminin|gestante|matern|\bmaes\b"),
    "comércio e economia": ("comércio, empresas, feiras, ambulantes, emprego, desenvolvimento econômico",
                            r"comerci|empresa|feira|ambulant|alvara|emprego|economic|industri|incentiv"),
    "habitação": ("moradia, habitação popular, regularização fundiária, COHAB", r"habitac|moradia|regularizacao fundiaria|cohab"),
    "saneamento e serviços": ("água, esgoto, coleta de lixo, iluminação pública", r"saneament|\bagua\b|esgot|coleta de lixo|iluminacao publica|drenagem"),
    "zona rural": ("zona rural, agricultura, produtores rurais, distritos", r"\brura(l|is)\b|agricul|agropecu|\bdistrito"),
    "homenagens": ("homenagens, títulos de cidadão honorário, medalhas, nomes de ruas em honra de pessoas",
                   r"cidada[o]? honorari|medalha|homenag|comenda|denomina"),
    "entidades e associações": ("associações, entidades sem fins lucrativos, utilidade pública",
                                r"utilidade publica|associac|instituto|fundacao|entidade"),
}


def sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.combining(c))


def norm(t: str) -> str:
    return sem_acento(t.lower())


# ---------------------------------------------------------------------------
# Extração do texto das leis do portal
# ---------------------------------------------------------------------------

def texto_do_html(bruto: str) -> str:
    bruto = re.sub(r"<!--.*?-->|<style.*?</style>|<script.*?</script>|<title>.*?</title>", " ", bruto, flags=re.S | re.I)
    bruto = re.sub(r"<(s|strike|del)\b.*?</\1>", " ", bruto, flags=re.S | re.I)  # redação revogada (riscada)
    bruto = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", bruto, flags=re.I)
    t = html_lib.unescape(re.sub(r"<[^>]+>", " ", bruto)).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def dividir_artigos(texto: str) -> list[tuple[str, str]]:
    marcas = list(re.finditer(r"(?m)^\s*(Art\.?\s*\d+[\wºo°\-]*)\.?", texto))
    arts = []
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        corpo = re.split(r"\n\s*Londrina,\s*\d", texto[m.end():fim])[0]
        arts.append((re.sub(r"\s+", " ", m.group(1)).replace("°", "º"), re.sub(r"\s+", " ", corpo).strip()[:4000]))
    return arts


def leis_do_portal(pasta: Path = PASTA_LEIS) -> list[dict]:
    leis = []
    for arq in sorted(pasta.glob("*/*/coleta.json")):
        meta = json.loads(arq.read_text(encoding="utf-8"))
        h = arq.parent / "lei.html"
        if not h.exists():
            continue
        texto = texto_do_html(h.read_text(encoding="utf-8", errors="replace"))
        sumula = (meta.get("sumula") or "").strip()
        sumula = re.sub(r"\s*\(?\s*REVOGAD[AO].*$", "", sumula, flags=re.I | re.S).strip() or sumula
        if len(texto) < 40 and not sumula:
            continue  # leis vazias no portal
        leis.append({"id_portal": meta["id_portal"], "ano": int(meta["ano"]), "numero": meta["numero"],
                     "titulo": meta["titulo"], "data": (meta.get("data_portal") or "")[:10], "sumula": sumula,
                     "autoria": meta.get("autoria_portal") or "", "url": meta["url"], "texto": texto,
                     "origem": "portal"})
    return leis


# ---------------------------------------------------------------------------
# Análise
# ---------------------------------------------------------------------------

def classificar_tipo(sumula: str) -> tuple[str, str]:
    s = norm(sumula).strip()
    for rot, explic, pad in TIPOS:
        if re.search(pad, s):
            return rot, explic
    return "outros", "Outros assuntos"


def _candidatos(texto: str) -> list[str]:
    toks = re.findall(r"[a-zà-ÿ][a-zà-ÿ\-]+", texto.lower())
    proib = STOP | STOP_JUR
    out = []
    for n in (1, 2, 3):
        for i in range(len(toks) - n + 1):
            g = toks[i:i + n]
            if g[0] in proib or g[-1] in proib or len(g[0]) < 3 or len(g[-1]) < 3:
                continue
            if n == 1 and len(g[0]) < 5:
                continue
            if sum(t in proib for t in g) > 1:
                continue
            out.append(" ".join(g))
    return out


class Modelo:
    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self.m = SentenceTransformer(MODELO, device="cpu")
        self.m.max_seq_length = 512
        self.cache: dict[str, np.ndarray] = {}

    def passagens(self, textos: list[str]) -> np.ndarray:
        return self.m.encode([f"passage: {t}" for t in textos], batch_size=32, normalize_embeddings=True,
                             convert_to_numpy=True).astype(np.float32)

    def consultas(self, textos: list[str]) -> np.ndarray:
        novos = [t for t in dict.fromkeys(textos) if t not in self.cache]
        if novos:
            v = self.m.encode([f"query: {t}" for t in novos], batch_size=64, normalize_embeddings=True,
                              convert_to_numpy=True).astype(np.float32)
            self.cache.update(zip(novos, v))
        return np.stack([self.cache[t] for t in textos])


class Analisador:
    def __init__(self, modelo: Modelo | None, corpus: list[str]):
        self.modelo = modelo
        df = Counter()
        for t in corpus:
            df.update(set(_candidatos(t)))
        n = max(1, len(corpus))
        self.idf = {c: float(np.log((1 + n) / (1 + f)) + 1) for c, f in df.items()}
        self.idf_max = float(np.log(1 + n) + 1)
        if modelo:
            self.temas_rot = list(TEMAS)
            self.temas_vet = modelo.consultas([TEMAS[t][0] for t in self.temas_rot])

    def texto_base(self, lei: dict) -> str:
        return (lei["sumula"] + "\n" + lei["texto"])[:20000]

    def analisar(self, lei: dict, vetor: np.ndarray | None) -> dict:
        tipo, explic = classificar_tipo(lei["sumula"] or lei["texto"][:300])
        base = norm(lei["sumula"] + " " + lei["texto"][:6000])
        regra = {t: len(re.findall(pad, base)) for t, (_, pad) in TEMAS.items()}
        pont = {t: (1.0 + 0.2 * min(n, 5)) if n else 0.0 for t, n in regra.items()}
        if vetor is not None and self.modelo:
            sims = self.temas_vet @ vetor
            z = (sims - sims.mean()) / (sims.std() + 1e-9)
            for i, t in enumerate(self.temas_rot):
                pont[t] += float(z[i])
        temas = [t for t, p in sorted(pont.items(), key=lambda kv: -kv[1]) if (regra[t] and p >= 1.4) or p >= 2.6][:3]

        # palavras-chave: súmula pesa 3x; TF-IDF escolhe candidatos; semântica + MMR escolhe os finais
        tf = Counter(_candidatos("\n".join([lei["sumula"]] * 3 + [lei["texto"][:15000]])))
        palavras = []
        if tf:
            tfidf = {c: (1 + np.log(f)) * self.idf.get(c, self.idf_max) for c, f in tf.items()}
            cands = sorted(tfidf, key=lambda c: tfidf[c] * (1 + 0.15 * c.count(" ")), reverse=True)[:30]
            tn = np.array([tfidf[c] for c in cands]); tn = tn / tn.max()
            if vetor is not None and self.modelo:
                vc = self.modelo.consultas(cands)
                relev = 0.7 * (vc @ vetor) + 0.3 * tn
                esc = [int(np.argmax(relev))]
                rest = [i for i in range(len(cands)) if i != esc[0]]
                while len(esc) < 8 and rest:
                    ult = set(cands[esc[-1]].split())
                    rest = [i for i in rest if not (set(cands[i].split()) & ult)]
                    if not rest:
                        break
                    red = (vc[rest] @ vc[esc].T).max(axis=1)
                    k = rest[int(np.argmax(0.5 * relev[rest] - 0.5 * red))]
                    esc.append(k); rest.remove(k)
                palavras = [cands[i] for i in esc]
            else:
                vistos = set()
                for c in cands:
                    if not (set(c.split()) & vistos):
                        palavras.append(c); vistos |= set(c.split())
                    if len(palavras) == 8:
                        break
        return {"tipo": tipo, "tipo_explicacao": explic, "temas": temas, "palavras_chave": palavras}


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS leis (
  id INTEGER PRIMARY KEY, id_portal INTEGER UNIQUE, ano INTEGER, numero TEXT, titulo TEXT, data TEXT,
  sumula TEXT, autoria TEXT, url TEXT, texto TEXT, origem TEXT, tipo TEXT, tipo_explicacao TEXT,
  temas TEXT, palavras_chave TEXT, emb BLOB
);
CREATE TABLE IF NOT EXISTS artigos (id INTEGER PRIMARY KEY, lei_id INTEGER, rotulo TEXT, texto TEXT, emb BLOB);
CREATE INDEX IF NOT EXISTS artigos_lei ON artigos(lei_id);
CREATE VIRTUAL TABLE IF NOT EXISTS leis_fts USING fts5(
  titulo, sumula, palavras, texto, tokenize = 'unicode61 remove_diacritics 2'
);
"""


def conectar() -> sqlite3.Connection:
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(BANCO, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _inserir(con, lei: dict, an: dict, vetor, arts: list[tuple[str, str]], vet_arts) -> int:
    cur = con.execute(
        "INSERT INTO leis (id_portal, ano, numero, titulo, data, sumula, autoria, url, texto, origem, tipo, "
        "tipo_explicacao, temas, palavras_chave, emb) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (lei.get("id_portal"), lei.get("ano"), lei.get("numero"), lei["titulo"], lei.get("data"), lei["sumula"],
         lei.get("autoria"), lei.get("url"), lei["texto"], lei.get("origem", "portal"), an["tipo"], an["tipo_explicacao"],
         json.dumps(an["temas"], ensure_ascii=False), json.dumps(an["palavras_chave"], ensure_ascii=False),
         vetor.tobytes() if vetor is not None else None))
    lid = cur.lastrowid
    for k, (rot, txt) in enumerate(arts):
        con.execute("INSERT INTO artigos (lei_id, rotulo, texto, emb) VALUES (?,?,?,?)",
                    (lid, rot, txt, vet_arts[k].tobytes() if vet_arts is not None else None))
    con.execute("INSERT INTO leis_fts (rowid, titulo, sumula, palavras, texto) VALUES (?,?,?,?,?)",
                (lid, lei["titulo"], lei["sumula"], " ".join(an["palavras_chave"] + an["temas"] + [an["tipo_explicacao"]]),
                 lei["texto"][:200000]))
    return lid


def indexar_portal() -> dict:
    leis = leis_do_portal()
    if BANCO.exists():
        BANCO.unlink()
    con = conectar()
    modelo = Modelo()
    an = Analisador(modelo, [l["sumula"] + "\n" + l["texto"][:15000] for l in leis])
    vets = modelo.passagens([f"{l['titulo']}. {l['sumula']}\n{l['texto'][:1500]}" for l in leis])
    total_arts = 0
    for i, (lei, v) in enumerate(zip(leis, vets), 1):
        arts = dividir_artigos(lei["texto"])
        va = modelo.passagens([f"{lei['sumula']} | {r} {t}"[:1200] for r, t in arts]) if arts else None
        _inserir(con, lei, an.analisar(lei, v), v, arts, va)
        total_arts += len(arts)
        if i % 20 == 0:
            print(f"[indexar] {i}/{len(leis)}", flush=True)
    con.commit()
    return {"leis": len(leis), "artigos": total_arts, "banco": str(BANCO)}


# ---------------------------------------------------------------------------
# Serviço de busca (usado pela aplicação web)
# ---------------------------------------------------------------------------

class BaseDeLeis:
    def __init__(self, semantica: bool = USAR_SEMANTICA):
        self.con = conectar()
        self.trava = threading.Lock()
        self.modelo = Modelo() if semantica else None
        self._carregar()

    def _carregar(self):
        linhas = self.con.execute("SELECT id, emb FROM leis").fetchall()
        self.ids = [r["id"] for r in linhas]
        self.vets = (np.stack([np.frombuffer(r["emb"], dtype=np.float32) for r in linhas])
                     if linhas and all(r["emb"] for r in linhas) else None)
        arts = self.con.execute("SELECT id, lei_id, emb FROM artigos WHERE emb IS NOT NULL").fetchall()
        self.art_lei = np.array([r["lei_id"] for r in arts]) if arts else np.array([])
        self.art_ids = [r["id"] for r in arts]
        self.art_vets = np.stack([np.frombuffer(r["emb"], dtype=np.float32) for r in arts]) if arts else None
        corpus = [r[0] + "\n" + r[1][:15000] for r in self.con.execute("SELECT sumula, texto FROM leis")]
        self.analisador = Analisador(self.modelo, corpus)

    def info(self) -> dict:
        tot = self.con.execute("SELECT count(*), min(ano), max(ano) FROM leis").fetchone()
        tipos = {r[0]: r[1] for r in self.con.execute("SELECT tipo, count(*) FROM leis GROUP BY tipo ORDER BY 2 DESC")}
        temas = Counter(t for r in self.con.execute("SELECT temas FROM leis") for t in json.loads(r[0]))
        return {"leis": tot[0], "ano_min": tot[1], "ano_max": tot[2], "tipos": tipos,
                "temas": dict(temas.most_common()), "semantica": self.modelo is not None,
                "explicacao_tipos": {r: e for r, e, _ in TIPOS} | {"outros": "Outros assuntos"}}

    def buscar(self, q: str, limite: int = 10, tipo: str | None = None, tema: str | None = None,
               ano_de: int | None = None, ano_ate: int | None = None) -> list[dict]:
        q = q.strip()
        filtro = {r["id"] for r in self.con.execute(
            "SELECT id, temas FROM leis WHERE (? IS NULL OR tipo = ?) AND (? IS NULL OR ano >= ?) AND (? IS NULL OR ano <= ?)",
            (tipo, tipo, ano_de, ano_de, ano_ate, ano_ate)) if not tema or tema in json.loads(r["temas"])}
        rankings: dict[str, list[int]] = {}
        trecho: dict[int, str] = {}
        if q and self.modelo is not None and self.vets is not None:
            vq = self.modelo.consultas([q])[0]
            s = self.vets @ vq
            rankings["semantica"] = [self.ids[i] for i in np.argsort(-s) if self.ids[i] in filtro][:50]
            if self.art_vets is not None and len(self.art_ids):
                sa = self.art_vets @ vq
                vistos = []
                for i in np.argsort(-sa)[:600]:
                    lid = int(self.art_lei[i])
                    if lid in filtro and lid not in vistos:
                        vistos.append(lid)
                        r = self.con.execute("SELECT rotulo, texto FROM artigos WHERE id = ?", (self.art_ids[i],)).fetchone()
                        trecho[lid] = f"{r['rotulo']} {r['texto'][:320]}"
                    if len(vistos) >= 50:
                        break
                rankings["artigo"] = vistos
        termos = [t for t in re.findall(r"\w+", norm(q)) if t not in STOP and len(t) > 2]
        if termos:
            consulta_fts = " OR ".join(f'"{t}"*' for t in termos)
            try:
                rs = self.con.execute(
                    "SELECT rowid, snippet(leis_fts, 3, '[', ']', ' … ', 18) AS sn FROM leis_fts WHERE leis_fts MATCH ? "
                    "ORDER BY bm25(leis_fts, 8.0, 6.0, 5.0, 1.0) LIMIT 80", (consulta_fts,)).fetchall()
            except sqlite3.OperationalError:
                rs = []
            rankings["texto"] = [r["rowid"] for r in rs if r["rowid"] in filtro][:50]
            for r in rs:
                trecho.setdefault(r["rowid"], r["sn"])
            pc = []
            for r in self.con.execute("SELECT id, palavras_chave, temas FROM leis"):
                if r["id"] not in filtro:
                    continue
                alvo = norm(" ".join(json.loads(r["palavras_chave"]) + json.loads(r["temas"])))
                n = sum(1 for t in termos if t in alvo)
                if n:
                    pc.append((n, r["id"]))
            rankings["palavras_chave"] = [i for _, i in sorted(pc, key=lambda x: -x[0])][:50]
        if not q:
            rankings["recentes"] = [r["id"] for r in self.con.execute("SELECT id FROM leis ORDER BY ano DESC, CAST(numero AS INTEGER) DESC")
                                    if r["id"] in filtro][:limite]
        pontos: dict[int, float] = Counter()
        sinais: dict[int, list[str]] = {}
        for nome, lista in rankings.items():
            for pos, lid in enumerate(lista, 1):
                pontos[lid] += 1 / (60 + pos)
                sinais.setdefault(lid, []).append(nome)
        melhores = sorted(pontos, key=lambda i: -pontos[i])[:limite]
        return [self.resumo(i, trecho.get(i), sinais.get(i, []), pontos[i]) for i in melhores]

    def resumo(self, lid: int, trecho: str | None = None, sinais=None, pont: float = 0.0) -> dict:
        r = self.con.execute("SELECT * FROM leis WHERE id = ?", (lid,)).fetchone()
        return {"id": r["id"], "titulo": r["titulo"], "ano": r["ano"], "numero": r["numero"], "data": r["data"],
                "sumula": r["sumula"], "tipo": r["tipo"], "tipo_explicacao": r["tipo_explicacao"],
                "temas": json.loads(r["temas"]), "palavras_chave": json.loads(r["palavras_chave"]),
                "url": r["url"], "origem": r["origem"], "autoria": r["autoria"], "trecho": trecho,
                "sinais": sinais or [], "pontuacao": round(pont, 4)}

    def detalhe(self, lid: int) -> dict | None:
        if not self.con.execute("SELECT 1 FROM leis WHERE id = ?", (lid,)).fetchone():
            return None
        d = self.resumo(lid)
        d["artigos"] = [{"rotulo": a["rotulo"], "texto": a["texto"]} for a in
                        self.con.execute("SELECT rotulo, texto FROM artigos WHERE lei_id = ? ORDER BY id", (lid,))]
        d["texto"] = self.con.execute("SELECT texto FROM leis WHERE id = ?", (lid,)).fetchone()[0]
        return d

    def adicionar(self, titulo: str, texto: str, origem: str = "ocr", ano: int | None = None) -> dict:
        """Indexa um texto vindo do OCR (já corrigido) como nova lei pesquisável."""
        m = re.search(r"S[ÚU]MULA\s*:?\s*(.+?)(?:\n\s*\n|\n(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ ,]{20,}))", texto, re.S | re.I)
        if m:
            sumula = re.sub(r"\s+", " ", m.group(1)).strip()
        else:
            linhas = [l.strip() for l in texto.split("\n") if len(l.strip()) > 30]
            sumula = next((l for l in linhas if re.match(r"(Disp[õo]e|Institui|Autoriza|Altera|Denomina|Declara|Confere|Cria|Estabelece|Concede)", l)),
                          linhas[0] if linhas else titulo)[:400]
        m_t = re.search(r"\bLEI\b[^\n]{0,80}?(\d[\d.]*)\s*(?:[,/]\s*(?:DE\s+.*?)?(\d{4}))?", texto, re.I)
        lei = {"titulo": titulo, "sumula": sumula, "texto": texto, "origem": origem, "url": None, "autoria": "",
               "numero": m_t.group(1).replace(".", "") if m_t else None, "ano": ano or (int(m_t.group(2)) if m_t and m_t.group(2) else None),
               "data": None, "id_portal": None}
        with self.trava:
            v = self.modelo.passagens([f"{titulo}. {sumula}\n{texto[:1500]}"])[0] if self.modelo else None
            arts = dividir_artigos(texto)
            va = self.modelo.passagens([f"{sumula} | {r} {t}"[:1200] for r, t in arts]) if (arts and self.modelo) else None
            lid = _inserir(self.con, lei, self.analisador.analisar(lei, v), v, arts, va)
            self.con.commit()
            self._carregar()
        return self.detalhe(lid)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--indexar":
        print(indexar_portal())
    else:
        base = BaseDeLeis()
        for r in base.buscar(" ".join(sys.argv[1:]) or "", limite=8):
            print(f"\n{r['titulo']} ({r['ano']}) [{r['tipo']}] temas={r['temas']} sinais={r['sinais']}")
            print(f"  {r['sumula'][:160]}")
            print(f"  palavras-chave: {', '.join(r['palavras_chave'])}")
