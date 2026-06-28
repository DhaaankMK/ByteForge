"""
gui/theme.py
---------------

Módulo central de identidade visual do ByteForge. Concentra a
paleta de cores extraída da logomarca oficial (gradiente preto ->
azul-índigo) e disponibiliza utilitários de interpolação de cor,
usados pelos componentes visuais (`gui/widgets.py`, `gui/splash.py`,
banners de cabeçalho, etc.) para manter consistência visual em toda
a aplicação.

Este módulo é puramente cosmético — não contém nenhuma lógica de
negócio e não deve ser importado pelo pacote `core`.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

# ----------------------------------------------------------------------
# Paleta extraída diretamente da arte oficial do ByteForge (logo e
# capa), garantindo que toda a interface reflita a identidade visual
# real da marca em vez de cores genéricas de template.
# ----------------------------------------------------------------------

GRADIENT_BLACK: str = "#000000"
GRADIENT_NAVY: str = "#0d0d33"
GRADIENT_DEEP_BLUE: str = "#14134d"
GRADIENT_INDIGO: str = "#211f80"
GRADIENT_VIVID_BLUE: str = "#2e2db3"
GRADIENT_BRIGHT_BLUE: str = "#3533cd"

# Sequência de cores usada para desenhar o gradiente horizontal de
# fundo (do escuro para o vívido), espelhando a arte da capa oficial.
BRAND_GRADIENT_STOPS: List[str] = [
    GRADIENT_BLACK,
    GRADIENT_NAVY,
    GRADIENT_DEEP_BLUE,
    GRADIENT_INDIGO,
    GRADIENT_VIVID_BLUE,
    GRADIENT_BRIGHT_BLUE,
]

# Cores de destaque (accent), derivadas do tom mais vívido da marca,
# usadas em botões, bordas de foco e elementos interativos.
ACCENT: str = "#3d3ce0"
ACCENT_HOVER: str = "#5250f2"
ACCENT_SOFT: str = "#2a29a8"

SUCCESS: str = "#2fae66"
WARNING: str = "#d99a2b"
DANGER: str = "#c0392b"
DANGER_HOVER: str = "#992e22"

TEXT_PRIMARY: str = "#f5f6ff"
TEXT_MUTED: str = "#a7a9d6"

ASSETS_DIR: Path = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH: Path = ASSETS_DIR / "logo.png"
COVER_PATH: Path = ASSETS_DIR / "capa.png"


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def interpolate_color(color_a: str, color_b: str, fraction: float) -> str:
    """
    Interpola linearmente entre duas cores hexadecimais. `fraction`
    deve estar entre 0.0 (retorna `color_a`) e 1.0 (retorna
    `color_b`). Utilizado para desenhar gradientes suaves em
    componentes baseados em `tkinter.Canvas`.
    """
    fraction = max(0.0, min(1.0, fraction))
    ra, ga, ba = _hex_to_rgb(color_a)
    rb, gb, bb = _hex_to_rgb(color_b)
    r = ra + (rb - ra) * fraction
    g = ga + (gb - ga) * fraction
    b = ba + (bb - ba) * fraction
    return _rgb_to_hex((r, g, b))


def multi_stop_gradient(stops: List[str], steps: int) -> List[str]:
    """
    Gera uma lista de `steps` cores hexadecimais interpolando
    suavemente através de uma sequência de cores de parada
    (`stops`), distribuídas uniformemente ao longo do eixo de
    interpolação. Usado para desenhar gradientes horizontais
    multi-tonais em `tkinter.Canvas` (ex.: cabeçalhos de banner).
    """
    if steps <= 1 or len(stops) == 1:
        return [stops[0]] * max(steps, 1)

    segment_count = len(stops) - 1
    result: List[str] = []
    for i in range(steps):
        position = (i / (steps - 1)) * segment_count
        segment_index = min(int(position), segment_count - 1)
        local_fraction = position - segment_index
        color = interpolate_color(stops[segment_index], stops[segment_index + 1], local_fraction)
        result.append(color)
    return result
