"""
Pré-processamento de imagens de documentos com OpenCV.

Cada transformação é uma função independente. Os "perfis" combinam
transformações para permitir comparar, no mesmo documento, o OCR sobre a
imagem original e sobre versões pré-processadas.

Nenhuma transformação altera o conteúdo textual: elas apenas modificam a
imagem que será entregue ao PaddleOCR.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Leitura e gravação (compatível com caminhos contendo acentos)
# ---------------------------------------------------------------------------

def carregar_imagem(caminho: str | Path) -> np.ndarray:
    """Carrega uma imagem em BGR. Usa imdecode para suportar caminhos com acentos."""
    dados = np.fromfile(str(caminho), dtype=np.uint8)
    imagem = cv2.imdecode(dados, cv2.IMREAD_COLOR)
    if imagem is None:
        raise ValueError(f"Não foi possível decodificar a imagem: {caminho}")
    return imagem


def salvar_imagem(imagem: np.ndarray, caminho: str | Path) -> None:
    """Salva uma imagem (útil para inspecionar visualmente o pré-processamento)."""
    caminho = Path(caminho)
    ok, buffer = cv2.imencode(caminho.suffix or ".png", imagem)
    if not ok:
        raise ValueError(f"Falha ao codificar a imagem para {caminho}")
    buffer.tofile(str(caminho))


# ---------------------------------------------------------------------------
# Transformações individuais
# ---------------------------------------------------------------------------

def escala_cinza(imagem: np.ndarray) -> np.ndarray:
    """Converte para escala de cinza (1 canal)."""
    if imagem.ndim == 2:
        return imagem
    return cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)


def aumentar_contraste(imagem: np.ndarray, clip_limit: float = 2.0, grade: int = 8) -> np.ndarray:
    """Aumenta o contraste local com CLAHE (equalização adaptativa de histograma)."""
    cinza = escala_cinza(imagem)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grade, grade))
    return clahe.apply(cinza)


def reduzir_ruido(imagem: np.ndarray, intensidade: int = 10) -> np.ndarray:
    """Reduz ruído com Non-Local Means (preserva melhor as bordas dos caracteres)."""
    cinza = escala_cinza(imagem)
    return cv2.fastNlMeansDenoising(cinza, None, h=intensidade, templateWindowSize=7, searchWindowSize=21)


def binarizacao_adaptativa(imagem: np.ndarray, bloco: int = 31, constante: int = 15) -> np.ndarray:
    """Binarização adaptativa gaussiana: robusta a iluminação irregular da digitalização."""
    cinza = escala_cinza(imagem)
    if bloco % 2 == 0:
        bloco += 1  # o OpenCV exige tamanho de bloco ímpar
    return cv2.adaptiveThreshold(
        cinza, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, bloco, constante
    )


def estimar_inclinacao(imagem: np.ndarray, angulo_maximo: float = 10.0, passo: float = 0.25) -> float:
    """
    Estima o ângulo de inclinação da página (em graus) pelo método de perfil de
    projeção: o ângulo correto é aquele em que as linhas de texto ficam
    horizontais, maximizando a variância da soma de pixels por linha.
    """
    cinza = escala_cinza(imagem)
    # Trabalha em uma versão reduzida para ganhar velocidade
    escala = min(1.0, 1000.0 / max(cinza.shape))
    pequena = cv2.resize(cinza, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA) if escala < 1 else cinza
    _, tinta = cv2.threshold(pequena, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    altura, largura = tinta.shape
    centro = (largura / 2, altura / 2)
    melhor_angulo, melhor_pontuacao = 0.0, -1.0
    for angulo in np.arange(-angulo_maximo, angulo_maximo + passo, passo):
        matriz = cv2.getRotationMatrix2D(centro, float(angulo), 1.0)
        girada = cv2.warpAffine(tinta, matriz, (largura, altura), flags=cv2.INTER_NEAREST, borderValue=0)
        perfil = girada.sum(axis=1, dtype=np.float64)
        pontuacao = float(np.var(perfil))
        if pontuacao > melhor_pontuacao:
            melhor_pontuacao, melhor_angulo = pontuacao, float(angulo)
    return melhor_angulo


def corrigir_inclinacao(imagem: np.ndarray, angulo_minimo: float = 0.3) -> np.ndarray:
    """Gira a página para deixar as linhas horizontais (ignora ângulos desprezíveis)."""
    angulo = estimar_inclinacao(imagem)
    if abs(angulo) < angulo_minimo:
        return imagem
    altura, largura = imagem.shape[:2]
    matriz = cv2.getRotationMatrix2D((largura / 2, altura / 2), angulo, 1.0)
    fundo = 255 if imagem.ndim == 2 else (255, 255, 255)
    return cv2.warpAffine(
        imagem, matriz, (largura, altura), flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT, borderValue=fundo,
    )


def redimensionar(imagem: np.ndarray, largura_minima: int = 1600, largura_maxima: int = 3000) -> np.ndarray:
    """
    Ajusta a largura para uma faixa útil ao OCR. Imagens pequenas (ex.: 385 px)
    têm caracteres com poucos pixels; ampliar costuma ajudar o reconhecimento.
    """
    largura = imagem.shape[1]
    if largura < largura_minima:
        fator = largura_minima / largura
        return cv2.resize(imagem, None, fx=fator, fy=fator, interpolation=cv2.INTER_CUBIC)
    if largura > largura_maxima:
        fator = largura_maxima / largura
        return cv2.resize(imagem, None, fx=fator, fy=fator, interpolation=cv2.INTER_AREA)
    return imagem


# Registro das transformações disponíveis (nome -> função)
TRANSFORMACOES = {
    "redimensionar": redimensionar,
    "cinza": escala_cinza,
    "contraste": aumentar_contraste,
    "ruido": reduzir_ruido,
    "inclinacao": corrigir_inclinacao,
    "binarizar": binarizacao_adaptativa,
}

# Perfis pré-definidos para os testes comparativos.
# A ordem das etapas importa: redimensionar e corrigir inclinação antes de binarizar.
PERFIS: dict[str, list[str]] = {
    "original": [],
    "ampliado": ["redimensionar"],
    "cinza_contraste": ["redimensionar", "cinza", "contraste"],
    "sem_ruido": ["redimensionar", "cinza", "ruido"],
    "binarizado": ["redimensionar", "cinza", "ruido", "binarizar"],
    "deskew": ["redimensionar", "inclinacao"],
    "completo": ["redimensionar", "cinza", "contraste", "ruido", "inclinacao", "binarizar"],
}


def aplicar_etapas(imagem: np.ndarray, etapas: list[str]) -> np.ndarray:
    """
    Aplica as etapas na ordem informada e devolve uma imagem BGR de 3 canais
    (formato esperado pelo PaddleOCR).
    """
    resultado = imagem
    for etapa in etapas:
        if etapa not in TRANSFORMACOES:
            raise ValueError(f"Etapa de pré-processamento desconhecida: {etapa!r}. "
                             f"Disponíveis: {', '.join(TRANSFORMACOES)}")
        resultado = TRANSFORMACOES[etapa](resultado)
    if resultado.ndim == 2:
        resultado = cv2.cvtColor(resultado, cv2.COLOR_GRAY2BGR)
    return resultado


def aplicar_perfil(imagem: np.ndarray, perfil: str) -> np.ndarray:
    """Aplica um perfil pré-definido (ver PERFIS)."""
    if perfil not in PERFIS:
        raise ValueError(f"Perfil desconhecido: {perfil!r}. Disponíveis: {', '.join(PERFIS)}")
    return aplicar_etapas(imagem, PERFIS[perfil])
