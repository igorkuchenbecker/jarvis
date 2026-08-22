"""Configuração de logging estruturado do JARVIS."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class FormatadorJson(logging.Formatter):
    """Formata cada registro de log como uma linha JSON."""

    def format(self, registro: logging.LogRecord) -> str:
        corpo: dict[str, Any] = {
            "quando": datetime.now(UTC).isoformat(),
            "nivel": registro.levelname,
            "modulo": registro.name,
            "mensagem": registro.getMessage(),
        }
        if registro.exc_info:
            corpo["excecao"] = self.formatException(registro.exc_info)
        extras = getattr(registro, "extras", None)
        if isinstance(extras, dict):
            corpo.update(extras)
        return json.dumps(corpo, ensure_ascii=False)


def configurar_logging(diretorio_logs: Path | None = None, nivel: int = logging.INFO) -> None:
    """Configura o logger raiz do JARVIS com saída JSON em stderr e, opcionalmente, arquivo."""
    raiz = logging.getLogger("jarvis")
    raiz.setLevel(nivel)
    raiz.handlers.clear()

    saida_erro = logging.StreamHandler(sys.stderr)
    saida_erro.setFormatter(FormatadorJson())
    raiz.addHandler(saida_erro)

    if diretorio_logs is not None:
        diretorio_logs.mkdir(parents=True, exist_ok=True)
        saida_arquivo = logging.FileHandler(diretorio_logs / "jarvis.log", encoding="utf-8")
        saida_arquivo.setFormatter(FormatadorJson())
        raiz.addHandler(saida_arquivo)

    raiz.propagate = False


def obter_logger(nome: str) -> logging.Logger:
    """Retorna um logger filho do logger raiz do JARVIS."""
    return logging.getLogger(f"jarvis.{nome}")
