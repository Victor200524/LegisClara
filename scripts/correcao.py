"""
Correção pós-OCR: ortografia, contexto, consistência e regras de redação jurídica.

O texto BRUTO do OCR nunca é alterado. Este módulo produz uma camada separada:
  - `texto_corrigido`: o bruto com as correções de ALTA confiança aplicadas;
  - `correcoes`: cada ocorrência com original, sugestão, método, motivo, confiança,
    alternativas e se foi aplicada automaticamente ou ficou só como sugestão.

Quatro níveis, do mais seguro ao mais "inteligente":
1. regra_juridica — convenções de redação legislativa (LC 95/1998):
     ordinal até o nono ("Art. 1º", não "Art. 1°" nem "Art. 1."); "Nº" com ordinal, não grau;
     incisos em algarismos romanos válidos e em sequência (I, II, III, IV…).
2. consistencia   — o mesmo nome próprio aparece de formas diferentes no documento
     ("Estrela do Norte" no cabeçalho x "Estrela do Noite" no corpo): vale a forma mais
     frequente/confiável.
3. dicionario     — palavra inexistente (Hunspell pt-BR VERO + léxico jurídico) é trocada
     pelo candidato mais provável. Candidatos: SymSpell (até 2 edições) + variantes por
     confusões típicas de OCR (l/i/1, rn/m, u/n, c/e, acento perdido…), ranqueados por uma
     distância de edição PONDERADA (trocas típicas de OCR custam pouco).
4. contexto       — o BERTimbau (BERT em português) escolhe, entre os candidatos, o que faz
     mais sentido na frase (ex.: "pessca" -> "pessoa" ou "pesca"?).

Decisão conservadora: só aplica sozinho quando o custo de edição é baixo e o vencedor tem
margem clara; nomes próprios fora do dicionário nunca são trocados automaticamente
(exceto acentuação). O resto vira sugestão para revisão humana.
"""

from __future__ import annotations

import html
import json
import math
import re
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_RECURSOS = RAIZ / "recursos"
DICIONARIO_HUNSPELL = PASTA_RECURSOS / "dicionario_pt_BR" / "pt_BR"
LEXICO_JURIDICO = PASTA_RECURSOS / "lexico_juridico.tsv"
# leis de Londrina: dentro do repositório (Leis_Londrina/) ou ao lado do projeto
PASTA_LEIS_LONDRINA = next((p for p in (RAIZ / "Leis_Londrina" / "documentos", RAIZ.parent / "Leis_Londrina" / "documentos") if p.exists()), RAIZ / "Leis_Londrina" / "documentos")
MODELO_CONTEXTO = "neuralmind/bert-base-portuguese-cased"
VERSAO = "1.0"

LETRAS = "A-Za-zÀ-ÖØ-öø-ÿ"
RE_PALAVRA = re.compile(rf"[{LETRAS}]+(?:-[{LETRAS}]+)*")
CONECTORES = {"de", "da", "do", "das", "dos", "e"}


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------

def sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.combining(c))


def ajustar_caixa(modelo: str, palavra: str) -> str:
    """Aplica à sugestão o padrão de maiúsculas do original (TUDO, Título ou minúsculas)."""
    letras = [c for c in modelo if c.isalpha()]
    if len(letras) > 1 and all(c.isupper() for c in letras):
        return palavra.upper()
    if modelo[:1].isupper():
        return palavra[:1].upper() + palavra[1:]
    return palavra


# Custos de substituição para trocas típicas de OCR (simétricos).
_PARES_BARATOS = {
    0.15: ["aá", "aà", "aâ", "aã", "eé", "eê", "ií", "oó", "oô", "oõ", "uú", "uü", "cç",
           "AÁ", "AÀ", "AÂ", "AÃ", "EÉ", "EÊ", "IÍ", "OÓ", "OÔ", "OÕ", "UÚ", "CÇ",
           "áà", "áâ", "áã", "âã", "éê", "óô", "óõ", "ôõ"],
    0.3: ["il", "i1", "l1", "Il", "I1", "lI", "i!", "l|", "I|", "O0", "o0", "S5", "s5", "B8", "Z2",
          "ií", "lí", "ce", "uv", "un", "nu", "rn", "ri", "ti", "fi", "ft", "tf", "hb", "ao",
          "eo", "ec", "gq", "mn"],
}
CUSTO_SUB = {}
for custo, pares in _PARES_BARATOS.items():
    for a, b in pares:
        CUSTO_SUB[(a, b)] = CUSTO_SUB[(b, a)] = min(custo, CUSTO_SUB.get((a, b), 9))
# multicaracteres confundidos (aplicados como variantes antes da busca)
TROCAS_MULTI = [("rn", "m"), ("m", "rn"), ("cl", "d"), ("d", "cl"), ("vv", "w"), ("ii", "u"), ("li", "h"), ("ln", "h")]


def custo_sub(a: str, b: str) -> float:
    if a == b:
        return 0.0
    if a.lower() == b.lower():
        return 0.05
    return CUSTO_SUB.get((a, b), CUSTO_SUB.get((a.lower(), b.lower()), 1.0))


def distancia_ponderada(a: str, b: str) -> float:
    """Levenshtein com custos de OCR; inserir/remover pontuação custa pouco."""
    n, m = len(a), len(b)
    ant = [j * 1.0 for j in range(m + 1)]
    for i in range(1, n + 1):
        atual = [i * 1.0] + [0.0] * m
        for j in range(1, m + 1):
            atual[j] = min(ant[j] + (0.3 if a[i - 1] in ".,'-" else 1.0),
                           atual[j - 1] + (0.3 if b[j - 1] in ".,'-" else 1.0),
                           ant[j - 1] + custo_sub(a[i - 1], b[j - 1]))
        ant = atual
    return ant[m]


def romano_para_int(r: str) -> int | None:
    if not re.fullmatch(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})", r) or not r:
        return None
    v = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    for i, c in enumerate(r):
        total += -v[c] if i + 1 < len(r) and v[c] < v[r[i + 1]] else v[c]
    return total


def int_para_romano(n: int) -> str:
    s = ""
    for v, r in [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                 (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]:
        while n >= v:
            s += r
            n -= v
    return s


# ---------------------------------------------------------------------------
# Léxico jurídico (a partir das leis de Londrina)
# ---------------------------------------------------------------------------

def construir_lexico_juridico(pasta_leis: Path = PASTA_LEIS_LONDRINA, destino: Path = LEXICO_JURIDICO,
                              excluir_com_pdf: bool = True) -> dict:
    """
    Conta as palavras das leis (lei.html). Por padrão EXCLUI as leis que têm PDF oficial,
    pois elas são o gabarito do benchmark — incluí-las daria ao corretor a resposta.
    """
    contagem: Counter = Counter()
    usadas, excluidas = 0, []
    for arq in sorted(pasta_leis.glob("*/*/lei.html")):
        if excluir_com_pdf and (arq.parent / "lei.pdf").exists():
            excluidas.append(f"{arq.parent.parent.name}/{arq.parent.name}")
            continue
        bruto = arq.read_text(encoding="utf-8", errors="replace")
        bruto = re.sub(r"<!--.*?-->|<style.*?</style>|<s>.*?</s>", " ", bruto, flags=re.S | re.I)
        texto = html.unescape(re.sub(r"<[^>]+>", " ", bruto))
        contagem.update(w.lower() for w in RE_PALAVRA.findall(texto) if len(w) > 1)
        usadas += 1
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as f:
        f.write(f"# léxico jurídico: {usadas} leis de Londrina; excluídas (gabarito do benchmark): {', '.join(excluidas)}\n")
        for w, c in contagem.most_common():
            f.write(f"{w}\t{c}\n")
    return {"leis": usadas, "excluidas": excluidas, "palavras": len(contagem)}


# ---------------------------------------------------------------------------
# Modelo de contexto (BERTimbau)
# ---------------------------------------------------------------------------

class ModeloContexto:
    """Pseudo-log-verossimilhança (PLL) de uma palavra dentro da frase, com BERT mascarado."""

    def __init__(self, nome: str = MODELO_CONTEXTO):
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer

        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(nome)
        self.modelo = AutoModelForMaskedLM.from_pretrained(nome).eval()

    def pontuar(self, esquerda: str, candidatos: list[str], direita: str) -> list[float]:
        """Soma do log-prob de cada subtoken do candidato, mascarando um subtoken por vez."""
        lotes, donos = [], []
        for k, cand in enumerate(candidatos):
            ids_esq = self.tok(esquerda, add_special_tokens=False)["input_ids"][-40:]
            ids_cand = self.tok((" " if esquerda else "") + cand, add_special_tokens=False)["input_ids"]
            ids_dir = self.tok(" " + direita, add_special_tokens=False)["input_ids"][:40] if direita else []
            base = [self.tok.cls_token_id] + ids_esq + ids_cand + ids_dir + [self.tok.sep_token_id]
            inicio = 1 + len(ids_esq)
            for p in range(len(ids_cand)):
                ids = list(base)
                alvo = ids[inicio + p]
                ids[inicio + p] = self.tok.mask_token_id
                lotes.append((ids, inicio + p, alvo))
                donos.append(k)
        if not lotes:
            return [0.0] * len(candidatos)
        maior = max(len(l[0]) for l in lotes)
        entrada = self.torch.full((len(lotes), maior), self.tok.pad_token_id)
        atencao = self.torch.zeros((len(lotes), maior), dtype=self.torch.long)
        for i, (ids, _, _) in enumerate(lotes):
            entrada[i, :len(ids)] = self.torch.tensor(ids)
            atencao[i, :len(ids)] = 1
        with self.torch.no_grad():
            logits = self.modelo(input_ids=entrada, attention_mask=atencao).logits
        logp = self.torch.log_softmax(logits, dim=-1)
        pont = [0.0] * len(candidatos)
        for i, (_, pos, alvo) in enumerate(lotes):
            pont[donos[i]] += float(logp[i, pos, alvo])
        return pont


# ---------------------------------------------------------------------------
# Corretor
# ---------------------------------------------------------------------------

@dataclass
class Correcao:
    linha: int                  # 1-based, no texto bruto
    inicio: int                 # deslocamento (caractere) dentro da linha
    fim: int
    original: str
    sugestao: str | None
    aplicada: bool
    metodo: str                 # regra_juridica | consistencia | dicionario | contexto
    motivo: str
    confianca: float
    alternativas: list = field(default_factory=list)


class Corretor:
    def __init__(self, usar_contexto: bool = True, construir_lexico_se_faltar: bool = True):
        t = time.perf_counter()
        from spellchecker import SpellChecker
        from spylls.hunspell import Dictionary
        from symspellpy import SymSpell

        self.hunspell = Dictionary.from_files(str(DICIONARIO_HUNSPELL))
        self.freq: dict[str, int] = dict(SpellChecker(language="pt").word_frequency.dictionary)
        if not LEXICO_JURIDICO.exists() and construir_lexico_se_faltar and PASTA_LEIS_LONDRINA.exists():
            construir_lexico_juridico()
        self.juridico: dict[str, int] = {}
        if LEXICO_JURIDICO.exists():
            for linha in LEXICO_JURIDICO.read_text(encoding="utf-8").splitlines():
                if linha and not linha.startswith("#"):
                    w, c = linha.split("\t")
                    self.juridico[w] = int(c)
        # frequência combinada: o léxico jurídico pesa como um corpus muito maior
        for w, c in self.juridico.items():
            self.freq[w] = self.freq.get(w, 0) + c * 2000
        self.sym = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
        for w, c in self.freq.items():
            self.sym.create_dictionary_entry(w, c)
        self.contexto = ModeloContexto() if usar_contexto else None
        self._cache_valida: dict[str, bool] = {}
        self.tempo_carga_s = round(time.perf_counter() - t, 1)

    # ---------------------------------------------------------------- validade
    def valida(self, w: str) -> bool:
        if w in self._cache_valida:
            return self._cache_valida[w]
        r = (w.lower() in self.juridico or self.hunspell.lookup(w) or self.hunspell.lookup(w.lower())
             or (w[:1].isupper() and self.hunspell.lookup(w[:1] + w[1:].lower())))
        if not r and "-" in w:
            r = all(self.valida(p) for p in w.split("-") if p)
        self._cache_valida[w] = bool(r)
        return bool(r)

    # ---------------------------------------------------------------- candidatos
    def _variantes_ocr(self, w: str) -> set[str]:
        """Variantes pelas confusões de OCR (1 troca), checadas no Hunspell."""
        var = set()
        for i, c in enumerate(w):
            for (a, b) in CUSTO_SUB:
                if a == c and CUSTO_SUB[(a, b)] <= 0.3 and b.isalpha():
                    var.add(w[:i] + b + w[i + 1:])
        for a, b in TROCAS_MULTI:
            i = w.find(a)
            while i >= 0:
                var.add(w[:i] + b + w[i + len(a):])
                i = w.find(a, i + 1)
        if len(w) > 4:  # letra extra/faltando no fim é comum (borda da caixa)
            var.update({w[:-1]} | {w + x for x in "aeiolrs"})
        return {v for v in var if v and self.valida(v)}

    def candidatos(self, w: str) -> list[dict]:
        from symspellpy import Verbosity

        baixo = w.lower()
        achados = {s.term for s in self.sym.lookup(baixo, Verbosity.ALL, max_edit_distance=2)}
        achados |= {v.lower() for v in self._variantes_ocr(baixo)}
        cands = []
        for c in achados:
            if c == baixo or not self.valida(c):
                continue
            custo = distancia_ponderada(baixo, c)
            if custo > max(1.3, 0.2 * len(baixo)):
                continue
            cands.append({"palavra": c, "custo": round(custo, 3), "frequencia": self.freq.get(c, 0)})
        cands.sort(key=lambda x: (x["custo"], -x["frequencia"]))
        return cands[:8]

    # ---------------------------------------------------------------- correção de uma página/documento
    def corrigir_documento(self, paginas: list[dict]) -> list[dict]:
        """
        paginas: registros do OCR (precisam de `texto` e, de preferência, `linhas_ordenadas`
        para saber a confiança de cada linha). Devolve um dicionário de correção por página.
        """
        linhas_doc = []  # (pagina_idx, n_linha, texto, confianca_min)
        for pi, reg in enumerate(paginas):
            linhas = (reg.get("texto") or "").split("\n")
            confs = [min((f["confianca"] for f in l if f.get("confianca") is not None), default=1.0)
                     for l in reg.get("linhas_ordenadas", [])]
            for li, t in enumerate(linhas):
                linhas_doc.append((pi, li + 1, t, confs[li] if li < len(confs) else 1.0))

        correcoes: list[list[Correcao]] = [[] for _ in paginas]
        ocupado: set = set()  # (pagina, linha, inicio) já tratados

        def add(pi, c: Correcao):
            chave = (pi, c.linha, c.inicio)
            if chave in ocupado:
                return
            ocupado.add(chave)
            correcoes[pi].append(c)

        for pi, ln, t, conf in linhas_doc:
            for c in self._regras_ordinais(ln, t):
                add(pi, c)
        for pi, c in self._regras_incisos(linhas_doc):
            add(pi, c)
        for pi, c in self._consistencia(linhas_doc):
            add(pi, c)
        for pi, c in self._dicionario(linhas_doc, ocupado):
            add(pi, c)

        saida = []
        for pi, reg in enumerate(paginas):
            cs = sorted(correcoes[pi], key=lambda c: (c.linha, c.inicio))
            linhas = (reg.get("texto") or "").split("\n")
            corrigidas = list(linhas)
            for c in sorted([c for c in cs if c.aplicada], key=lambda c: (c.linha, -c.inicio)):
                l = corrigidas[c.linha - 1]
                corrigidas[c.linha - 1] = l[:c.inicio] + c.sugestao + l[c.fim:]
            saida.append({
                "versao": VERSAO,
                "texto_corrigido": "\n".join(corrigidas),
                "correcoes": [asdict(c) for c in cs],
                "estatisticas": {
                    "aplicadas": sum(c.aplicada for c in cs),
                    "sugestoes": sum((not c.aplicada) and c.sugestao is not None for c in cs),
                    "sem_sugestao": sum(c.sugestao is None for c in cs),
                    "por_metodo": dict(Counter(c.metodo for c in cs)),
                },
                "configuracao": {"contexto": MODELO_CONTEXTO if self.contexto else None,
                                 "dicionario": "Hunspell pt_BR (VERO, LibreOffice) + léxico jurídico + frequências pyspellchecker"},
            })
        return saida

    # ---------------------------------------------------------------- 1. regras jurídicas
    def _regras_ordinais(self, ln: int, t: str) -> list[Correcao]:
        out = []
        # "Art. 1°" / "§ 2°" / "Artigo 3°" -> º  (grau no lugar do ordinal)
        for m in re.finditer(r"(?:\bArt(?:igo)?\.?|§)\s*\d+\s*(°)", t):
            out.append(Correcao(ln, m.start(1), m.end(1), "°", "º", True, "regra_juridica",
                                "símbolo de grau no lugar do ordinal em artigo/parágrafo", 0.98))
        # "N°" / "n°" / "N.°" -> º
        for m in re.finditer(r"\b[Nn]\.?\s?(°)", t):
            out.append(Correcao(ln, m.start(1), m.end(1), "°", "º", True, "regra_juridica",
                                "símbolo de grau no lugar do ordinal em “nº”", 0.97))
        # "Art. 1. Texto" -> "Art. 1º Texto": LC 95/1998 manda ordinal do 1º ao 9º
        for m in re.finditer(r"\bArt(?:igo)?\.?\s*([1-9])(\.)(?=\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", t):
            out.append(Correcao(ln, m.start(2), m.end(2), ".", "º", True, "regra_juridica",
                                "artigos 1 a 9 usam ordinal (LC 95/1998, art. 10, I); o ponto é o “º” mal lido", 0.9))
        return out

    def _regras_incisos(self, linhas_doc) -> list[tuple[int, Correcao]]:
        """Incisos: blocos de linhas 'X - texto' entre artigos; rótulos devem ser I, II, III…"""
        re_inc = re.compile(r"^(\s*)([IVXLCivxlc1l|!]{1,6})(\s*[-–—])\s*\S")
        out, bloco = [], []

        def fechar():
            if len(bloco) >= 2:
                romanos = sum(1 for *_, r in bloco if re.search(r"[IVXivx]", r))
                if romanos >= max(1, len(bloco) // 2):  # é uma lista de incisos romanos
                    esperado = 1
                    for pi, ln, ini, fim, r in bloco:
                        mapeado = re.sub(r"[1l|!i]", "I", r).replace("v", "V").replace("x", "X").replace("c", "C")
                        valor = romano_para_int(mapeado)
                        alvo = int_para_romano(esperado)
                        if valor == esperado:
                            sug, conf, motivo = mapeado, 0.95, "rótulo de inciso com caractere confundido (l/1/i → I)"
                        elif distancia_ponderada(r.upper(), alvo) <= 1.0 or (set(mapeado) == {"I"} and set(alvo) == {"I"}):
                            sug, conf, motivo = alvo, 0.85, f"sequência de incisos: esperado {alvo} após {int_para_romano(esperado - 1) or 'início'}"
                        else:
                            sug, conf, motivo = None, 0.0, "rótulo de inciso fora da sequência; conferir"
                        if sug != r:
                            out.append((pi, Correcao(ln, ini, fim, r, sug, sug is not None and conf >= 0.85,
                                                     "regra_juridica", motivo, conf)))
                        esperado = (valor if valor == esperado else esperado) + 1
            bloco.clear()

        for pi, ln, t, _ in linhas_doc:
            if re.match(r"^\s*(Art(igo)?\.?\s*\d|§|Par[áa]grafo|CAP[ÍI]TULO|T[ÍI]TULO|SE[ÇC][ÃA]O)", t, re.I):
                fechar()
                continue
            m = re_inc.match(t)
            if m:
                bloco.append((pi, ln, m.start(2), m.end(2), m.group(2)))
        fechar()
        return out

    # ---------------------------------------------------------------- 2. consistência
    def _consistencia(self, linhas_doc) -> list[tuple[int, Correcao]]:
        """Nomes próprios compostos (ex.: "Estrela do Norte") escritos de formas diferentes."""
        re_nome = re.compile(rf"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][{LETRAS}]+(?:\s+(?:d[aeo]s?|e)\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][{LETRAS}]+|\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][{LETRAS}]+)+")
        ocorr = []  # (pi, ln, inicio, palavras[(txt, ini, fim)], conf)
        for pi, ln, t, conf in linhas_doc:
            for m in re_nome.finditer(t):
                pals = [(w.group(0), m.start() + w.start(), m.start() + w.end()) for w in RE_PALAVRA.finditer(m.group(0))]
                for i in range(len(pals)):
                    for j in range(i + 2, len(pals) + 1):
                        sub = pals[i:j]
                        if sub[0][0].lower() in CONECTORES or sub[-1][0].lower() in CONECTORES:
                            continue
                        ocorr.append((pi, ln, sub, conf))
        forma = lambda pals: tuple(sem_acento(p[0]).lower() for p in pals)
        cont = Counter(forma(o[2]) for o in ocorr)
        melhor_conf = defaultdict(float)
        for o in ocorr:
            melhor_conf[forma(o[2])] = max(melhor_conf[forma(o[2])], o[3])
        out = []
        for pi, ln, pals, conf in ocorr:
            f = forma(pals)
            for g, n in cont.items():
                if g == f or len(g) != len(f):
                    continue
                difs = [i for i in range(len(f)) if f[i] != g[i]]
                if len(difs) != 1 or f[difs[0]] in CONECTORES:
                    continue
                i = difs[0]
                if distancia_ponderada(f[i], g[i]) > 1.6:
                    continue
                # a outra forma precisa ser mais frequente OU vista com confiança maior
                if not (n > cont[f] or (n == cont[f] and melhor_conf[g] > conf + 0.03)):
                    continue
                orig, ini, fim = pals[i]
                # recupera a grafia (com acento) da outra forma em alguma ocorrência
                exemplo = next(p[2][i][0] for p in ocorr if forma(p[2]) == g)
                sug = ajustar_caixa(orig, exemplo.lower() if not exemplo.isupper() else exemplo.lower())
                if exemplo[:1].isupper() and not orig.isupper():
                    sug = exemplo[:1] + exemplo[1:].lower() if exemplo.isupper() else exemplo
                aplicar = n >= 2 or melhor_conf[g] >= 0.95
                if any(c.linha == ln and c.inicio == ini for _, c in out if _ == pi):
                    break
                out.append((pi, Correcao(ln, ini, fim, orig, sug, aplicar, "consistencia",
                                         f"o documento traz “{' '.join(p for p in g)}” {n}× (confiança até {melhor_conf[g]:.2f}); "
                                         f"aqui aparece “{orig}” (confiança da linha {conf:.2f})",
                                         0.9 if aplicar else 0.6)))
                break
        return out

    # ---------------------------------------------------------------- 3 e 4. dicionário + contexto
    def _ignorar(self, w: str, t: str, ini: int, fim: int) -> bool:
        if len(w) < 3:
            return True
        if (ini > 0 and t[ini - 1].isdigit()) or (fim < len(t) and t[fim:fim + 1].isdigit()):
            return True  # colado a números: códigos, "Art.l0" etc. (sinalizados pelo ocr.py)
        if w.isupper() and len(w) <= 5:
            return True  # siglas: CEP, SP, LDO, SÚMULA curta…
        if fim < len(t) and t[fim] in "@/" or (ini > 0 and t[ini - 1] in "@/."):
            return True  # e-mails, URLs, abreviações compostas
        if fim < len(t) and t[fim] == "." and len(w) <= 4:
            return True  # abreviações: Art., Cx., Av.
        return False

    def _dicionario(self, linhas_doc, ocupado) -> list[tuple[int, Correcao]]:
        out = []
        for idx, (pi, ln, t, conf) in enumerate(linhas_doc):
            for m in RE_PALAVRA.finditer(t):
                w, ini, fim = m.group(0), m.start(), m.end()
                if (pi, ln, ini) in ocupado or self._ignorar(w, t, ini, fim):
                    continue
                # hifenização no fim da linha ("sancio-" + "no"): valida a palavra unida
                if fim < len(t) and t[fim:].strip() == "-" or (w.endswith("-")):
                    continue
                if t.rstrip().endswith(w + "-") or (idx > 0 and ini == len(t) - len(t.lstrip()) and
                                                     linhas_doc[idx - 1][2].rstrip().endswith("-")):
                    continue
                if self.valida(w):
                    continue
                cands = self.candidatos(w)
                proprio = w[:1].isupper() and not w.isupper()
                if not cands:
                    out.append((pi, Correcao(ln, ini, fim, w, None, False, "dicionario",
                                             "palavra não encontrada no dicionário e sem sugestão próxima (nome próprio? sigla?)", 0.0)))
                    continue
                metodo = "dicionario"
                if self.contexto and len(cands) > 1:
                    top = cands[:5]
                    esq = t[:ini] if ini else (linhas_doc[idx - 1][2] if idx > 0 else "")
                    dirt = t[fim:] if t[fim:].strip() else (linhas_doc[idx + 1][2] if idx + 1 < len(linhas_doc) else "")
                    ctx = self.contexto.pontuar(esq[-200:], [ajustar_caixa(w, c["palavra"]) for c in top], dirt[:200])
                    for c, s in zip(top, ctx):
                        c["contexto"] = round(s, 3)
                        bonus = 4.0 if sem_acento(c["palavra"]) == sem_acento(w.lower()) else 0.0
                        c["pontuacao"] = round(s - 4.0 * c["custo"] + 0.3 * math.log10(c["frequencia"] + 1) + bonus, 3)
                    top.sort(key=lambda c: -c["pontuacao"])
                    cands = top + cands[5:]
                    metodo = "contexto"
                    margem = top[0]["pontuacao"] - top[1]["pontuacao"]
                else:
                    margem = 99.0 if len(cands) == 1 else (cands[1]["custo"] - cands[0]["custo"]) * 3
                melhor = cands[0]
                sug = ajustar_caixa(w, melhor["palavra"])
                so_acento = sem_acento(sug).lower() == sem_acento(w).lower()
                aplicar = (melhor["custo"] <= 1.0 and margem >= 1.0 and (not proprio or so_acento)) or \
                          (so_acento and margem >= 0.3)
                confianca = round(min(0.99, 0.5 + 0.12 * min(margem, 4) - 0.2 * melhor["custo"]), 2)
                motivo = (f"“{w}” não existe no dicionário; " +
                          ("só faltou/sobrou acento" if so_acento else f"custo de edição {melhor['custo']}") +
                          (f"; o contexto preferiu “{sug}” (margem {margem:.1f})" if metodo == "contexto" else "") +
                          ("" if aplicar else "; ficou como sugestão (margem pequena, custo alto ou nome próprio)"))
                out.append((pi, Correcao(ln, ini, fim, w, sug, aplicar, metodo, motivo, max(0.0, confianca),
                                         alternativas=cands[:5])))
        return out


_corretor: Corretor | None = None


def obter_corretor(usar_contexto: bool = True) -> Corretor:
    """Instância única (carregar dicionários + BERT leva ~20 s)."""
    global _corretor
    if _corretor is None or (usar_contexto and _corretor.contexto is None):
        _corretor = Corretor(usar_contexto=usar_contexto)
    return _corretor


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Corrige o texto de pagina_NNN.json (gera pagina_NNN_correcao.json).")
    ap.add_argument("pasta", type=Path, help="pasta com pagina_NNN.json")
    ap.add_argument("--sem-contexto", action="store_true")
    ap.add_argument("--construir-lexico", action="store_true")
    a = ap.parse_args()
    if a.construir_lexico:
        print(construir_lexico_juridico())
    regs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(a.pasta.glob("pagina_[0-9][0-9][0-9].json"))]
    res = obter_corretor(not a.sem_contexto).corrigir_documento(regs)
    for reg, r in zip(regs, res):
        destino = a.pasta / f"pagina_{reg['pagina']:03d}_correcao.json"
        destino.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(destino.name, r["estatisticas"])
