# LegisClara

OCR de documentos legislativos em português com **PaddleOCR 3.x**, correção automática do texto
reconhecido e aplicação web para enviar uma imagem e ver o resultado, as métricas e o JSON.

## O que faz

- **OCR**: imagem ou PDF → texto, na ordem de leitura (inclusive em páginas com duas colunas), com
  confiança por trecho e marcação do que precisa de revisão humana.
- **Correção pós-OCR** (o texto bruto é sempre preservado):
  - **regras jurídicas**: `Art. 1°` → `1º`, incisos `i`/`iV`/`Vi` → `II`/`IV`/`VI`;
  - **consistência**: um nome escrito de formas diferentes no mesmo documento (`Estrela do Noite` → `Norte`);
  - **dicionário pt-BR + léxico jurídico**: `piuviais` → `pluviais`, `Municipio` → `Município`;
  - **contexto (BERTimbau)**: `pessca` → `pessoa`, e não `pesca`.
- **Métricas**: confiança do modelo (estimativa) e **acurácia real** (CER/WER) quando há texto de referência.
- **Metadados jurídicos**: número e data da norma, artigos, parágrafos, incisos e leis citadas.

## Como rodar

Requer Python 3.11. Roda em CPU, sem GPU.

```bash
git clone https://github.com/Victor200524/LegisClara.git
cd LegisClara
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn webapp.servidor:app --port 8000
```

Abra **http://localhost:8000** e envie uma imagem ou um PDF.

- No primeiro uso, os modelos do PaddleOCR e o BERTimbau (~430 MB) são baixados automaticamente.
- O corretor leva uns 30 s para carregar. Aguarde a mensagem `corretor (dicionário + BERTimbau) pronto` no terminal.
- **Teste rápido:** envie uma imagem de `imagens/03_leis_londrina_foto/imagens_do_documento/`. O texto
  oficial é carregado sozinho e a tela mostra a acurácia antes e depois da correção.

### Linha de comando

```bash
.venv/bin/python main.py                                  # OCR das pastas em imagens/
.venv/bin/python main.py --comparar                       # compara perfis de pré-processamento
.venv/bin/python -m scripts.correcao resultados/02_estatuto_idoso   # corrige uma pasta de resultados
.venv/bin/python -m scripts.benchmark_londrina            # benchmark com leis de Londrina (retomável)
```

## Estrutura

```
webapp/            aplicação web (FastAPI + HTML/JS)
scripts/           ocr, preprocessamento, avaliacao, metadados, correcao, benchmark_londrina
recursos/          dicionário pt-BR (VERO/LibreOffice, LGPLv3) e léxico jurídico
Leis_Londrina/     237 leis da Câmara Municipal de Londrina (3 por ano, 1948–2026) + análise da estrutura
imagens/           imagens de teste (Estatuto do Idoso e leis de Londrina: digital, escaneado e foto)
referencias/       textos corretos usados para medir a acurácia
resultados/        saídas do OCR e relatório do benchmark
docs/              documentação detalhada
```

## Resultados

Acurácia medida contra o texto oficial do PDF:

| Imagem | Palavras certas (OCR) | Após correção |
|---|---|---|
| Lei 14300, foto de celular | 89,5% | **93,9%** |
| Lei 13990, foto de celular | 82,6% | **86,3%** |

O benchmark completo (`resultados/benchmark_londrina/benchmark.md`) ficou **parcial**. Nas páginas
digitais, a maior parte do erro vem da **ordem de leitura** em tabelas: contando as palavras sem levar
em conta a ordem, o OCR acerta 90,7%.

Documentação completa: [docs/DOCUMENTACAO.md](docs/DOCUMENTACAO.md) ·
estrutura das leis de Londrina: [Leis_Londrina/ESTRUTURA_DAS_LEIS.md](Leis_Londrina/ESTRUTURA_DAS_LEIS.md)
