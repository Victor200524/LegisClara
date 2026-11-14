# Benchmark de OCR — leis de Londrina (acurácia real)

Acurácia real do PaddleOCR em leis de Londrina; referência = camada de texto do PDF oficial (texto horizontal; carimbo vertical da assinatura excluído).

Páginas: 14 (de 6 leis).

| Condição | Perfil | Acurácia caracteres | Acurácia palavras | CER | WER | F1 palavras (sem ordem) | Art. | Leis | Datas | Confiança média | Tempo médio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| digital | original | 69,11% | 61,76% | 0.3089 | 0.3824 | 90,73% | 45/45 | 14/14 | 16/16 | 87,14% | 29.12 s |
| digital | ampliado | 69,11% | 61,76% | 0.3089 | 0.3824 | 90,73% | 45/45 | 14/14 | 16/16 | 87,14% | 25.09 s |
| digital | deskew | 69,11% | 61,76% | 0.3089 | 0.3824 | 90,73% | 45/45 | 14/14 | 16/16 | 87,14% | 26.02 s |
| digital | completo | 75,25% | 68,28% | 0.2475 | 0.3172 | 90,98% | 22/22 | 8/8 | 10/10 | 91,63% | 28.64 s |

CER/WER agregados = soma das distâncias ÷ soma do tamanho das referências. Art./Leis/Datas = elementos idênticos no OCR ÷ elementos na referência ("Art. 1°" no lugar de "Art. 1º" conta como erro).
