"""Memória persistente do JARVIS: textos guardados e busca textual via SQLite FTS5."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class RepositorioMemoria:
    def __init__(self, caminho_banco: Path) -> None:
        caminho_banco.parent.mkdir(parents=True, exist_ok=True)
        self._conexao = sqlite3.connect(caminho_banco)
        self._conexao.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memorias USING fts5(texto, criado_em UNINDEXED)"
        )
        self._conexao.commit()

    def armazenar(self, texto: str) -> None:
        self._conexao.execute(
            "INSERT INTO memorias(texto, criado_em) VALUES (?, ?)",
            (texto, datetime.now(UTC).isoformat()),
        )
        self._conexao.commit()

    def buscar(self, consulta: str, limite: int = 5) -> list[str]:
        try:
            cursor = self._conexao.execute(
                "SELECT texto FROM memorias WHERE memorias MATCH ? ORDER BY rank LIMIT ?",
                (consulta, limite),
            )
        except sqlite3.OperationalError:
            return []
        return [linha[0] for linha in cursor.fetchall()]

    def fechar(self) -> None:
        self._conexao.close()
