# Projeto OCR Leis — PaddleOCR em documentos jurídicos brasileiros

Ambiente de experimentação para medir a precisão do **PaddleOCR 3.x** na transcrição de
páginas digitalizadas de leis brasileiras, comparando a imagem original com versões
pré-processadas (OpenCV) e calculando **CER** e **WER** contra transcrições de referência
revisadas por humanos.

---

## 1. Objetivo

- Converter imagens de páginas de leis em texto, preservando conteúdo e estrutura
  (artigos, parágrafos, incisos, alíneas, numeração de leis, datas, acentuação).
- Descobrir se o pré-processamento de imagem melhora o reconhecimento.
- Medir objetivamente a qualidade (CER/WER) quando houver uma transcrição de referência.
- **Nunca** corrigir, resumir ou reescrever o texto reconhecido: o resultado gravado é
  exatamente a saída do modelo. Trechos duvidosos são apenas **sinalizados** para revisão humana.

## 2. Como o PaddleOCR funciona

O PaddleOCR 3.x (API `PaddleOCR(...).predict(imagem)`) executa um pipeline em etapas:

1. **(Opcional) Classificação de orientação do documento** e **"unwarping"** (desentortar
   páginas fotografadas). Ambos ficam **desativados** aqui: as páginas já estão na
   orientação correta e o unwarping pode deformar o texto.
2. **Detecção de texto** (`PP-OCRv5_server_det`): localiza cada linha/trecho de texto e
   devolve um polígono (caixa) por trecho.
3. **(Opcional) Orientação da linha** — desativada (linhas horizontais).
4. **Reconhecimento** (`latin_PP-OCRv5_mobile_rec`, escolhido por `lang="pt"`): lê cada
   trecho recortado e devolve o texto e uma **confiança** entre 0 e 1. O alfabeto latino
   cobre os caracteres do português (á, ã, ç, õ, º, ª, §...).

O resultado bruto contém, por trecho: `rec_texts`, `rec_scores`, `rec_polys`/`rec_boxes`.
A ordem de leitura **não** é garantida pelo modelo — por isso o projeto a reconstrói
(ver arquitetura). Os modelos são baixados uma única vez para `~/.paddlex/official_models/`;
depois disso o OCR roda **offline**, sem APIs externas.

## 3. Arquitetura

```text
Projeto_OCR_Leis/
├── imagens/                       # ENTRADA: uma pasta por documento
│   ├── 01_exposicao_motivos_1983/imagens_do_documento/
│   └── 02_estatuto_idoso/imagens_do_documento/
├── referencias/                   # transcrições humanas (opcional) para CER/WER
│   ├── 01_exposicao_motivos_1983/  pagina_001.txt, ...
│   └── 02_estatuto_idoso/
├── resultados/                    # SAÍDA (gerada)
├── scripts/
│   ├── ocr.py                     # localização de páginas, PaddleOCR, ordem de leitura, exportação
│   ├── preprocessamento.py        # transformações OpenCV e perfis
│   ├── avaliacao.py               # CER, WER, elementos jurídicos, relatórios
│   └── metadados.py               # texto do OCR -> metadados jurídicos estruturados (JSON)
├── main.py                        # linha de comando
├── pipeline_passo_a_passo.ipynb   # notebook que mostra cada etapa do pipeline
├── requirements.txt
└── README.md
```

Fluxo de `main.py`:

```text
imagens/<documento>/imagens_do_documento/*.{jpg,png,pdf,...}
   │  ocr.listar_paginas()      → ordem natural dos nomes; PDFs rasterizados a 300 DPI (PyMuPDF)
   ▼
preprocessamento.aplicar_perfil()  → "original" não altera a imagem
   ▼
MotorOCR.reconhecer()              → PaddleOCR 3.x, lang=pt, device=cpu
   ▼
ocr.ordenar_leitura()              → agrupa trechos em linhas; detecta 2 colunas
   ▼
ocr.sinais_de_ambiguidade() + limiar de confiança → lista "revisao_humana"
   ▼
resultados/<documento>[/preprocessado_<perfil>]/pagina_NNN.{txt,json}, documento_completo.txt
   ▼
avaliacao.gerar_relatorio()        → relatorio.json / relatorio.md (+ comparativo_perfis)
```

**Ordem de leitura.** Os trechos são agrupados em linhas pela sobreposição vertical e
ordenados da esquerda para a direita. Se houver um "corredor" vertical vazio no meio da
página (tolerando poucos elementos que o atravessam, como um cabeçalho centralizado ou o
número da página), ela é tratada como duas colunas (lê-se a coluna esquerda inteira e depois a
direita); títulos que atravessam as duas colunas são mantidos na posição correta. Use
`--uma-coluna` para desativar.

**Revisão humana.** Um trecho entra em `revisao_humana` (no JSON de cada página) quando:
- a confiança do modelo é menor que `--limiar-confianca` (padrão 0,80); ou
- há mistura suspeita de letras e dígitos (ex.: `0UTUBRO`, `Art.l0` — confusões O/0, l/1, S/5),
  exceto ordinais e numerações legítimas (`1º`, `nº`, `10.741`); ou
- aparece o símbolo de grau `°` onde normalmente se usa o ordinal `º` (`Art. 1°`).

O texto **não é alterado**; o sinal só indica onde conferir.

## 4. Requisitos

- Linux (testado no Arch Linux), CPU x86-64. **Não requer GPU.**
- Python **3.11** (o PaddlePaddle não publica pacotes para todas as versões mais novas).
- ~2 GB livres (bibliotecas + modelos) e acesso à internet **apenas na primeira execução**
  (download dos modelos).
- Bibliotecas (ver `requirements.txt`): `paddlepaddle==3.2.2`, `paddleocr` 3.x,
  `opencv-contrib-python`, `pillow`, `pymupdf`.

> **Por que PaddlePaddle 3.2.2?** Na série 3.3.x o backend oneDNN da CPU falha com
> `ConvertPirAttribute2RuntimeAttribute` ao executar os modelos PP-OCRv5.

## 5. Criar o ambiente virtual (Arch Linux)

Opção A — `uv` (recomendada; baixa o Python 3.11 automaticamente se necessário):

```bash
sudo pacman -S --needed uv
cd Projeto_OCR_Leis
uv venv --python 3.11 .venv
```

Opção B — `venv` padrão (requer Python 3.11 instalado, ex.: AUR `python311` ou `pyenv`):

```bash
cd Projeto_OCR_Leis
python3.11 -m venv .venv
```

## 6. Instalar as dependências

```bash
# com uv
uv pip install --python .venv/bin/python -r requirements.txt

# ou com pip
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Verifique:

```bash
.venv/bin/python -c "import paddle, paddleocr, cv2; print(paddle.__version__, paddleocr.__version__, cv2.__version__)"
```

Se aparecer erro de importação do `cv2`, provavelmente há dois pacotes OpenCV instalados.
Corrija com:

```bash
uv pip uninstall --python .venv/bin/python opencv-python opencv-python-headless
uv pip install --python .venv/bin/python --reinstall opencv-contrib-python==4.10.0.84
```

## 7. Adicionar imagens

Coloque os arquivos em `imagens/<documento>/imagens_do_documento/`.

- Formatos: `.jpg .jpeg .png .bmp .tif .tiff .webp .pdf` (outros arquivos, como `.txt`, são ignorados).
- A ordem das páginas segue a **ordenação natural** dos nomes (`pagina_2` antes de `pagina_10`).
  Recomenda-se `pagina_001.png`, `pagina_002.png`...
- Um PDF é dividido em páginas automaticamente (300 DPI).
- Para um **novo documento**, basta criar `imagens/03_meu_documento/imagens_do_documento/`.

### Situação das imagens dos documentos de teste

| Documento | Fonte | Situação |
|---|---|---|
| `02_estatuto_idoso` | institutodelongevidade.org | **3 imagens baixadas** automaticamente da própria matéria (capa e duas páginas internas do Estatuto). |
| `01_exposicao_motivos_1983` | pt.scribd.com | **Não baixado.** O Scribd responde com um desafio anti-robô ("Client Challenge") e exige conta para download; o bloqueio não foi contornado. Ver `imagens/01_exposicao_motivos_1983/imagens_do_documento/LEIA-ME.txt`. |

Para adicionar o documento 1 manualmente: acesse o link do Scribd com sua conta, baixe o
PDF (se a sua conta permitir) ou salve cada página como imagem, copie para
`imagens/01_exposicao_motivos_1983/imagens_do_documento/` e rode
`.venv/bin/python main.py --documento 01_exposicao_motivos_1983`.

## 8. Executar o OCR

```bash
cd Projeto_OCR_Leis

# Todos os documentos, imagem original (sem pré-processamento)
.venv/bin/python main.py

# Apenas um documento
.venv/bin/python main.py --documento 02_estatuto_idoso

# Ajustar o limiar de confiança para revisão humana
.venv/bin/python main.py --limiar-confianca 0.9

# Desativar a detecção de duas colunas
.venv/bin/python main.py --uma-coluna
```

Os avisos do PaddlePaddle (`No ccache found`, etc.) são inofensivos. A primeira execução
baixa os modelos; as seguintes usam o cache em `~/.paddlex/`.

### Notebook passo a passo

`pipeline_passo_a_passo.ipynb` executa as funções dos scripts etapa por etapa e mostra o
resultado intermediário de cada uma: páginas encontradas, cada transformação de
pré-processamento, as caixas detectadas pelo PaddleOCR coloridas pela confiança, a ordem de
leitura reconstruída, o texto final, os trechos marcados para revisão humana, a gravação dos
resultados, a avaliação e a extração dos metadados jurídicos. O documento, a página e o perfil são definidos na célula
"Parâmetros do experimento".

```bash
.venv/bin/jupyter lab pipeline_passo_a_passo.ipynb
```

## 9. Onde encontrar os resultados

```text
resultados/<documento>/
├── pagina_001.txt              # texto reconhecido, na ordem de leitura reconstruída
├── pagina_001.json             # resultado estruturado da página (ver abaixo)
├── ...
├── documento_completo.txt      # todas as páginas, em ordem, com separadores
├── relatorio.json              # métricas por página + resumo
├── relatorio.md                # o mesmo relatório em tabela
├── comparativo_perfis.json/.md # (quando há mais de um perfil executado)
├── metadados.json              # (gerado pelo notebook ou por scripts/metadados.py)
└── preprocessado_<perfil>/     # mesma estrutura, para cada perfil de pré-processamento
```

Conteúdo de `pagina_NNN.json`:

- `documento`, `pagina`, `imagem_origem`, `perfil_preprocessamento`, `etapas_preprocessamento`;
- `status` (`ok` ou `erro`), `erro` e `detalhes_erro` (traceback, se houver);
- `tempo_preprocessamento_s`, `tempo_ocr_s`, `dimensoes_imagem`;
- `quantidade_caracteres`, `quantidade_palavras`, `quantidade_fragmentos`,
  `confianca_media`, `confianca_minima`;
- `texto` (o mesmo do `.txt`) e `layout` (número de colunas, divisória);
- `linhas_ordenadas`: cada linha com seus trechos (texto, confiança, caixa, coluna);
- `necessita_revisao_humana` e `revisao_humana`: trechos sinalizados, linha no TXT e motivos;
- `resultado_bruto_paddleocr`: saída original do modelo (`rec_texts`, `rec_scores`, polígonos...);
- `versoes`, `parametros_paddleocr` e `limiar_confianca_revisao`, para reprodutibilidade.

Um erro em uma página é registrado no JSON e no relatório, e a execução continua.

### Metadados jurídicos (`metadados.json`)

`scripts/metadados.py` transforma o texto reconhecido em metadados estruturados:

- **norma**: tipo, número, data, apelido e ementa, com todas as ocorrências encontradas e as
  divergências entre elas;
- **estrutura**: títulos, capítulos e seções;
- **artigos**: caput, parágrafos, incisos e alíneas em hierarquia, com a localização
  (título/capítulo), a página e a linha de cada um;
- **leis e datas citadas**, notas de rodapé, número de página impresso e textos não classificados;
- **pendências**: algarismo romano inválido em inciso (`Il`, `VIl`), mês ilegível (`0UTUBRO`),
  `°` no lugar de `º`, artigo de 1 a 9 sem ordinal (LC 95/1998) etc.;
- **rastreabilidade**: perfil, versões e dados de cada página.

Os textos continuam **brutos**. Campos `*_normalizado` (ex.: `data_normalizada: "2003-10-01"`)
só são preenchidos quando o texto bruto é inequívoco; senão ficam `null` e o motivo vai para
`pendencias`. A classificação usa padrões de texto (regex) e depende de a ordem de leitura
estar correta.

```bash
# pelo notebook (seção 8) ou diretamente:
.venv/bin/python -c "from pathlib import Path; from scripts import metadados; print(metadados.salvar_metadados(Path('resultados/02_estatuto_idoso'))[1])"
```

## 10. Testes comparativos (pré-processamento)

Transformações disponíveis em `scripts/preprocessamento.py`: escala de cinza, aumento de
contraste (CLAHE), redução de ruído (Non-Local Means), binarização adaptativa gaussiana,
correção de inclinação (perfil de projeção, ±10°) e redimensionamento (largura entre
1600 e 3000 px). Elas são combinadas em perfis:

```bash
.venv/bin/python main.py --listar-perfis
```

| Perfil | Etapas |
|---|---|
| `original` | nenhuma |
| `ampliado` | redimensionar |
| `cinza_contraste` | redimensionar → cinza → contraste |
| `sem_ruido` | redimensionar → cinza → ruído |
| `binarizado` | redimensionar → cinza → ruído → binarizar |
| `deskew` | redimensionar → inclinação |
| `completo` | redimensionar → cinza → contraste → ruído → inclinação → binarizar |

```bash
# Todos os perfis
.venv/bin/python main.py --comparar

# Perfis escolhidos
.venv/bin/python main.py --perfis original ampliado binarizado

# Gravar a imagem entregue ao OCR (para inspeção visual): pagina_NNN_entrada.png
.venv/bin/python main.py --perfis binarizado --salvar-imagens-processadas
```

O comparativo é gravado em `resultados/<documento>/comparativo_perfis.md`.
Para criar um perfil novo, adicione uma entrada ao dicionário `PERFIS` em
`scripts/preprocessamento.py`.

### Adicionar transcrições de referência (para CER/WER)

1. Crie `referencias/<documento>/pagina_NNN.txt` com a transcrição **revisada por humanos**
   da página correspondente (mesma numeração dos resultados).
2. Recalcule os relatórios sem refazer o OCR:

```bash
.venv/bin/python main.py --somente-avaliacao
```

Sem referência, CER e WER aparecem como `—`/`null`: **nenhum valor é estimado**.
A confiança média do modelo é exibida, mas **não** é medida de acerto.

Comparação avulsa entre dois arquivos:

```bash
.venv/bin/python -m scripts.avaliacao --referencia ref.txt --hipotese resultados/02_estatuto_idoso/pagina_002.txt
```

## 11. Como interpretar CER e WER

- **CER** = (substituições + inserções + remoções de caracteres) ÷ nº de caracteres da referência.
- **WER** = o mesmo cálculo, em palavras.

Antes do cálculo, os textos passam apenas por normalização Unicode (NFC) e pela unificação
de espaços/quebras de linha (a quebra de linha depende do layout, não do reconhecimento).
**Acentos, maiúsculas, pontuação, `º` × `°` e `§` contam como erro.**

Referência prática:

| CER | Leitura |
|---|---|
| < 0,02 | excelente — revisão pontual |
| 0,02 – 0,05 | bom — revisão leve |
| 0,05 – 0,10 | razoável — revisão completa necessária |
| > 0,10 | fraco — texto pouco confiável |

O WER é sempre maior que o CER: um único caractere errado invalida a palavra inteira.
Em textos jurídicos, um CER baixo ainda pode esconder erros graves (ex.: `Art. 7º` → `Art. 1º`,
`não` → `nao`); por isso o relatório também compara **elementos jurídicos** (artigos,
parágrafos, incisos, alíneas, leis, datas) entre referência e OCR e lista os que
ficaram ausentes ou divergentes. Os valores podem passar de 1,0 quando o OCR insere muito
texto que não existe na referência.

## 12. Aplicação web

Interface no navegador para enviar uma imagem (ou PDF de até 20 páginas) e ver o resultado do
mesmo pipeline do notebook: pré-processamento → PaddleOCR → ordem de leitura → revisão humana →
metadados jurídicos.

```bash
cd Projeto_OCR_Leis
.venv/bin/pip install fastapi uvicorn python-multipart   # só na primeira vez
.venv/bin/python -m uvicorn webapp.servidor:app --port 8000
# abra http://localhost:8000
```

O que a tela mostra:

| Aba | Conteúdo |
|---|---|
| Visualização | imagem que entrou no OCR com as caixas detectadas (verde ≥ 0,95; amarelo entre o limiar e 0,95; vermelho abaixo do limiar) e o texto reconhecido ao lado; passar o mouse liga caixa ↔ texto; opção de mostrar a ordem de leitura |
| Métricas | **estimativas pela confiança do modelo**: média, mediana, mínima, ponderada por caracteres, % de trechos/caracteres acima do limiar, histograma, tempos, trechos para revisão e elementos jurídicos encontrados |
| Acurácia (referência) | cole a transcrição correta da página → **acurácia real**: CER, WER, acurácia de caracteres (1 − CER) e de palavras (1 − WER), erros por tipo (trocados/faltando/sobrando), preservação de Art./§/incisos/leis/datas e comparação palavra a palavra |
| Metadados jurídicos | identificação da norma, estatísticas, pendências e árvore de artigos (`scripts/metadados.py`) |
| JSON | JSON da página (idêntico ao `pagina_NNN.json` do `main.py`), JSON completo do documento e `metadados.json`, com download |

Importante: **confiança não é acurácia**. Um trecho pode ter confiança 0,99 e estar errado; a acurácia
só é medida contra um texto de referência. A interface marca cada número como "estimativa" ou "real".

Cada envio é gravado em `resultados_web/<id>/` com os mesmos arquivos do `main.py`
(`pagina_NNN.json`, `pagina_NNN.txt`, `documento_completo.txt`, `metadados.json`) mais
`pagina_NNN_entrada.png` (a imagem efetivamente enviada ao OCR) e `execucao.json` (parâmetros e referências).

API (documentação interativa em http://localhost:8000/docs):

```bash
curl -F arquivo=@imagem.jpg -F perfil=original -F limiar=0.8 http://localhost:8000/api/ocr
curl -H 'Content-Type: application/json' -d '{"pagina":1,"texto":"..."}' \
     http://localhost:8000/api/execucoes/<id>/referencia
curl -O http://localhost:8000/api/execucoes/<id>/json
```

## 13. Correção pós-OCR (ortografia, contexto e regras jurídicas)

`scripts/correcao.py` cria uma camada de correção **sem apagar o texto bruto**:
`pagina_NNN_correcao.json` traz `texto_corrigido` e a lista de correções (original, sugestão,
método, motivo, confiança, alternativas, aplicada ou só sugerida).

| Nível | O que faz | Exemplo |
|---|---|---|
| regra_juridica | ordinal até o 9º (LC 95/1998), `°`→`º`, incisos romanos válidos e em sequência | `Artigo 1°`→`1º`, `i`/`iV`/`Vi`→`II`/`IV`/`VI` |
| consistencia | nome próprio escrito de formas diferentes no documento | `Estrela do Noite`→`Norte` |
| dicionario | palavra inexistente (Hunspell pt-BR VERO + léxico jurídico de Londrina); candidatos por SymSpell + confusões de OCR (l/i/1, rn/m, acento) | `piuviais`→`pluviais`, `intermunicipai`→`intermunicipal` |
| contexto | BERTimbau escolhe o candidato que faz sentido na frase | `pessca`→`pessoa` (não `pesca`) |

Só aplica sozinho com custo baixo e margem clara; nomes próprios fora do dicionário viram
**sugestão** (ex.: `Sireia`). Na aplicação web a opção vem ligada; o texto corrigido mostra
correções aplicadas (verde) e sugestões (amarelo) com o motivo ao passar o mouse.

Recursos (baixados uma vez): `recursos/dicionario_pt_BR/` (VERO, LGPLv3) e o modelo
`neuralmind/bert-base-portuguese-cased` (Hugging Face, ~430 MB, em `~/.cache/huggingface`).
O léxico jurídico (`recursos/lexico_juridico.tsv`) é gerado das leis de Londrina **excluindo**
as 6 leis usadas como gabarito do benchmark.

Dependências extras: `torch` (CPU), `transformers<5`, `spylls`, `pyspellchecker`, `symspellpy`.

```bash
.venv/bin/python -m scripts.correcao resultados/02_estatuto_idoso      # corrige uma pasta de resultados
```

## 14. Benchmark com leis de Londrina (acurácia real)

`scripts/benchmark_londrina.py` usa os PDFs oficiais (camada de texto = gabarito exato) de 6 leis
(14 páginas), gera imagens em 3 condições (digital 300 dpi, escaneado, foto de celular) e mede
CER/WER por perfil de pré-processamento. Resultados em `resultados/benchmark_londrina/`
(`benchmark.md`). As imagens ficam em `imagens/03_leis_londrina_*` e as referências em
`referencias/03_leis_londrina/` — enviando uma dessas imagens na aplicação web, a acurácia real
é calculada automaticamente.

```bash
.venv/bin/python -m scripts.benchmark_londrina            # retomável
.venv/bin/python -m scripts.benchmark_londrina --somente-relatorio
```

## 15. Limitações conhecidas

- **Ordem de leitura** é heurística: layouts com notas laterais, tabelas, mais de duas
  colunas ou caixas de destaque podem sair fora de ordem.
- **Estrutura** (recuos, negrito, centralização, hierarquia visual) não é preservada; apenas
  quebras de linha e a sequência do texto.
- **Imagens pequenas** (ex.: 385 px de largura, como uma das páginas do Estatuto) têm
  caracteres com poucos pixels e baixa precisão; ampliar ajuda, mas não recupera detalhes perdidos.
- **Símbolos jurídicos** — `º`/`ª`/`°`, `§`, travessões (`–`/`—`/`-`) e algarismos romanos
  (`I`/`l`/`1`) — são confusões frequentes.
- **Documentos datilografados** antigos (como a Exposição de Motivos de 1983) costumam ter
  manchas, caracteres falhados e inclinação; o modelo é treinado majoritariamente com texto impresso.
- **Manuscritos, carimbos e assinaturas** não são reconhecidos de forma confiável.
- A **confiança** do modelo não garante acerto: palavras erradas podem ter confiança alta.
- Execução em CPU é mais lenta (segundos por página); o detector `server` privilegia precisão.
- O pré-processamento pode **piorar** o resultado (ex.: binarização apagando acentos finos);
  por isso nada é aplicado por padrão e os perfis devem ser comparados.
