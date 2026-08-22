"""Captura de tela via `grim` (Wayland/wlroots — Hyprland é o compositor-alvo do projeto)."""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path


class ErroCaptura(Exception):
    """Levantada quando não é possível capturar a tela (grim ausente, sessão não suportada etc.)."""


def capturar_tela(
    diretorio_destino: Path | None = None, binario: str = "grim", timeout_segundos: int = 15
) -> Path:
    diretorio = diretorio_destino or Path(tempfile.gettempdir())
    destino = diretorio / f"jarvis_tela_{uuid.uuid4().hex}.png"

    try:
        processo = subprocess.run(
            [binario, str(destino)],
            capture_output=True,
            text=True,
            timeout=timeout_segundos,
        )
    except FileNotFoundError as erro:
        raise ErroCaptura(
            f"binário '{binario}' não encontrado no PATH — instale o grim (screenshot para "
            "Wayland/wlroots)"
        ) from erro
    except subprocess.TimeoutExpired as erro:
        raise ErroCaptura("captura de tela não respondeu a tempo") from erro

    if processo.returncode != 0:
        raise ErroCaptura(f"{binario} falhou: {processo.stderr.strip()}")

    return destino
