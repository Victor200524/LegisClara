# Estrutura das leis municipais de Londrina/PR: mapeamento da amostra

Amostra: 237 leis em `documentos/<ano>/lei_<numero>/` (1948–2026, 3 por ano), com 237 `lei.html`, 237 `coleta.json` e 6 `lei.pdf`.
Método: conversão de cada HTML com `html.parser` da stdlib, preservando marcas de negrito, tachado, tabelas, comentários e classes CSS, seguida de leitura. As 214 leis com menos de 12 mil caracteres foram lidas integralmente, e as 2.790 primeiras linhas (1948–1984) linha a linha. As leis longas foram lidas no início, no fim e em todas as linhas estruturais (títulos, capítulos, notas, anexos, tabelas, vetos), com amostras do corpo. Foram elas: 1948/lei_42, 1949/lei_71, 1953/lei_219, 1955/lei_290, 1962/lei_787, 1963/lei_788, 1969/lei_1636, 1971/lei_2027, 1973/lei_2212, 1973/lei_2397, 1987/lei_3940, 1991/lei_4911, 1997/lei_7305, 2011/lei_11117, 2011/lei_11468, 2015/lei_12233, 2020/lei_13193, 2022/lei_13440 e 2026/lei_14065. Os 6 PDFs passaram por `pdftotext -layout` e foram comparados palavra a palavra com o HTML. As contagens vieram de scripts e todos os casos estranhos citados foram conferidos na leitura.

Convenção: os exemplos usam o caminho `ano/lei_numero`. "Família A/B/C/D" refere-se às quatro variantes de marcação HTML descritas na seção 4.

---

## 0. Envelope comum a todos os HTML (gerado pelo portal)

Os 237 arquivos têm o mesmo envelope, independentemente da época:

```html
<title>LEI ORDINÁRIA Nº 22/1948</title>
<div style="width:100%; font-family:Arial; font-size:14px; ...">
<p style="font-size:18px; font-weight:bold; text-align:left;">LEI ORDINÁRIA Nº 22/1948</p>   ← título repetido
<div style="padding-left:45%;"><br/>[súmula]<br/><br/></div>                                ← súmula
<div style="display:block;"> ... texto da lei ... </div>
```

- O título aparece **duas vezes** (em `<title>` e no `<p>` de 18px) em todas as 237 leis. Em 1960/lei_607 e 2022/lei_13440 há ainda um **segundo `<title>`** (vazio) e um bloco `<style>` dentro do corpo.
- A súmula fica sempre no `<div style="padding-left:45%;">` (237/237).
- O corpo propriamente dito começa no `<div style="display:block;">`.
- Não existe nenhuma imagem real. As 223 `<img>` (em 50 leis) são GIFs transparentes de 1×1 px em `data:image/gif;base64,R0lGODlhAQABAIAAAP...`, com `float:left; width:80px`, usados só como espaçadores nos blocos de assinatura (ex.: 2000/lei_8185, 2015/lei_12310).

---

## 1. Cabeçalho / título

| Formato (campo `titulo` e `<title>`) | Leis | Período | Exemplo |
|---|---|---|---|
| `LEI ORDINÁRIA Nº <n>/<aaaa>` | 229 | 1948 → 2024/lei_13825 | 1948/lei_1 `LEI ORDINÁRIA Nº 1/1948` |
| `LEI ORDINÁRIA Nº <n> - B/<aaaa>` | 1 | 1959 | 1959/lei_502 `LEI ORDINÁRIA Nº 502 - B/1959` |
| `LEI N.º <n>, DE <d> DE <MÊS> DE <aaaa>` | 6 | 2024/lei_13921 (31/12/2024) → 2026 | 2026/lei_14300 `LEI N.º 14300, DE 11 DE NOVEMBRO DE 2026` |
| `LEI N.º <n> - A, DE <d> DE <MÊS> DE <aaaa>` | 1 | pasta 2025 (lei de 1959) | 2025/lei_516 `LEI N.º 516 - A, DE 4 DE DEZEMBRO DE 1959` |

Observações:
- O formato antigo é gerado pelo portal e **não traz a data**. A data só aparece no fecho do texto.
- O formato novo traz a data por extenso e começou na última lei de 2024 (2024/lei_13921). As duas leis anteriores de 2024 (13728, 13825) ainda usam o formato antigo.
- Grafias do "número": `Nº` (formato antigo) e `N.º` (formato novo, inclusive em "PROJETO DE LEI N.º 275/2026" no rodapé de 2026/lei_14300). No corpo aparecem também `nº`, `n°`, `n.º`, `nºs`, `nos` (2009/lei_10759 "lotes nos 49-B") e `Nº.` ("Lei Municipal nº. 10.730", 2009/lei_10850).
- O número no título **não usa ponto de milhar** ("14300", "1291"). No corpo, as citações costumam usar ("Lei nº 11.468").
- Sufixos de letra no número: `502 - B` e `516 - A`. Em ambos, o campo `numero` do `coleta.json` guarda só `"502"` e `"516"`, sem a letra.
- **Lei Complementar: não apareceu nenhuma.** O campo `complementar` é `false` nas 237. As únicas "Leis Complementares" citadas são federais (LC 101/2000 em 2004/lei_9518 e 2022/lei_13440; LC 142/2013 em 2020/lei_13193).
- Divergências entre o ano do título e a pasta/ano: 1968/lei_1291 tem o título `Nº 1291/1967`. A 2025/lei_516 é uma lei de 1959 cadastrada em 2025 (`data_portal` 22/08/2025). A 2026/lei_14065 é `DE 22 DE DEZEMBRO DE 2025`, mas está na listagem de 2026 (`data_portal` 05/01/2026).
- No texto da lei, antes de 2024, não existe linha de título própria. O "Nº" só reaparece dentro de alguns preâmbulos de promulgação ("PROMULGO A LEI Nº 788:", 1963/lei_788; "PROMULGO A SEGUINTE LEI Nº 258", 1955/lei_258; "LEI Nº 1.070:", 1966/lei_1070; "LEI Nº 1448:", 1969/lei_1448).

---

## 2. Súmula / ementa

### 2.1 Rótulo e posição
- A súmula fica sempre logo abaixo do título, no `div` com `padding-left:45%` (237/237).
- **Sem rótulo** em 231 leis.
- **Com rótulo** apenas nas 6 leis da família C (2024–2026): `<strong>SÚMULA:</strong>` (2024/lei_13921, 2025/lei_13990, 2025/lei_14064), `SÚMULA :` com espaço antes dos dois-pontos (2026/lei_14300) e `Súmula:` (2026/lei_14065, 2026/lei_14182).
- Em 2026/lei_14065 e 2026/lei_14182 o rótulo "Súmula:" também está **dentro do campo `sumula` do JSON**.

### 2.2 HTML × `coleta.json`
Após normalizar os espaços, a súmula do HTML e a do JSON coincidem em 228 leis. As 9 diferenças são só de espaçamento ou rótulo:
- 7 casos de espaço antes da nota de revogação: em 1956/lei_291, 1959/lei_528, 2007/lei_10284, 2011/lei_11468 e 2013/lei_11807, o JSON tem "...Obras).(Revogada..." e o HTML tem "...Obras). (Revogada...". Em 2001/lei_8682 o HTML tem "( REVOGADA". Em 1958/lei_476 o HTML tem "1958 )".
- 2 casos em que o rótulo "Súmula:" difere (2026/lei_14065, 2026/lei_14182).

Elementos que **não são ementa** mas estão colados a ela, tanto no HTML quanto no JSON:
- **Notas de revogação da lei inteira** em 32 leis, por exemplo "(REVOGADA pelo Art. 3º da Lei nº 973 de 5 de abril de 1965)" (1952/lei_136) e "(Revogada pelo Art. 254 da Lei nº 11.381 de 21 de novembro de 2011)" (1956/lei_291, 1977/lei_2865, 2000/lei_8040). No HTML a nota é um `<a href>`. Pode haver duas notas: 1953/lei_219 tem "(REVOGADA pelo Art. 222 da Lei nº 2.576...) (Livro III revogado pelo Art. 321 da Lei nº 2692...)".
- **Indicação de substitutivo**, como "(Substitutivo nº 01/93)" (1993/lei_5511, 1994/lei_5676, 1997/lei_7305, 1999/lei_7633 e outras).
- **Lixo de digitação**: 1985/lei_3771 termina com "...ao Distrito de São Luiz. MÁBIO GONÇALVES PALHANO". 1972/lei_2119 começa com acento grave: "`Abre crédito...". 1991/lei_4624 tem uma quebra de linha no meio da súmula do JSON.
- **Rubrica temática em maiúsculas**: "REFORMA DA PREVIDÊNCIA MUNICIPAL - Adere às regras..." (2020/lei_13193).
- **Súmula que não é ementa**: 1958/lei_476 tem "LEI INEXISTENTE (Trata-se na verdade da Resolução nº 20 de 13 de dezembro de 1958)".

### 2.3 Divergências súmula × texto (conferidas na leitura)

| Lei | Súmula | Texto |
|---|---|---|
| 1967/lei_1168 | "Vitório Lombardi" a atual rua 'B' | "VITÓRIO LIBARDI" à atual Rua 3 |
| 1974/lei_2459 | "Horace Wills" | "HORACE WELLS" |
| 1975/lei_2559 | "Escola Joaquim Bernardes da Silva" | "JOAQUIM BERNARDES MARTINS" |
| 1976/lei_2599 | "Dr. Arnaldo Faivro Busato" | "Sr. ARNALDO BUSATO" |
| 1975/lei_2598 | "Lei nº 974/75" | "Lei Municipal nº 974, de 09 de abril de 1965" |
| 1985/lei_3771 | "MÁBIO" (com acento) | "RODOVIA MABIO GONÇALVES PALHANO" |
| 1989/lei_4309 | "NCr$ 200.000,00" | "NCz$ 200.000,00" |
| 1995/lei_6469 | "...e autoriza sua doação à COHAB-LD" | o texto só desafeta (Art. 1º) e tem a cláusula de vigência (Art. 2º); a doação não aparece |
| 1961/lei_706 | "exercício de 1962" | o Art. 1º diz "exercício de 1.963" e o Art. 2º diz 1.962 |

### 2.4 Verbo inicial da súmula (lista completa, 237 leis)

| Verbo | Nº | Exemplo |
|---|---:|---|
| Autoriza | 33 | 1948/lei_22 |
| Dá (denominação / nova redação) | 20 | 1957/lei_387, 1981/lei_3247 |
| Altera | 19 | 1956/lei_291 |
| Abre (crédito) | 17 | 1955/lei_274 |
| Denomina | 17 | 1981/lei_3333 |
| Dispõe | 15 | 1952/lei_155 |
| Desafeta | 15 | 1982/lei_3494 |
| Declara | 13 | 1969/lei_1542 |
| Institui | 11 | 1948/lei_42 |
| Cria | 10 | 1949/lei_43 |
| Confere | 9 | 1950/lei_106 |
| Orça | 8 | 1949/lei_71 |
| Introduz (alterações) | 8 | 1984/lei_3654 |
| Inclui | 6 | 1995/lei_6254 |
| Enquadra | 5 | 1978/lei_2866 |
| Estabelece (1 delas com vírgula: "Estabelece,") | 4 | 1972/lei_2028, 2020/lei_13096 |
| Revoga | 3 | 1948/lei_1 |
| Acresce | 3 | 1950/lei_72 |
| Estende (1 delas com vírgula) | 2 | 1979/lei_3042, 2019/lei_12828 |
| Fixa | 2 | 1962/lei_707 |
| Reestrutura | 2 | 1971/lei_2027 |
| Acrescenta | 2 | 1997/lei_7123 |
| Aprova | 1 | 1962/lei_747 |
| Regula | 1 | 1976/lei_2660 |
| Outorga | 1 | 1986/lei_3849 |
| Considera | 1 | 1986/lei_3894 |
| Restaura | 1 | 1993/lei_5675 |
| Dispensa | 1 | 1994/lei_5857 |
| Prorroga | 1 | 1997/lei_6942 |
| Torna | 1 | 2004/lei_9333 |
| Concede | 1 | 2013/lei_11998 |
| Reconhece | 1 | 2017/lei_12567 |
| (substantivo) "Proibição" | 1 | 2025/lei_516 |
| (rubrica) "REFORMA" | 1 | 2020/lei_13193 |
| (não é verbo) "LEI INEXISTENTE" | 1 | 1958/lei_476 |

Para comparar as súmulas é preciso remover antes o rótulo "Súmula:", o acento grave inicial e a vírgula colada ao verbo.

---

## 3. Preâmbulo (fórmula de promulgação)

Contagem por lei, considerando o primeiro preâmbulo:

| Fórmula | Leis | Período | Exemplos |
|---|---:|---|---|
| "A CÂMARA MUNICIPAL DE LONDRINA, ESTADO DO PARANÁ, **DECRETOU** E EU, **PREFEITO MUNICIPAL**, SANCIONO A SEGUINTE LEI:" | 100 | 1948–1993 (+2013, +2025*) | 1948/lei_22, 1993/lei_5675 |
| idem com "**PREFEITO DO MUNICÍPIO**" | 23 | 1976–1993 (+2013) | 1976/lei_2599, 1986/lei_3939 |
| "...DECRETOU E EU SANCIONO A SEGUINTE LEI:" (sem cargo) | 1 | 1948 | 1948/lei_1 |
| "...**APROVOU** E EU, PREFEITO DO MUNICÍPIO, SANCIONO A SEGUINTE LEI:" | 85 | 1994–2026 | 1994/lei_5676 em diante |
| "...APROVOU E EU, PREFEITO DO MUNICÍPIO **DE LONDRINA**, SANCIONO..." | 2 | 2009, 2024 | 2009/lei_10850, 2024/lei_13921 |
| "...APROVOU [,] E EU, PREFEITO MUNICIPAL, SANCIONO..." | 3 | 1962, 2001, 2011 | 1962/lei_787, 2001/lei_8682, 2011/lei_11468 |
| "...DECRETOU E EU, **PRESIDENTE, PROMULGO** A SEGUINTE LEI [Nº n]:" | 6 | 1955–1969 | 1955/lei_258, 1959/lei_528, 1963/lei_788, 1963/lei_833, 1963/lei_877, 1969/lei_1448 |
| "...APROVOU E EU, PRESIDENTE, PROMULGO A SEGUINTE LEI Nº 1.070:" | 1 | 1966 | 1966/lei_1070 |
| "...APROVOU E EU, PRESIDENTE, PROMULGO, **NOS TERMOS DO PARÁGRAFO 2º DO ARTIGO 66 DA LEI ORGÂNICA DOS MUNICÍPIOS**..." | 2 | 1978, 1981 | 1978/lei_2866, 1981/lei_3419 |
| "...NOS TERMOS DO PARÁGRAFO 4º DO ARTIGO 82 DA LEI ORGÂNICA DOS MUNICÍPIOS..." | 1 | 1988 | 1988/lei_4055 |
| "...NOS TERMOS DO PARÁGRAFO 7º / § 7º / §7º DO ARTIGO 31 DA LEI ORGÂNICA DO MUNICÍPIO [DE LONDRINA]..." | 9 | 1992–2012 | 1992/lei_5129, 1996/lei_6941, 2005/lei_9897, 2009/lei_10668, 2012/lei_11469, 2012/lei_11806 |
| "...NOS TERMOS DO § 3º DO ARTIGO 31 DA LEI ORGÂNICA DO MUNICÍPIO..." | 2 | 1997, 2021 | 1997/lei_7123 (sanção tácita), 2021/lei_13194 (veto integral) |
| **Segundo preâmbulo**: "...APROVOU E EU, PRESIDENTE, PROMULGO, NOS TERMOS DO § 7º DO ARTIGO 31 DA LEI ORGÂNICA DO MUNICÍPIO, **OS SEGUINTES DISPOSITIVOS DA LEI MUNICIPAL Nº 11.117, DE 10 DE JANEIRO DE 2011**:" | 2 | 2011 | 2011/lei_11117, 2011/lei_11468 |
| Sem preâmbulo | 4–5 | — | 1953/lei_175 e 1956/lei_360 (vazias), 1958/lei_476 (inexistente), 1953/lei_219 (começa direto em "PARTE GERAL"), 1967/lei_1168 ("SANCIONO A SEGUINTE:", sem "LEI") |

\* 2025/lei_516 é a lei de 1959 com "DECRETOU".

Observações:
- **DECRETOU → APROVOU**: a troca ocorreu em janeiro de 1994. Em 1993 todas as leis ainda usam DECRETOU (1993/lei_5347, 5511, 5675). A partir de 1994/lei_5676 as leis sancionadas usam APROVOU. Exceções: 1962/lei_787 (APROVOU em 1962) e 2013/lei_11902 e 2013/lei_11998 (DECRETOU em 2013).
- **"PREFEITO MUNICIPAL" → "PREFEITO DO MUNICÍPIO"**: aparece pela primeira vez em 1976/lei_2599 (família B) e na família A a partir de 1986/lei_3939. As duas formas convivem até 2013.
- **Quem promulga (Presidente da Câmara)** e por quê: até 1969 a fórmula não explica o motivo. Depois o motivo aparece no rodapé: "Promulgação oriunda de sanção tácita" (1997/lei_7123, 2012/lei_11469), "...da rejeição de veto total" (2005/lei_9897, 2009/lei_10668, 2012/lei_11806), "...de rejeição de veto integral" (2021/lei_13194) e "...da rejeição de veto parcial" (2011/lei_11117, 2011/lei_11468, 2013/lei_11902).
- **Variações de digitação no preâmbulo**:
  - "A CÂMARA MUNICIPAL A CÂMARA MUNICIPAL DE LONDRINA..." (2012/lei_11469).
  - "A CÂMARA MUNICIPAL, ESTADO DO PARANÁ" sem "DE LONDRINA" (1990/lei_4406).
  - "DECRETOU EU, PREFEITO" sem o "E" (1980/lei_3122).
  - "ESTADO DO PARANÁ. APROVOU" (2001/lei_8682).
  - "ESTADO DO PARANA" sem acento (1959/lei_502, 1960/lei_607).
  - "SANCIONO O SEGUINTE LEI" (1955/lei_290, 1961/lei_706).
  - "decretou e eu, Prefeito Municipal, sanciono a seguinte, Lei:" em minúsculas (1956/lei_326, 1965/lei_965).
  - "L E I :" espaçado (1999/lei_7633, 2025/lei_516).
  - "LEI" quebrado em outra linha ou em outro `<p class="Carta">` (1961/lei_706).
  - "LEI:" alinhado à direita num `<div>` separado (1985/lei_3848).
  - "LEI**:" com os dois-pontos fora do negrito (família C).
  - Na família C o preâmbulo vem junto com o primeiro "CAPÍTULO I" no mesmo `<strong>` (2026/lei_14065).

---

## 4. Corpo e hierarquia

### 4.1 Quatro "famílias" de marcação HTML

| Família | Marcação | Leis | Período | Características |
|---|---|---:|---|---|
| **A** "Carta/RP" | `<p class="Carta">` preâmbulo; `<b>Art. 1º</b>`; `<p class="TitVioleta">` títulos/capítulos; `<p class="recuado">` ou `recuadospan` para o texto citado em alterações; `<p class="RP">` fecho; `<p class="RegPub">` Ref. | 110 | 1948–1993 | um parágrafo por dispositivo, rótulo em negrito, quase sem quebras internas |
| **B** "margem" | preâmbulo em `<b>/<strong>`; `<div class="margem">` com **texto corrido e quebras `<br>` duras a cada ~70 caracteres**; Art./§/incisos **sem negrito**; `<p class="alertafinal">` | 112 | 1949–2024 (exclusiva de 1995 a 2024) | assinaturas em colunas embaralhadas (ver 6 e 10) |
| **C** "SÚMULA" | rótulo SÚMULA; `<div style="text-align: center;">` com o preâmbulo em `<strong>`; `<strong>Art. 1º</strong>`; data em `div` alinhado à direita; assinatura centralizada em `<strong>`; `<span style="font-size:11px"><em>Ref.:</em>` | 6 | 2024/lei_13921–2026 | sem a frase "Este texto não substitui..." |
| **D** atípicas | — | 9 | — | 1960/lei_607 e 2022/lei_13440 têm CSS próprio e classes semânticas (`article`, `indent`; `artigo`, `paragrafo`, `paragrafo-unico`, `inciso`, `alinea`, `capitulo`, `secao`, `titulo-principal`). 1959/lei_502, 1961/lei_608, 1981/lei_3419, 1985/lei_3848 e 2025/lei_516 usam `<strong>` sem classe. 1953/lei_175 e 1956/lei_360 estão vazias. |

Distribuição por quinquênio (A/B/C/D):

| Quinquênio | A | B | C | D |
|---|---:|---:|---:|---:|
| 1945 | 5 | 1 | | |
| 1950 | 14 | | | 1 |
| 1955 | 11 | 2 | | 2 |
| 1960 | 13 | | | 2 |
| 1965 | 13 | 2 | | |
| 1970 | 13 | 2 | | |
| 1975 | 10 | 5 | | |
| 1980 | 12 | 2 | | 1 |
| 1985 | 10 | 4 | | 1 |
| 1990 | 9 | 6 | | |
| 1995–2019 | | 75 | | |
| 2020 | | 13 | 1 | 1 |
| 2025 | | | 5 | 1 |

Antes de 1994 a família B aparece quase só em leis de **utilidade pública, denominação e título honorífico** (ex.: 1949/lei_43, 1957/lei_387, 1969/lei_1542, 1974/lei_2459, 1981/lei_3333). Parece ter vindo de outra fonte de digitação, porque já traz Ref./Autoria e o alerta da Folha de Londrina mesmo em 1949.

Tags e classes: `<b>` (114 leis), `<strong>` (132), `<u>` (21), `<i>`/`<em>`, `<center>` (40), `<font>` (1997/lei_7305, 2003/lei_9180, 2008/lei_10551), `<dl><dt>` (2003/lei_9180), `<ol><li>` (2026/lei_14065), `<sup>` (1971/lei_2027) e âncoras `<a name="art1">`, `<a name="ana1_p1">` e similares (1.322 `a name` em leis antigas).

### 4.2 Níveis hierárquicos (contagem por linha de rótulo, sem comentários)

| Nível | Leis | Ocorrências | Onde |
|---|---:|---:|---|
| PARTE | 2 | 5 | 1953/lei_219 ("PARTE GERAL - Disposições Preliminares", "PARTE ESPECIAL"); 1971/lei_2027 ("TABELA DE VENCIMENTOS: PARTE PRIMEIRA", que é parte de tabela) |
| LIVRO | 1 | 5 | 1953/lei_219 ("LIVRO I - Da Aplicação do Direito Municipal") |
| TÍTULO | 5 | 50 | 1948/lei_42, 1953/lei_219 ("TÍTULO ÚNICO"), 1973/lei_2212, 1973/lei_2397, 2011/lei_11468 (TÍTULO I–XVII) |
| CAPÍTULO | 12 | 195 | 1948/lei_42, 1952/lei_155 (capítulos sem nome), 1953/lei_219, 1971/lei_2027, 1973/lei_2212, 1973/lei_2397, 1997/lei_7305, 2011/lei_11117, 2011/lei_11468, 2020/lei_13193, 2022/lei_13440, 2026/lei_14065 |
| SEÇÃO / Secção | 8 | 101 | 1953/lei_219 ("SECÇÃO", 63), 2011/lei_11468, 1973/lei_2212, 2022/lei_13440, 2026/lei_14065 ("Seção II") |
| SUBSEÇÃO | 2 | 31 | 2011/lei_11468, 2020/lei_13193 |
| "DISPOSIÇÕES FINAIS/GERAIS/PRELIMINARES" soltas, sem rótulo de nível | 4 | 8 | 1953/lei_219, 1973/lei_2212, 2011/lei_11468, 2022/lei_13440 |

- Formas do rótulo: "CAPÍTULO I - DOS CARGOS" (rótulo e nome na mesma linha, com hífen; família A), "CAPÍTULO I" + quebra + "DAS DISPOSIÇÕES GERAIS" (família B, 2011/lei_11117), "TÍTULO I – DO QUADRO PRÓPRIO..." + "CAPÍTULO ÚNICO - DISPOSIÇÕES PRELIMINARES" na linha seguinte do mesmo `<p>` (1973/lei_2397) e "SEÇÃO I – DAS APOSENTADORIAS / SUBSEÇÃO I – DA APOSENTADORIA COMUM" dentro de texto citado entre aspas (2020/lei_13193).
- Também aparecem títulos de seção **dentro de texto alterador citado** ("Seção V-A Da Secretaria Municipal de Planejamento", 1999/lei_7836) e títulos alterados com nota ("TÍTULO XII ... (Redação alterada pelo art. 12 da Lei nº 13.403...)", 2011/lei_11468).
- **95% das leis não têm nenhum nível acima de artigo.** Mediana de 3 artigos e 252 palavras por lei. Distribuição do número de artigos: 1 → 32 leis, 2 → 54, 3 → 46, 4 → 33, 5–9 → 40, 10 ou mais → 28, 0 → 4.

### 4.3 Artigos
Rótulos encontrados (contagem de ocorrências / leis):

| Forma | Ocorrências | Leis | Exemplo |
|---|---:|---:|---|
| `Art. 1º` … `Art. 9º` (ordinal) | ~1.150 | 233 | todas |
| `Art. 10.` em diante (cardinal com ponto) | ~1.550 | 23 | 1948/lei_42, 1953/lei_219, 2011/lei_11468 |
| `Art. 10` sem ponto | 13 | 4 | 1960/lei_607, 1997/lei_7305, 2020/lei_13193, 2026/lei_14065 |
| `Art. 1°` (sinal de grau) | 24 | 6 | 1991/lei_4911, 2014/lei_12232, 2026/lei_14065 |
| `ART. 1º` (maiúsculo) | 2 | 1 | 1981/lei_3419 |
| `Art 1º` (sem ponto) | 1 | 1 | 1999/lei_7836 |
| `Art.1º` (sem espaço) | 1 | 1 | 2019/lei_12913 |
| `Art. 1º -` / `Art. 2º -Esta` (hífen depois do rótulo) | 9 | 5 | 1985/lei_3848, 1990/lei_4406, 2013/lei_11902 |
| `Art.. 25.` (ponto duplo) | 1 | 1 | 1963/lei_788 |
| `Art. º7` (ordinal invertido) | 1 | 1 | 1961/lei_706 |
| `Art. 5º-A`, `Art. 10-A.`, `Art. 4º-A` a `4º-D`, `Art. 9º-B` | 21 | 6 | 1999/lei_7836, 2007/lei_10433, 2011/lei_11468, 2014/lei_11999, 2020/lei_13193, 2021/lei_13333 |
| `Art. 1o` (letra "o") | **0** | — | não apareceu |

- Na família A o rótulo está em `<b>`, às vezes com espaço dentro da tag (`<b>Art. 3º </b>Todo`, 1952/lei_155) ou sem espaço depois (`<b>Art. 2º</b>As`, 1954/lei_257). Na família C às vezes o numeral é partido: `<strong>I</strong>I` (`I**I –**`, 2025/lei_13990).
- Numeração com problemas: 1962/lei_787 tem **dois "Art. 2º"**. 1953/lei_219 vai até o Art. 704 com saltos (661 rótulos para 659 números distintos). 2011/lei_11468 vai até o Art. 399, e o segundo bloco promulgado volta ao Art. 39 (ver 6).
- A cláusula final evolui assim: "Revogam-se as disposições em contrário." como artigo próprio (1948–1960, ex.: 1948/lei_22); "Esta Lei entrará em vigor na data de sua publicação, revogadas as disposições em contrário." (1950–2000); "Esta lei entra em vigor..." com "lei" minúsculo (predominante de 2000 a 2019); "Esta Lei entra em vigor..." de novo maiúsculo a partir de 2023.

### 4.4 Parágrafos
- `§ 1º` (971 ocorrências / 48 leis); `Parágrafo único.` (435 / 78 leis).
- Variantes: `§1º` (1997/lei_7305), `§ 1°` (2006/lei_10134), `§ 1.` (1973/lei_2212), `§ 1 ` (2022/lei_13440), `Parágrafo Único` (1953/lei_219, 1973/lei_2212), `Parágrafo único -` e `Parágrafo Único –` (1963/lei_788, 1990/lei_4406), `Parágrafos único.` (erro de digitação, 1976/lei_2660).
- Na família B o parágrafo às vezes vem **colado no meio da linha** do artigo anterior ("...7,50m. Parágrafo único. Na porção...", 1994/lei_5857; também em 1997/lei_7305, 2003/lei_9180, 2011/lei_11468).

### 4.5 Incisos, alíneas e itens
- **Incisos romanos**:
  - com hífen `I -` (192 ocorrências / 19 leis, 1952–2026; ex.: 1952/lei_155 `<b>I -</b>`);
  - com travessão `I –` (1.154 / 38 leis, a partir de 1973/lei_2212 e predominante depois de 1990);
  - com ponto `I.` (2005/lei_9897);
  - sem marcador no texto (2026/lei_14065), porque estão em `<ol style="list-style-type:upper-roman"><li>` e o numeral só existe no CSS. O PDF mostra "I. II. III.".
- **Alíneas**: `a)` (477 / 32 leis), `a -`/`c -` (1990/lei_4406), `a.` (2022/lei_13440). Às vezes alíneas aparecem como subitens de parágrafo sem inciso (1954/lei_257 § 1º a)…c)).
- **Itens numéricos**:
  - `01. RUA ...` (denominações, ex.: 1981/lei_3333, 1983/lei_3611, 1985/lei_3848, 1989/lei_4405);
  - `1 - Diretoria` (1957/lei_413);
  - `1) JARDIM INTERLAGOS` (1984/lei_3654);
  - `1.` a `66.` (lista de serviços em 1969/lei_1636);
  - `1.`, `2.`, `3.` abaixo da alínea c) (2011/lei_11117);
  - `1º -`, `2º -` em tabela (1968/lei_1447).
- Também aparecem "ALTERAÇÃO PRIMEIRA … SÉTIMA" como divisão de artigo alterador (1968/lei_1447, 1969/lei_1636).

### 4.6 Como distinguir no HTML
- **Família A**: cada dispositivo começa numa linha e o rótulo fica em `<b>`. Títulos e capítulos ficam em `<p class="TitVioleta">`, às vezes entre comentários `<!--TitI-->…<!--TitF-->`. O texto citado em alterações fica em `p.recuado` ou `p.recuadospan`.
- **Família B**: não há marcação estrutural. É preciso segmentar por regex no texto (`^Art\.`, `^§`, `^[IVX]+ [-–]`, `^[a-z]\)`), juntando antes as linhas quebradas pelas `<br>` duras.
- **Família C**: rótulos em `<strong>`, um dispositivo por `<br>`.
- **Família D (2022/lei_13440)**: as classes CSS já trazem a semântica.

---

## 5. Elementos especiais

| Elemento | Leis | Detalhes e exemplos |
|---|---:|---|
| **Tabelas HTML** (`<table>` com conteúdo) | 31 (98 tabelas) | 1948–2023. Orçamentos com 140–441 linhas (1949/lei_71, 1955/lei_290, 1962/lei_787), créditos (1954/lei_239, 1964/lei_921, 1966/lei_1167, 1972/lei_2211), tabelas de tributos (1948/lei_42 "TABELA Nº 1…4-C", 1997/lei_7305 "TABELA I…V"), vencimentos (1962/lei_747, 1971/lei_2027, 1973/lei_2397), cargos (1980/lei_3184, 2018/lei_12827, 2023/lei_13547). As tabelas antigas têm cabeçalho multilinha (Código Local/Geral). |
| `<table>` **vazia** no topo do corpo | 20 | 1981/lei_3333, 2000/lei_8040, quase todas de 2018 a 2024 (ex.: 2018/lei_12739, 2024/lei_13825) |
| **Tabelas em texto** com pontilhado | 3 | "...para conjunto habitacional............60.000,00" (1979/lei_2963; também 1987/lei_3940, 2003/lei_9180) |
| **Anexos** com rótulo | 6 | 1971/lei_2027 ("ANEXO I…IV"), 1973/lei_2397, 1980/lei_3184 ("ANEXO"), 2018/lei_12827 ("ANEXO I", "ANEXO II"), 2023/lei_13547 ("ANEXO ÚNICO / Quadro de Equivalência"), 2026/lei_14065 (lista de Anexos I–VII) |
| Anexos **fora do HTML** | 3 | 2022/lei_13440 "* Ver anexos em pdf."; 2026/lei_14065 "ANEXOS (Clique aqui)" com link para cloudsoftcam.com.br; 1974/lei_2519 "nos termos da minuta de convênio, integrante da presente Lei", sem a minuta |
| Posição do anexo | — | depois de Ref. e do alerta (1997/lei_7305, 1980/lei_3184, 2018/lei_12827); antes do fecho (1971/lei_2027); entre a assinatura e o Ref. (2023/lei_13547); depois do fecho e sem assinatura (1948/lei_42, 1969/lei_1636 "LISTA DE SERVIÇOS...") |
| **Imagens, mapas, plantas** | **0** | só GIFs espaçadores. Plantas e croquis são citados mas não incluídos: "conforme consta da planta inclusa" (1948/lei_1), "Indicação aproximada, em croqui, do sistema viário" (2007/lei_10284), "Memorial Descritivo nº 138/90-SUOV" (1991/lei_4624) |
| **Memoriais descritivos** (divisas, rumos, m²) | 44 com m²; 15 com "divisas e confrontações"; 12 com rumos | "com as seguintes divisas e confrontações: ao Norte, com a Rua Pará, numa extensão de 36,45mts" (1948/lei_22); "A NORDESTE, com o Lote 67, no rumo NW 45º26 SE, com 15,01m" (1991/lei_4624); "no rumo NE 71º35’52” SW" (2022/lei_13546). Matrícula/registro: "Matrícula n° 63.446 do 2° Oficio do Registro de Imóveis" (2014/lei_12232). Unidades: `ms²` (1948), `m2`, `m²`, "metros quadrados", "alqueires paulistas" (2007/lei_10284), "mts" |
| **Moeda** | — | **Cr$** em 46 leis (1948–1993); **NCr$** em 7 (1967–1970, ex.: 1967/lei_1229); **Cz$** em 3 (1987/lei_3940, 1989/lei_4309, 1990/lei_4406); **NCz$** em 2 (1989–1990); **R$** em 12 (1999/lei_7836 → 2025); **C$** em 1 (2025/lei_516, digitação). Valores sem centavos ou com vírgula estranha: "Cr$ 2.270.922.000," (1964/lei_964), "Cr$ 184.483, 760" (1966/lei_1167). Indexadores: U.F.L. (1988/lei_4055), UFIRs (2000/lei_8040), salário mínimo (1968/lei_1447, 2015/lei_12233), IPCA-E (2025/lei_14064). |
| **VETADO** | 10 leis, 63 ocorrências | "(vetado)" no meio da frase (1975/lei_2598); "b) (vetado);" (1977/lei_2865); "01. (Vetado)." (1985/lei_3848); "Art. 2º Vetado." (2025/lei_516); "II – VETADO" e "Art. 7º VETADO" (2013/lei_11902); "~~§ 1º VETADO.~~" seguido do texto restaurado e "(Dispositivo com promulgação oriunda da rejeição de veto parcial)" (2011/lei_11117) |
| **Texto riscado** | 17 leis, 177 `<s>` | **só `<s>`**: não há `<strike>`, `<del>` nem `text-decoration:line-through`. É a redação anterior mantida no texto consolidado, seguida da nova (1959/lei_528, 1987/lei_3940, 1988/lei_4055, 1989/lei_4405, 1990/lei_4406 com 3 camadas sucessivas do caput do Art. 1º, 1996/lei_6706, 2007/lei_10433, 2011/lei_11468, 2015/lei_12233, 2018/lei_12827). Há `<s>` que abrangem vários dispositivos e `<s>` vazios ou partidos (2015/lei_12233). |
| **Notas de alteração** | — | "(Redação dada pelo Art. 1º da Lei nº 4.382, de 14 de dezembro de 1989)" e variantes "Redação do caput dada/alterada", "Redação mantida", "Redação acrescida" (14 leis, 215 ocorrências); "(Incluído pelo...)", "(Acrescido pelo...)", "(Acrescida pelo...)" (10 leis); "(REVOGADO pelo art. 2° da Lei nº 12.555...)", "(Revogado pelo art. 1º da Lei nº 13.135...)" em dispositivos (ex.: 2015/lei_12233, 2018/lei_12827); "(Excluído pelo Art. 1º Lei nº 2.284...)" e "(Renumerado de Art. 97 para Art. 95 pelo...)" (1973/lei_2212); "(Vide Art. 1º da Lei nº 589...)" (1957/lei_413), "(Vide Decreto nº 553...)" (2011/lei_11117), "Vide alterações feitas pela Lei nº 14.147" (2026/lei_14065). Quase sempre ficam logo depois de um `<a href>` para a lei alteradora. |
| **Erratas** | 3 | só como nota no rodapé: "Errata publicada no Jornal Oficial nº 726, de 23.2.2006 - fls. 24." (2005/lei_9897); 2019/lei_12998; 2022/lei_13334 |
| **Republicação / retificação** | 0 | não apareceu |
| Comentários HTML | 14 leis | marcadores de digitação (`<!--L22_48it01-->`, `<!--TitI-->`/`<!--TitF-->`); `<!--Falta restante da Lei-->` (1963/lei_788); CSS do LibreOffice dentro de comentário (2015/lei_12386, 2017/lei_12485); **índice analítico de 65 KB dentro de um comentário** com tags próprias (1953/lei_219) |

---

## 6. Fecho e rodapé

### 6.1 Local e data

| Fórmula | Leis | Período | Exemplo |
|---|---:|---|---|
| "EDIFÍCIO DA PREFEITURA MUNICIPAL DE LONDRINA, aos 20 de maio de 1948." | 26 | 1948–1968 (+2025/lei_516) | 1948/lei_22 |
| "PAÇO MUNICIPAL, aos 15 de dezembro de 1950." | 16 | 1950–1956 | 1950/lei_106 |
| "EDIFÍCIO DA PREFEITURA DO MUNICÍPIO DE LONDRINA, aos ..." | 51 | 1957–1990 | 1973/lei_2212 |
| "SALA DAS SESSÕES, em ..." / "SALA DE SESSÕES" / "Sala das sessões" | 18 | 1948–2009 | promulgações pela Câmara e orçamentos assinados pela Comissão (1948/lei_42, 1955/lei_290, 1961/lei_706, 1962/lei_787) |
| "EDIFÍCIO DA CÂMARA MUNICIPAL DE LONDRINA, ..." | 2 | 1978, 1988 | 1978/lei_2866, 1988/lei_4055 |
| "Londrina, 10 de fevereiro de 1949." | 122 | família B desde 1949; família A desde 1990/lei_4515; único formato a partir de 1990 | 2015/lei_12310 |

Formatos de data: "aos 1º de Dezembro de 1949", "aos 31 de agosto de 1.951" (ponto no ano, 1951–1983), "em 6/janeiro/1969" (1969/lei_1448), "aos 26 de setembro de 1967:" (dois-pontos), "28 de agosto de l997" (letra "l" no ano, 1997/lei_7123), "12 de JANEIRO de 2018" (2018/lei_12650), "Londrina, de 21 de julho de 2006" (2006/lei_10016), "26 de dezembro e 1967" (1968/lei_1291), "SALA DAS SESSÕES EM 13 DE DEZEMBRO DE 1948." (1948/lei_42).

### 6.2 Signatários
- **Prefeito**:
  - "Prefeito Municipal" (1948 em diante);
  - "Prefeito do Município" (a partir de 1976/1986);
  - "Prefeito Municipal em exercício" (1979/lei_2963, 1980/lei_3246);
  - "Prefeito do Município (em exercício)" (2008/lei_10434);
  - "(em substituição)" (2023/lei_13637);
  - "a) Antonio Fernandes Sobrinho" com "a)" de "assinado" (1956/lei_326; "a) Sadao Masuko" em 1963/lei_833);
  - "= Dalton Fonseca Paranaguá =" (1970–1972);
  - nome sublinhado com "_____" (até 1988).
- **Co-signatários**:
  - "SECRETÁRIO" (1952–1968);
  - "RESP. PELA SECRETARIA" e "respondendo p/ Secretaria Geral" (1960–1968);
  - "Chefe de Gabinete" (1969–1974);
  - "Secretário Geral" (1975–1997);
  - "Secretário de Governo" (1998–2022);
  - "Secretário Municipal de Governo" (2022/lei_13546);
  - mais secretários setoriais conforme a matéria: Administração, Fazenda, Planejamento, Urbanismo/Obras, Saúde, Educação, "Diretor-Presidente do IPPUL" (1996/lei_6941, 2003/lei_9028), "Diretora Superintendente da Autarquia Municipal de Saúde" (2004/lei_9333), "PROCURADOR JUDICIAL" (1987/lei_3940; 7 signatários).
- **A partir de 2023 só o Prefeito assina** (2023/lei_13727, 2024/lei_13728, família C). Em 2022/lei_13440 a assinatura vem em linha: "Marcelo Belinati Martins, Prefeito do Município."
- **Câmara**: "PRESIDENTE DA CÂMARA" + "1º SECRETÁRIO" (+ "2º Secretário" em 1981/lei_3419); "Presidente (em exercício)" (2009/lei_10668); "Vereador Rony dos Santos Alves / Presidente" (2013/lei_11902).
- Casos estranhos:
  - "A COMISSÃO: ____" sem nomes (1961/lei_706);
  - "A COMISSÃO DE JUSTIÇA, LEGISLAÇÃO E REDAÇÃO. / Pres. / rel." (1955/lei_290);
  - "COMISSÃO" (1948/lei_42);
  - "ALCYONE V. PIMPÃO F. ALVES / Vereador" (1971/lei_2027);
  - "Presidente / Secretário" sem nomes (1962/lei_787);
  - sem nenhuma assinatura (1985/lei_3848, 1954/lei_239 apenas com o nome).
- **Assinaturas em colunas embaralhadas (família B)**: os nomes de dois ou três signatários e os cargos ficam intercalados ou quebrados no meio. Exemplos: "ANTONIO CASEMIRO / BELINATI / ADEMAR / TROIANO / ARIOVALDO FERRAZ / ARRUDA / Prefeito Municipal / Secretário / Geral / Secretário de Administração" (1981/lei_3333) e "LUIZ EDUARDO CHEIDA JOSÉ CARLOS DE OLIVEIRA ARRUDA WILSON BATTINI / Prefeito do Município Secretário Geral Secretário de Administração" (1993/lei_5675).

### 6.3 Bloco "Ref." (processo legislativo)
- Presença por década: 1940: 1/6 · 1950: 2/30 · 1960: 3/30 · 1970: 20/30 · 1980: 29/30 · 1990: 30/30 · 2000: 30/30 · 2010: 30/30 · 2020: 19/21. Faltam 2022/lei_13440 e 2025/lei_516; a partir de 1974 falta também em 1985/lei_3848.
- Formas do rótulo:
  - "Ref." (135 leis);
  - "Ref.:" (26);
  - "Ref. Projeto de Lei nº 105/73" na mesma linha (1974/lei_2398);
  - "Ref. Projeto Lei 141/77" (1978/lei_2866);
  - "Ref.: ao Projeto de Lei nº 162/65" (1966/lei_1070, a primeira ocorrência na família A);
  - "Ref.:" em itálico com `font-size:11px` (família C).
- Projeto de origem:
  - "Projeto de Lei nº 55/49." (ano com 2 ou 4 dígitos);
  - "Projeto de Lei nº 69/74 - A.L." (1974/lei_2459);
  - "PROJETO DE LEI Nº 187/2025" e "PROJETO DE LEI N.º 275/2026" em maiúsculas (família C);
  - "Substitutivo nº 1/2025 ao Projeto de Lei nº 268/2025" (2026/lei_14065).
- Autoria:
  - "Autor: Executivo Municipal" ou "Autor: EXECUTIVO MUNICIPAL" (1974–1992, 22 leis);
  - "Autores:" (1988/lei_4055, 1992/lei_5129);
  - "Autoria:" (117 leis, de 1949 a 2026): "Autoria: Executivo Municipal.", "Autoria: vereador Célio Guergoletto", "Autoria: Vereadora Sandra...", listas de 8 a 14 vereadores (2007/lei_10135, 2020/lei_12999), "Autoria: Mesa Executiva (Rony dos Santos Alves, ...)" (2013/lei_11998), "Mesa Diretora (...)" (2024/lei_13921);
  - "Autor: Mesa Executiva da Câmara Municipal de Londrina" (1980/lei_3122).
- "Apoio: <vereadores>" (8 leis, 2015–2023; ex.: 2015/lei_12386, 2021/lei_13333).
- Tramitação:
  - "Aprovado na forma do Substitutivo nº 01/87" (32 leis, a partir de 1987/lei_3997), às vezes "..., de autoria da Comissão de Justiça, Legislação e Redação" ou "..., do próprio autor";
  - "Aprovado com Emenda Aditiva nº 01/86" (1987/lei_3940; é a primeira);
  - Emendas Supressiva e Modificativa (1991/lei_4767, 1991/lei_4911);
  - "Aprovado com as Emendas nºs 1, 4, 6, 7(exceto inciso II), 12, 14 e 15" (2011/lei_11117);
  - uma lista de mais de 100 emendas e subemendas (2011/lei_11468);
  - "Aprovado na forma da redação final, proposta pela Comissão..." (2001/lei_8506).
- Promulgação: "Promulgação oriunda de sanção tácita." e "...da rejeição de veto total / parcial / integral." (seção 3).

### 6.4 Alerta de publicação ("não substitui")
- Frase: "Este texto não substitui o publicado no ...". Aparece em 112 leis, de 1949 a 2024, na família B e em algumas da família A.
- Variante antiga: "Este texto não substitui a publicação..." (1949/lei_43).
- Veículo citado:
  - "jornal Folha de Londrina, em 26.9.1957." (29 leis, 1957–1997);
  - "Jornal de Londrina, Edição nº 1.883" (4 leis, 1995–1996, sempre junto com a Folha);
  - "Jornal Oficial, edição nº 70, Caderno Único, Fl. 1, em 22.1.1998" (84 leis, a partir de 1997/lei_6942).
- Em 2011/lei_11468 a forma é "Promulgação: Jornal Oficial, edição nº 1809...".
- A família C (2024+) não tem esse alerta. A publicação passa para o campo `jom` do JSON ("Publicado na Edição N.º 5378 (20ª Página) do Jornal Oficial do Município (JOM) em 31/12/2024 páginas 20 e 21").
- A data do alerta pode ser bem posterior à da lei: 1976/lei_2721 (lei de 31/12/1976, publicada em 12.3.1977); 1982/lei_3420 (lei de 1º/4/1982, publicada em "7.5.1983"); 1991/lei_4911 (dez/1991, publicada em 21/03/1992).

### 6.5 Leis com dois documentos no mesmo HTML (veto parcial derrubado)
2011/lei_11117, 2011/lei_11468 e 2013/lei_11902 seguem esta ordem:

1. lei sancionada (preâmbulo, artigos com "VETADO", fecho "Londrina, 10 de janeiro de 2011.", Ref. e alerta);
2. **segundo preâmbulo** "PROMULGO ... OS SEGUINTES DISPOSITIVOS DA LEI MUNICIPAL Nº ..." (ausente em 2013/lei_11902, que começa direto com "“...");
3. os dispositivos promulgados entre aspas, com "..." e "...”";
4. **segundo fecho** com outra data ("Londrina, 2 de março de 2011." / "Presidente");
5. segundo Ref. com "Promulgação oriunda da rejeição de veto parcial." e segundo alerta.

Os mesmos números de artigo aparecem duas vezes.

---

## 7. Citações a outras normas

Inventário por regex no texto sem tags (as contagens incluem os "Projeto de Lei nº x/aa" do Ref.):

| Forma | Ocorrências | Exemplo |
|---|---:|---|
| `Lei nº 2.576 de 31 de outubro de 1975` (ponto de milhar + data por extenso, com ou sem vírgula) | 514 | 1953/lei_219, 2016/lei_12387 |
| `Lei nº 9/1967`, `Lei nº 55/49` (ano com 4 ou 2 dígitos) | 95 + 84 | 1967/lei_1168, 1949/lei_43 |
| `Lei nº 1.111` (sem data) | 34 | 1953/lei_219 |
| `Lei nº 20, de 9 de abril de 1948` (número < 1000) | 26 | 1948/lei_42 |
| `Lei Complementar nº 101/2000`, `Lei Complementar Federal nº 101/2000` | 28 | 2004/lei_9518, 2022/lei_13440 |
| `Lei Federal nº 4.320, de 17 de março de 1964` e `Lei Federal nº 4.320/64` | 24 + 13 | 1967/lei_1229, 1972/lei_2028 |
| `Lei Municipal nº 3.645, de 19 de dezembro de 1983` | 15 | 1984/lei_3654 |
| `Lei Municipal nº 1.185, de 25.04.1967` (data numérica) | 11 | 1953/lei_219 |
| `Lei nº 1151/66`, `Lei nº 5669/1993`, `Lei nº 2945` (sem ponto de milhar) | 8 + 2 + 6 | 1968/lei_1447, 2007/lei_10433, 1979/lei_2963 |
| `Lei 1.153/66`, `Lei 360`, `Lei Federal 11.977, de ...` (sem "nº") | ~10 | 1968/lei_1447, 1957/lei_361, 2009/lei_10850 |
| `Lei 4.117, de 27/08/62` | 1 | 1963/lei_833 |
| `Leis nºs 963/64, 1816/71 e 1859/71`, `Leis nºs 3.652, de ... e ...` (plural) | — | 1975/lei_2598, 1993/lei_5675 |
| `Decreto-Lei nº 137/46`, `Decreto-Lei nº 137, de 23 de novembro de 1946`, `Decreto-Lei Federal nº 8.079` | 4 | 1948/lei_1, 1953/lei_219 |
| `Decreto nº 553, de 10 de maio de 2019`, `Decreto nº 1.264 de 22 de outubro de 2026`, `Decreto nº 36` | 15 | 2011/lei_11117, 2026/lei_14065 |
| `Lei Estadual nº 863, de 20 de junho de 1952` | 3 (só em 1953/lei_219) | |
| `Resolução nº 20 de 13 de dezembro de 1958`, `Resolução 11/70`, "Resoluções nºs 109/2009 do Conselho Nacional..." | — | 1958/lei_476, 1971/lei_2027, 2015/lei_12233 |
| Constituição | 10 leis | "artigo 15, parágrafo 2º, da Constituição Federal" (1960/lei_529); "Constituição Federal de 1946" (1967/lei_1290); "art. 165, inciso II, § 2º, da Constituição Federal, de 5 de outubro de 1988" (2022/lei_13440); "Emenda Constitucional nº 103/2019" (2020/lei_13193) |
| Lei Orgânica | | "art. 100, da Lei Orgânica do Município de Londrina, de 5 de abril de 1990" (2022/lei_13440); "Lei Orgânica dos Municípios" e "do Município" nos preâmbulos |
| Códigos por nome | 26 leis | "(Código de Obras)", "Código Tributário Nacional", "Código de Defesa do Consumidor", "Código Civil", "Código Nacional de Trânsito", "Código Ambiental do Município (Lei nº 11.471, de 05 de janeiro de 2012)" |
| Normas técnicas | | "(ABNT) NBR 9050 em seus itens 7.4.3..." (2012/lei_11806) |
| Dispositivo citado | | "item 318, do artigo 1º, da Lei nº 1.154", "Seção IV, do Capítulo III, do Título II, da Lei nº 281", "nos incisos II e III, § 1º, do artigo 43, da Lei Federal nº 4.320/64" |

Leis citadas pelo nome popular: "Lei de Zoneamento de Londrina" (1985/lei_3810), "Lei de Responsabilidade Fiscal - LRF", "Estatuto da Criança e do Adolescente", "Plano Diretor".

**Hiperlinks**: 158 leis têm `<a href>` para a norma citada. Tipos de destino:
- `https://www.cml.pr.gov.br/proposicoes/Leis/<ano>/<n>/0/<id>` (607);
- `.../proposicoes/<n>/0/1/0/<id>` e `.../proposicoes/pesquisa/<n>/<n>/0/<id>` (notas de revogação);
- `https://www.cloudsoftcam.com.br/...pdf` (decretos e anexos);
- `https://portal.londrina.pr.gov.br/images/stories/jornalOficial/Jornal-5780-Assinado.pdf`;
- `L0219.htm#` dentro do comentário de 1953/lei_219.

A âncora às vezes envolve só "artigo 186", ou o link fica antes da citação ("O[link] Anexo I"). Também há âncoras sem `href` (`<a name="art1">`).

---

## 8. Tipologia por conteúdo (237 leis)

Classificação manual a partir da súmula e do texto, com um tipo principal por lei.

| # | Tipo | Nº | Leis | Onde está o conteúdo relevante |
|---|---|---:|---|---|
| 01 | Denominação ou percurso de logradouro/próprio público (ruas, praças, rodovia, escola, posto, bosque; reconhecimento de bairro) | 37 | 1949/lei_43, 1953/lei_197, 1957/lei_387, 1958/lei_414, 1959/lei_477, 1959/lei_502, 1967/lei_1168, 1974/lei_2459, 1975/lei_2559, 1976/lei_2721, 1979/lei_3042, 1980/lei_3246, 1981/lei_3333, 1982/lei_3568, 1983/lei_3611, 1983/lei_3653, 1985/lei_3771, 1985/lei_3848, 1988/lei_4210, 1989/lei_4405, 1993/lei_5511, 1994/lei_5676, 1994/lei_6038, 1996/lei_6706, 2002/lei_8855, 2002/lei_9027, 2003/lei_9332, 2004/lei_9702, 2008/lei_10667, 2009/lei_10759, 2012/lei_11638, 2014/lei_12116, 2017/lei_12567, 2018/lei_12739, 2019/lei_12828, 2021/lei_13263, 2024/lei_13825 | **Art. 1º** (e listas numeradas "01. RUA X - Atual Rua 01. Entre..."): o nome do homenageado (muitas vezes em MAIÚSCULAS), a denominação provisória ("atual Rua \"11\""), o loteamento ou conjunto, a gleba e o lote, os limites ("que se inicia na confluência com... e termina...", "tendo de um lado a Quadra 6 e de outro..."). Quase nunca há biografia; a súmula costuma repetir nome e local. |
| 02 | Crédito adicional / transferência orçamentária | 22 | 1954/lei_239, 1955/lei_274, 1958/lei_445, 1960/lei_568, 1961/lei_608, 1964/lei_921, 1965/lei_1017, 1966/lei_1167, 1967/lei_1229, 1970/lei_1637, 1970/lei_1721, 1971/lei_1917, 1972/lei_2119, 1972/lei_2211, 1973/lei_2305, 1978/lei_2914, 1978/lei_2962, 1979/lei_2963, 1989/lei_4309, 1990/lei_4623, 2003/lei_9180, 2019/lei_12913 | Art. 1º (valor, finalidade, beneficiário) e **tabelas de dotações** (códigos, órgão, valor); Art. 2º (fonte: anulação de dotação, excesso de arrecadação, art. 43 da Lei 4.320/64) |
| 03 | Orçamento anual / LDO / PPA | 8 | 1949/lei_71, 1955/lei_290, 1960/lei_607, 1961/lei_706, 1962/lei_787, 1964/lei_964, 2022/lei_13440, 2026/lei_14065 | totais nos Art. 1º e 2º e **tabelas enormes** de receita e despesa. Nas LDO/PPA recentes o essencial está em **anexos PDF externos** |
| 04 | Imóvel público (desafetação, doação, permuta, concessão ou permissão de uso, aquisição, arrendamento, prorrogação de prazo) | 28 | 1948/lei_1, 1948/lei_22, 1951/lei_135, 1952/lei_136, 1964/lei_878, 1970/lei_1806, 1972/lei_2028, 1982/lei_3494, 1984/lei_3654, 1988/lei_4132, 1990/lei_4515, 1991/lei_4624, 1993/lei_5675, 1995/lei_6469, 1997/lei_6942, 1998/lei_7306, 1998/lei_7469, 1999/lei_7633, 2001/lei_8506, 2001/lei_8682, 2006/lei_9898, 2007/lei_10433, 2014/lei_12232, 2017/lei_12649, 2022/lei_13546, 2023/lei_13637, 2024/lei_13728, 2025/lei_14064 | Art. 1º (descrição do imóvel: área em m², lote, quadra, loteamento, gleba, matrícula, **memorial de divisas e rumos**); Art. 2º (beneficiário: entidade ou empresa e finalidade); artigos de encargos, prazo e reversão (formulaicos) |
| 05 | Utilidade pública | 14 | 1969/lei_1542, 1971/lei_1807, 1977/lei_2722, 1977/lei_2793, 1982/lei_3420, 1986/lei_3894, 1986/lei_3939, 2000/lei_8185, 2002/lei_8683, 2008/lei_10434, 2010/lei_10851, 2010/lei_10983, 2012/lei_11469, 2016/lei_12436 | Art. 1º (nome da entidade + "com sede e foro neste Município"); a partir de 2000, Parágrafo único e Art. 2º (I–III) são **texto-padrão idêntico** |
| 06 | Título honorífico / honraria | 6 | 1976/lei_2599, 1986/lei_3849, 1987/lei_4054, 2007/lei_10135, 2008/lei_10551, 2015/lei_12386 | Art. 1º (nome e às vezes cargo: "DD. Secretário da Saúde Pública do Estado"); o Ref. (autoria e apoio) |
| 07 | Alteração ou revogação de lei | 28 | 1950/lei_72, 1956/lei_291, 1957/lei_361, 1963/lei_877, 1965/lei_965, 1965/lei_1069, 1966/lei_1119, 1969/lei_1448, 1975/lei_2598, 1977/lei_2865, 1981/lei_3247, 1984/lei_3712, 1984/lei_3770, 1991/lei_4767, 1995/lei_6039, 1997/lei_7123, 1998/lei_7632, 1999/lei_7836, 2000/lei_8040, 2000/lei_8330, 2005/lei_9800, 2009/lei_10850, 2014/lei_11999, 2016/lei_12387, 2016/lei_12484, 2017/lei_12485, 2019/lei_12998, 2021/lei_13333 | a súmula identifica a lei alterada e o tema; o **texto novo entre aspas** (com "...", ". . .", "[...]" ou "omissis") traz o conteúdo material; "onde se lê ... leia-se" (1966/lei_1119, 1984/lei_3770) |
| 08 | Zoneamento / perímetro urbano / uso do solo | 17 | 1963/lei_788, 1978/lei_2866, 1979/lei_3121, 1981/lei_3419, 1985/lei_3810, 1992/lei_5129, 1992/lei_5346, 1994/lei_5857, 1995/lei_6254, 1996/lei_6941, 2001/lei_8331, 2003/lei_9028, 2005/lei_9703, 2006/lei_10016, 2007/lei_10284, 2010/lei_11116, 2013/lei_11902 | Art. 1º (via ou trecho + zona: "ZC-4", "Quadro XII – Zona Comercial Seis (ZC-6) do Anexo 2 da Lei nº 7.485"); memoriais de perímetro (1995/lei_6254, 2010/lei_11116) |
| 09 | Institui data, semana, campanha ou programa | 6 | 1968/lei_1369, 1996/lei_6470, 2011/lei_11292, 2023/lei_13727, 2025/lei_13990, 2026/lei_14300 | Art. 1º (nome e data) e artigos de objetivos (incisos) |
| 10 | Código, estatuto ou regulamento geral / nova política | 11 | 1948/lei_42, 1952/lei_155, 1953/lei_219, 1971/lei_2027, 1973/lei_2212, 1973/lei_2397, 1991/lei_4911, 2011/lei_11117, 2011/lei_11468, 2015/lei_12233, 2020/lei_13193 | distribuído por títulos e capítulos; os nomes dos capítulos e seções são o melhor resumo |
| 11 | Pessoal: cargos, vencimentos, abono, planos de cargos, subsídios | 16 | 1949/lei_57, 1950/lei_106, 1954/lei_257, 1961/lei_657, 1962/lei_707, 1962/lei_747, 1980/lei_3184, 1983/lei_3569, 1989/lei_4212, 1992/lei_4912, 2006/lei_10134, 2013/lei_11998, 2018/lei_12650, 2018/lei_12827, 2023/lei_13547, 2024/lei_13921 | artigos e **tabelas de cargos e valores** (anexos) |
| 12 | Autorizações diversas ao Executivo (venda de bens móveis, convênio, empréstimo, concessão de serviço, auxílio financeiro, criação de órgão) | 20 | 1950/lei_89, 1951/lei_107, 1954/lei_220, 1955/lei_258, 1956/lei_326, 1957/lei_413, 1960/lei_529, 1963/lei_833, 1966/lei_1070, 1967/lei_1290, 1968/lei_1291, 1974/lei_2398, 1974/lei_2519, 1975/lei_2520, 1980/lei_3122, 1987/lei_3997, 1993/lei_5347, 2004/lei_9518, 2013/lei_11807, 2022/lei_13334 | Art. 1º (objeto: "15 (quinze) muares velhos", "Trator Rodoviário", "convênio com o DER-PR", valor e parte) |
| 13 | Regulação / obrigações a particulares / outros | 15 | 1959/lei_528, 1976/lei_2660, 1987/lei_3940, 1988/lei_4055, 1990/lei_4406, 2004/lei_9333, 2005/lei_9897, 2009/lei_10668, 2012/lei_11806, 2015/lei_12310, 2020/lei_12999, 2020/lei_13096, 2021/lei_13194, 2025/lei_516, 2026/lei_14182 | Art. 1º (obrigação ou proibição) e artigos de sanções (multas em R$, prazos) |
| 14 | Tributário (taxa, isenção, contribuição, alteração do Código Tributário) | 6 | 1951/lei_121, 1952/lei_174, 1968/lei_1447, 1969/lei_1636, 1997/lei_7305, 1999/lei_8039 | fato gerador, alíquotas e **tabelas** |
| 00 | Inexistente / sem texto | 3 | 1953/lei_175, 1956/lei_360, 1958/lei_476 | só a súmula |

Leis com mais de um tipo (registradas no tipo principal):
- 1961/lei_657 cria cargos e abre crédito;
- 1999/lei_7836 altera a estrutura administrativa e abre crédito;
- 1972/lei_2028 trata de pagamento de desapropriação e abre crédito;
- 1984/lei_3654 e 2017/lei_12649 alteram leis que tratam de imóveis;
- 1953/lei_197 cria escola e recebe terreno em doação;
- 2019/lei_12828 estende avenida e revoga item de lei de denominação.

---

## 9. Evolução por época (linha do tempo)

| Quando | Mudança | Evidência |
|---|---|---|
| 1948–2024 (até 13825) | título "LEI ORDINÁRIA Nº n/aaaa" gerado pelo portal, sem data | 1948/lei_1 … 2024/lei_13825 |
| 1948–1993 | família A (Carta/RP, `<b>Art.</b>`) predominante | seção 4.1 |
| 1948–1960 | "Revogam-se as disposições em contrário." como artigo autônomo | 1948/lei_22, 1957/lei_413 |
| 1948–1988 | linha "______" para assinatura | 1948/lei_1, 1988/lei_4055 |
| 1949– | família B esporádica, já com Ref./Autoria e alerta da Folha de Londrina | 1949/lei_43, 1957/lei_387 |
| 1950–1956 | fecho "PAÇO MUNICIPAL" | 1950/lei_89 |
| 1955–1969 | promulgação pelo Presidente da Câmara "DECRETOU E EU, PRESIDENTE, PROMULGO" | 1955/lei_258 |
| 1957–1990 | fecho "EDIFÍCIO DA PREFEITURA DO MUNICÍPIO DE LONDRINA, aos ..." | 1957/lei_413, 1990/lei_4406 |
| 1966 | primeiro "Ref." na família A | 1966/lei_1070 |
| 1967–1970 | NCr$ | 1967/lei_1229 |
| 1969–1974 | co-signatário "Chefe de Gabinete"; 1970–72 "= Nome =" | 1970/lei_1721 |
| 1973– | inciso com travessão "–" (passa a predominar depois de 1990) | 1973/lei_2212 |
| 1974–1992 | Ref. regular na família A com "Autor:" | 1974/lei_2519 |
| 1975–1997 | "Secretário Geral" | 1975/lei_2520 |
| 1976/1986 | "PREFEITO DO MUNICÍPIO" no preâmbulo e no fecho | 1976/lei_2599, 1986/lei_3939 |
| 1978–2021 | promulgação "NOS TERMOS DO § ... DA LEI ORGÂNICA" (66 §2º → 82 §4º → 31 §7º / §3º) | seção 3 |
| 1987– | "Aprovado na forma do Substitutivo / com Emenda" | 1987/lei_3940, 1987/lei_3997 |
| 1987–1990 | Cz$ / NCz$; 1990–1993 Cr$ de novo; 1999– R$ | 1987/lei_3940, 1989/lei_4309, 1993/lei_5347, 1999/lei_7836 |
| 1990 | fecho "Londrina, dd de mês de aaaa." também na família A | 1990/lei_4515 |
| jan/1994 | **DECRETOU → APROVOU** nas leis sancionadas | 1994/lei_5676 |
| 1995–2024 | só família B | — |
| 1995–1997 | alerta cita Folha de Londrina + Jornal de Londrina | 1995/lei_6469 |
| 1997– | alerta "Jornal Oficial, edição nº ..." | 1997/lei_6942 |
| 1997 / 2005– | "Promulgação oriunda de sanção tácita / rejeição de veto ..." | 1997/lei_7123, 2005/lei_9897 |
| 1998–2022 | "Secretário de Governo" | 1998/lei_7306 |
| 2000– | texto-padrão de utilidade pública com Parágrafo único e Art. 2º I–III | 2000/lei_8185 |
| 2015– | "Apoio:" no Ref. | 2015/lei_12386 |
| 2018–2024 | `<table>` vazia no topo | 2018/lei_12739 |
| 2023– | só o Prefeito assina | 2023/lei_13727 |
| 31/12/2024– | família C: título "LEI N.º n, DE d DE MÊS DE aaaa", rótulo SÚMULA, **PDF assinado** (`url_pdf`), metadados `autoria_portal`/`situacao`/`jom`, sem o alerta "não substitui" | 2024/lei_13921 |

---

## 10. Qualidade e armadilhas para o parser

**Estrutura HTML**
1. **Título duplicado** (`<title>` + `<p>`) em 237/237 e segundo `<title>` em 1960/lei_607 e 2022/lei_13440.
2. **CSS como texto**: `<style>` dentro do corpo (1960/lei_607, 2022/lei_13440). Quem extrai com `get_text` sem descartar `<style>` recebe "body { font-family: sans-serif; }…". Há CSS também dentro de comentários (2015/lei_12386, 2017/lei_12485).
3. **Comentário gigante**: índice analítico de 65 KB com tags internas dentro de `<!-- -->` em 1953/lei_219. Com o comentário são 52,7 mil palavras; sem ele, 42,6 mil. Um strip por regex `<[^>]+>` vaza o índice. Só um parser de verdade o descarta.
4. **Comentários de controle**: `<!--L136_51_it02-->`, `<!--TitI-->`, `<!--Falta restante da Lei-->`.
5. **Espaçadores e nbsp**: GIFs de 1×1 px (223); caracteres U+00A0 literais em 183 leis (até 5.583 em 1953/lei_219). Entidades HTML quase não aparecem (`&amp;` em 2002/lei_9027 e 2016/lei_12436; `&gt;` em 1971/lei_2027).
6. **Quebras duras** no meio de frases e nomes (família B): "VILA INDUSTRIAL-\nSABBI" (1969/lei_1542). É preciso juntar as linhas antes de segmentar.
7. **Palavras coladas ao remover links**: "pela[link]Lei" vira "pelaLei" (9 leis; ex.: 2024/lei_13921, 1993/lei_5675, 1980/lei_3184). O PDF confirma que o original tem espaço.
8. **Numerais de incisos fora do texto** (`<ol>` com CSS) em 2026/lei_14065.
9. **Negrito que parte o rótulo** ("I**I –**", 2025/lei_13990; "**Art. 1º **Adere"); negrito e sublinhado em células de tabela (`**__**__`, 1961/lei_706).

**Conteúdo consolidado**
10. **Redações antigas riscadas** (`<s>`, 17 leis) convivem com a vigente. Em 1990/lei_4406 há três redações do caput do Art. 1º. Se o objetivo é o texto vigente, é preciso remover o `<s>` (e o rótulo que estiver dentro dele). Se é o histórico, é preciso mantê-lo, separado.
11. **Notas editoriais misturadas ao texto**: "(Redação dada pelo...)", "(REVOGADO pelo...)", "(Vide ...)", "(Dispositivo com promulgação oriunda...)", inclusive em negrito. Também a nota de revogação da lei inteira na súmula (32 leis).
12. **Texto de outra lei entre aspas**: os artigos citados ("Art. 186. O imposto...", 1968/lei_1447; "Art. 22." em 1996/lei_6941; "SEÇÃO I..." em 2020/lei_13193) não são artigos da lei que os cita. Há também elipses "...", ". . .", "[...]" e "omissis".
13. **Dois documentos num HTML** (veto parcial): 2011/lei_11117, 2011/lei_11468, 2013/lei_11902.
14. **Assinaturas embaralhadas** em colunas (família B), por exemplo "DÉLIO N. CÉZAR / PAULO TURCI / LÚCIO TEDESCO MARCHESE / Prefeito do / Município / Secretário Geral / ..." (1986/lei_3894), e "Prefeito do MunicípioSecretário de Governo" colado (2011/lei_11292).

**Leis vazias, truncadas ou incompletas**
15. 1953/lei_175: só título e súmula (20 palavras). 1956/lei_360: "(Encadernada em separado)." 1958/lei_476: "LEI INEXISTENTE".
16. 1963/lei_788 está **truncada** ("SALA DAS SESSÕES, em 10 de janeiro de 1963." + `<!--Falta restante da Lei-->`).
17. 2019/lei_12913 anuncia "nos Programas de Trabalhos a seguir especificados:" e "conforme a seguir especificado:", mas **as tabelas não existem** no HTML.
18. Anexos só em PDF externo (2022/lei_13440, 2026/lei_14065) e minuta não incluída (1974/lei_2519).
19. Sem assinatura: 1985/lei_3848, 1948/lei_42 (só "COMISSÃO"), 1961/lei_706 e 1962/lei_787 (cargos sem nome).

**Divergências de número e data**
20. Ano do título ≠ pasta: 1968/lei_1291 (`/1967`), 2025/lei_516 (lei de 1959), 2026/lei_14065 (de 22/12/2025).
21. Data do fecho ≠ `data_portal`: antes de cerca de 1990 é comum diferir em dias. Casos grandes:
    - 1948/lei_1 (fecho 21/01/1948 × portal 13/08/1948);
    - 1952/lei_155 (fecho 19/09 × portal 16/08);
    - 1961/lei_608 (fecho 15/12/1960 × portal 14/03/1961);
    - 1967/lei_1168 (fecho "9 de março de 1968", publicada em 16.3.1967);
    - 1981/lei_3419 (fecho 23/11/1981 × portal 07/02/1981);
    - 1985/lei_3848 (fecho 03/01/1986 × portal 03/01/1985);
    - 1992/lei_5346 (fecho 30/12 × portal 09/12).

    De 2019 a 2024 o `data_portal` tem hora "05:00" (artefato de fuso). Em 2024+ é a data e hora de cadastro.
22. Datas internas erradas: 1961/lei_706 (exercício "1.963"), 1955/lei_290 (Art. 7º "31 de dezembro de 1.963" num orçamento de 1956), 1962/lei_787 ("Cr$ 691.800,00" no Art. 1º contra 691.800.000,00 nas tabelas; dois "Art. 2º").
23. `numero` no JSON sem o sufixo da letra (502-B → "502"; 516-A → "516").

**Erros de digitação no texto oficial** (o exemplo "ROJETO DE LEI" **não apareceu** nesta amostra)
24. Nomes:
    - "José Tiago Camargo do **Município**" no lugar de "do Amaral" (2026/lei_14300). O erro está também no PDF oficial, mas o carimbo digital diz "José Tiago Camargo do Amaral".
    - "ROMINDO GLAROIN" por ROMILDO GIAROLA (1961/lei_608).
    - "ANTONIO BERNANDES SOBRINHO" e "MARIO CONTA" por Fernandes Sobrinho e Mário Cunha (2025/lei_516).
    - "WALDMIR BELINATII" (1991/lei_4911).
    - "Institututo" (súmula de 1956/lei_326).
    - "Municípío" (2011/lei_11292).
    - "entra em vigorar" (2016/lei_12484).
    - "Lei Municipal nº.669/93", que deveria ser 5.669 (2007/lei_10433).
    - "datas nºs l8, l9" com letra "l" (súmula de 1948/lei_22).
    - "l953"/"l950" em súmulas (1953/lei_175 e 1949/lei_71).
    - "(dispoõe" (súmula de 1975/lei_2598).
25. Perda de codificação: "SECRET?RIO" (1959/lei_502), "??Designação de Despesa" (1962/lei_787), "?CORTADO" (1955/lei_290).
26. Ortografia histórica (antes de 1971): "êste", "sôbre", "vigôr", "Govêrno", "creada", "Secção", "ítem", "agôsto". Afeta qualquer busca lexical.

**Metadados**
27. `autoria_portal` = "Poder Executivo" nas 6 leis de 2024+, **mesmo quando o Ref. traz autoria de vereador ou da Mesa** (2025/lei_13990, 2026/lei_14182, 2026/lei_14300, 2024/lei_13921). O campo indica quem remeteu ou publicou, não quem propôs.
28. `jom` de 2026/lei_14065 contém uma nota "Vide Decreto nº 1363..." em vez da publicação. `url_pdf_gerado` está ausente (3) ou nulo (3) exatamente nas 6 leis com `url_pdf`. `autoria_portal`, `situacao` e `jom` estão vazios nas outras 231.

**PDF × HTML (6 leis)**
29. O PDF (mPDF ou iText) acrescenta em cada página: o cabeçalho "Prefeitura do Município de Londrina / Estado do Paraná", o carimbo "Documento assinado digitalmente por <nome> (054.***.***-84) [em dd/mm/aaaa hh:mm]" **intercalado no meio do texto** e o rodapé "Para verificar sua autenticidade, acesse: https://www.cml.pr.gov.br/cer e informe o código: 2611111025141B2321". Hifenização partida ("dar- se-á").
30. A semelhança de palavras entre HTML e PDF fica entre 0,86 e 0,94. Fora o boilerplate, o texto normativo é idêntico, com estas exceções:
    - HTML de 2026/lei_14065: tem as notas "Vide ..." posteriores, que não estão no PDF, e não tem os numerais dos incisos;
    - PDF de 2026/lei_14065: tem o erro "20259" onde o HTML diz "2029";
    - HTML: palavras coladas nos links ("pelaLei", "daLei").

    Nenhum PDF contém os anexos (o de 14065 tem 5 páginas, sem anexos).

---

## 11. Lacunas da amostra (o que não apareceu e onde procurar)

| Estrutura ausente ou rara | Por que provavelmente existe | Onde procurar |
|---|---|---|
| **Lei Complementar municipal** | o coletor tem o campo `complementar` e o portal distingue o tipo; 0 de 237 | filtrar "complementar" no portal (qualquer ano) |
| **Cruzeiro real (CR$)** e URV | a sequência de moedas da amostra pula de Cr$ (1993/lei_5347) para R$ (1999/lei_7836) | leis de ago/1993 a jun/1994 (por exemplo, números ~5.500–5.800) |
| Moedas de 1995–1998 em R$ | só há R$ a partir de 1999 | créditos e taxas de 1995–1998 |
| **Mapas, plantas, croquis, imagens** | citados ("planta inclusa", 1948/lei_1; "croqui", 2007/lei_10284; "Memorial Descritivo nº 138/90-SUOV", 1991/lei_4624), mas nunca embutidos | leis de loteamento, perímetro e zoneamento (Lei 7.484/1998 Anexo Único, citada em 2010/lei_11116; Lei 12.236/2015, citada nas revogações de 2003/lei_9028 e 2005/lei_9703) |
| **Anexos em PDF** (LDO, PPA, LOA) | "Ver anexos em pdf" (2022/lei_13440) e link "Clique aqui" (2026/lei_14065) | baixar os PDFs dos anexos dessas duas leis e de uma LOA recente (não há nenhuma LOA após 1964 na amostra) |
| **LIVRO e PARTE** fora de 1953/lei_219; **SUBSEÇÃO** fora de 2011/lei_11468 e 2020/lei_13193 | só aparecem em códigos | Código Tributário (Lei 1.151/1966, citada por 1968/lei_1447 e 1969/lei_1636); Código de Posturas (Lei 2.576/1975, que revoga 1953/lei_219; Lei 13.903/2024, que revoga 2011/lei_11468); Código de Obras (Lei 281/1955 e Lei 11.381/2011); Código Ambiental (Lei 11.471/2012); Estatuto dos Servidores (Lei 4.928/1992); Plano Diretor (Lei 7.482/1998) |
| **Leis de denominação "em massa"** (centenas de itens) | 1983/lei_3611 altera o "item 318, do artigo 1º, da Lei nº 1.154 de 13 de dezembro de 1966"; 1983/lei_3653, o item 186 da Lei 880/1964; 2019/lei_12828, o item 291 da Lei 2.046/1972 | Leis 880/1964, 1.154/1966, 2.046/1972 |
| Zoneamento clássico com quadros | citado: Lei 3.706/1984 (1985/lei_3810, 1994/lei_5857, 1996/lei_6941), Lei 7.485/1998 (2001/lei_8331, 2007/lei_10284) | Leis 3.706/1984, 7.485/1998, 12.236/2015 |
| **Itens numéricos dentro de alíneas** e quarto nível | só 2011/lei_11117 ("1. 2. 3." sob a alínea c) | códigos e LDOs |
| **Art. "1o"** (letra o), artigos com letra no texto original (não inseridos) | 0 casos de "1o" | provável em transcrições dos anos 1990–2000; buscar por regex no acervo |
| **Republicação / retificação** como texto | só notas de errata (3 leis) | leis com "Errata publicada", buscar as edições do JOM |
| Texto vetado com razões do veto / mensagem | só "VETADO" | a mensagem de veto fica no processo legislativo, não em `/Leis` |
| Mais de 3 leis no formato novo (família C) | só 6 amostras (2024–2026) | baixar, por exemplo, 20–30 leis de 2025–2026 para estabilizar a "gramática" nova (rótulo SÚMULA, Ref. em `<em>`, `<ol>`) |
| Leis estaduais e federais citadas com frequência | "Lei Estadual" só em 1953/lei_219 | leis de convênio e de trânsito |
| Leis de 1948 anteriores a 1/1948 / Decretos-Lei de 1946–47 | 1948/lei_1 revoga o "Decreto-Lei nº 137/46" | não são "Leis" no portal; fora do escopo |

---

## 12. Viés da amostra

- **Mês**: a regra 1ª/meio/última, com a listagem ordenada da mais recente para a mais antiga, concentra a amostra nas pontas do ano. Pelo `data_portal`: **dezembro 74**, **janeiro 47**, setembro 32, agosto 19, fevereiro 15, julho 14, março 13, junho 6, outubro 6, abril 4, maio 3, novembro 4. A ordenação aproximada por data dentro de cada ano dá:
  - "1ª da listagem" (mais recente): dezembro em 74 de 79 anos;
  - "última" (mais antiga): janeiro em 46;
  - "meio": quase sempre julho a setembro.
- **Tipo**: as pontas do ano favorecem:
  - leis de fim de exercício: orçamentos e créditos suplementares de dezembro (6 dos 8 orçamentos são de dezembro: 1949/lei_71, 1955/lei_290, 1960/lei_607, 1961/lei_706, 1962/lei_787, 1964/lei_964), reajustes e abonos de Natal (1950/lei_106, 1954/lei_257);
  - leis sancionadas no recesso (fim de dezembro e começo de janeiro), muitas vezes promulgadas pela Câmara por sanção tácita ou veto derrubado (2011/lei_11468 de 29/12, 2012/lei_11469 de 04/01, 2012/lei_11806 de 27/12).

  O "meio" puxa denominações e leis rotineiras (18 das 37 denominações e 15 dos 22 créditos estão no meio).
- **Artefatos de cadastro**: a "1ª/meio/última" de uma listagem pode ser uma lei antiga cadastrada tarde (2025/lei_516 é de 1959) ou de outro ano (1968/lei_1291 = 1291/1967; 2026/lei_14065 de dezembro de 2025). Isso infla a variedade de formatos dentro de um mesmo ano.
- **Peso por época**: 3 leis por ano dá o mesmo peso a 1948 (poucas leis por ano) e a 2020 (centenas por ano), o que superrepresenta as leis antigas. A família C (o formato atual) tem só 6 exemplos.
- **Peso por tamanho**: pelo acaso da posição, 4 códigos ou estatutos grandes entraram (1948/lei_42, 1953/lei_219, 2011/lei_11468, 2020/lei_13193) e concentram cerca de 60% das palavras da amostra. Qualquer estatística por palavra fica dominada por eles.

---

## 13. Gramática consolidada de uma lei de Londrina

Notação: `?` = opcional, `*` = zero ou mais, `+` = um ou mais, `|` = alternativa. Entre colchetes, a época em que o bloco aparece.

```
DOCUMENTO_HTML :=
    TITULO_TAG                              -- <title>, sempre
    TITULO_VISIVEL                          -- <p 18px>, sempre, idêntico ao <title>
    SUMULA                                  -- <div padding-left:45%>, sempre (pode ser só "LEI INEXISTENTE")
    CORPO?                                  -- ausente em 1953/lei_175; "(Encadernada em separado)" em 1956/lei_360
    NOTAS_POS_PUBLICACAO*                   -- "Vide Decreto ...", links [2026]

TITULO := "LEI ORDINÁRIA Nº " NUM ("- " LETRA)? "/" ANO                       [1948 → 2024/13825]
        | "LEI N.º " NUM ("- " LETRA)? ", DE " DIA " DE " MÊS " DE " ANO      [31/12/2024 →]

SUMULA := ("SÚMULA" | "Súmula") " "? ":" )?  [só 2024+]
          EMENTA                              -- verbo no presente: Autoriza|Dá|Altera|Abre|Denomina|Dispõe|Desafeta|Declara|Institui|Cria|Confere|Orça|Introduz|Inclui|Enquadra|...
          ("(Substitutivo nº n/aa)")?         [1993–2007]
          NOTA_REVOGACAO_LEI*                 -- "(REVOGADA pelo Art. x da Lei nº ... de ...)" com link

CORPO :=
    TABELA_VAZIA?                                         [2018–2024; 1981/3333; 2000/8040]
    PREAMBULO?                                            -- ausente em 1953/lei_219
    (EPIGRAFE_ESTRUTURAL | DISPOSITIVO | TABELA | TEXTO_CITADO)+
    ANEXOS?                                               -- pode vir aqui (antes do fecho) [1971/2027]
    FECHO?
    ASSINATURAS?
    ANEXOS?                                               -- ou aqui [2023/13547]
    REF?                                                  [esporádico 1949–1973; regular 1974 →]
    ALERTA_PUBLICACAO?                                    [1949 → 2024; ausente em 2024/13921+]
    ANEXOS?                                               -- ou aqui [1980/3184, 1997/7305, 2018/12827]
    BLOCO_PROMULGACAO_PARCIAL?                            -- veto parcial derrubado [2011, 2013]

PREAMBULO := "A CÂMARA MUNICIPAL DE LONDRINA, ESTADO DO PARANÁ, "
             ( "DECRETOU"  [1948–1993]  | "APROVOU" [1994 →; exceções 1962/787, 2013/11902, 2013/11998] )
             " E EU, "
             ( ("PREFEITO MUNICIPAL" | "PREFEITO DO MUNICÍPIO" [1976/1986 →] | "PREFEITO DO MUNICÍPIO DE LONDRINA") ", SANCIONO"
             | "PRESIDENTE, PROMULGO" (", NOS TERMOS DO § n DO ARTIGO m DA LEI ORGÂNICA ...")? [1955 →] )
             " A SEGUINTE LEI" (" Nº n")? ":"

EPIGRAFE_ESTRUTURAL := ("PARTE" | "LIVRO" | "TÍTULO" | "CAPÍTULO" | "SEÇÃO"|"SECÇÃO" | "SUBSEÇÃO") (ROMANO|"ÚNICO"|"ÚNICA") (" - " NOME | <quebra> NOME)?
                     | "DISPOSIÇÕES FINAIS|GERAIS|PRELIMINARES|TRANSITÓRIAS"
                       -- presente em ~5% das leis; ordem PARTE > LIVRO > TÍTULO > CAPÍTULO > SEÇÃO > SUBSEÇÃO

DISPOSITIVO := ARTIGO
ARTIGO      := ROTULO_ART CAPUT NOTA* (PARAGRAFO | INCISO | ALINEA | ITEM)*
ROTULO_ART  := "Art. " (ORDINAL[1–9]"º|°" | CARDINAL[10+] "."?) ("-" LETRA)? (" -")?
               -- variantes: "ART.", "Art 1º", "Art.1º", "Art.. 25.", "Art. º7"
PARAGRAFO   := ("§ " n "º|°|." | "Parágrafo único." | "Parágrafo Único -") TEXTO NOTA* (INCISO|ALINEA)*
INCISO      := ROMANO (" - " | " – " | ". ") TEXTO (ALINEA)*   -- ou <ol><li> sem numeral [2026/14065]
ALINEA      := LETRA (")" | " -" | ".") TEXTO (ITEM)*
ITEM        := NUM ("." | " -" | ")") TEXTO                    -- listas de ruas "01. RUA X - Atual Rua 1 ..."
NOTA        := "(Redação dada|alterada|mantida|acrescida pelo ...)" | "(Incluído|Acrescido pelo ...)"
             | "(Revogado pelo ...)" | "(Vide ...)" | "(Excluído|Renumerado ...)"
             | "(Dispositivo com promulgação oriunda da rejeição de veto parcial)"
             | "(vetado)" | "VETADO"
VERSAO_ANTIGA := <s> DISPOSITIVO </s>                          -- texto consolidado [17 leis, 1953–2018]
TEXTO_CITADO := "“" (ROTULO_ART|EPIGRAFE...) ... ("..." | ". . ." | "[...]" | "omissis") "”"   -- nova redação de outra lei
              | "ALTERAÇÃO PRIMEIRA - ..." [1968–1969] | "onde se lê ... leia-se ..."
TABELA      := <table> ... | linhas com pontilhado "......valor"

FECHO := ( "EDIFÍCIO DA PREFEITURA MUNICIPAL DE LONDRINA, aos"   [1948–1968]
         | "PAÇO MUNICIPAL, aos"                                 [1950–1956]
         | "EDIFÍCIO DA PREFEITURA DO MUNICÍPIO DE LONDRINA, aos" [1957–1990]
         | "SALA DAS SESSÕES, em" | "EDIFÍCIO DA CÂMARA MUNICIPAL" -- promulgação pela Câmara ou Comissão
         | "Londrina,"                                           [1949 → ; único a partir de 1990] )
         DATA_EXTENSO "."

ASSINATURAS := ( "______"? NOME CARGO )+                       -- Prefeito [+ Secretário/Chefe de Gabinete/Sec. Geral/Sec. de Governo + setoriais]
                                                               -- ou Presidente da Câmara [+ 1º/2º Secretário] | "A COMISSÃO"
                                                               -- família B: nomes e cargos intercalados em colunas
                                                               -- 2023+: só o Prefeito

REF := ("Ref." | "Ref.:") 
       ( "Substitutivo nº n/aaaa ao " )? "Projeto de Lei nº n/aa(aa)" (" - A.L.")?
       ( ("Autor:" [1974–1992] | "Autores:" | "Autoria:") AUTORES )?
       ( "Apoio:" VEREADORES )?                                  [2015 →]
       ( "Aprovado na forma do Substitutivo nº ..." | "Aprovado com (a|as) Emenda(s) ..." )?   [1987 →]
       ( "Promulgação oriunda de sanção tácita." | "Promulgação oriunda da rejeição de veto total|parcial|integral." )?

ALERTA_PUBLICACAO := "Este texto não substitui o publicado no "
                     ( "jornal Folha de Londrina, em d.m.aaaa" [1957–1997]
                     | "... e Jornal de Londrina, Edição nº ..." [1995–1996]
                     | "Jornal Oficial, edição nº n, Caderno Único, fls. x, em d/m/aaaa" [1997 →] )
                     ( " Errata publicada no Jornal Oficial nº ..." )?

BLOCO_PROMULGACAO_PARCIAL := PREAMBULO("...PROMULGO ... OS SEGUINTES DISPOSITIVOS DA LEI MUNICIPAL Nº ...")?
                             TEXTO_CITADO+ FECHO ASSINATURAS(Presidente) REF ALERTA_PUBLICACAO

ANEXOS := ( ("ANEXO" ROMANO? | "ANEXO ÚNICO" | "TABELA Nº n" | "LISTA DE ...") TITULO_ANEXO? TABELA+ )+
        | "* Ver anexos em pdf." | "ANEXOS (Clique aqui)"   -- conteúdo fora do HTML
```

Blocos sempre presentes: título (duas vezes) e súmula. Quase sempre presentes: preâmbulo, artigos, cláusula de vigência e fecho com data. Opcionais e dependentes da época: assinaturas, Ref., alerta, anexos, notas de consolidação, versões riscadas e o segundo bloco de promulgação.
