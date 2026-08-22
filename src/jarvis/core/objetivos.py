"""Persistência de objetivos (goals) do JARVIS em SQLite — permite retomar após um crash.

Um objetivo tem uma lista de subtarefas; o índice da subtarefa atual e o estado de cada uma são
salvos a cada progresso (`salvar_checkpoint`), não só no final — é isso que torna o objetivo
retomável: um processo novo pode chamar `obter_em_andamento()` e continuar de onde parou, sem
replanejar nem re-executar subtarefas já concluídas.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class Subtarefa:
    descricao: str
    criterio_sucesso: str
    estado: str = "pendente"  # pendente | concluida | falhou


@dataclass
class ObjetivoPersistido:
    id: str
    descricao: str
    subtarefas: list[Subtarefa]
    indice_atual: int
    estado: str  # em_andamento | concluido | falhou
    replanejamentos: int = 0


def _subtarefas_para_json(subtarefas: list[Subtarefa]) -> str:
    return json.dumps(
        [
            {
                "descricao": s.descricao,
                "criterio_sucesso": s.criterio_sucesso,
                "estado": s.estado,
            }
            for s in subtarefas
        ]
    )


def _subtarefas_de_json(bruto: str) -> list[Subtarefa]:
    dados: list[dict[str, Any]] = json.loads(bruto)
    return [Subtarefa(**item) for item in dados]


class RepositorioObjetivos:
    def __init__(self, caminho_banco: Path) -> None:
        caminho_banco.parent.mkdir(parents=True, exist_ok=True)
        self._conexao = sqlite3.connect(caminho_banco)
        self._conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS objetivos (
                id TEXT PRIMARY KEY,
                descricao TEXT NOT NULL,
                subtarefas_json TEXT NOT NULL,
                indice_atual INTEGER NOT NULL,
                estado TEXT NOT NULL,
                replanejamentos INTEGER NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            )
            """
        )
        self._conexao.commit()

    def criar(self, descricao: str, subtarefas: list[Subtarefa]) -> str:
        id_objetivo = str(uuid.uuid4())
        agora = datetime.now(UTC).isoformat()
        self._conexao.execute(
            "INSERT INTO objetivos(id, descricao, subtarefas_json, indice_atual, estado, "
            "replanejamentos, criado_em, atualizado_em) "
            "VALUES (?, ?, ?, 0, 'em_andamento', 0, ?, ?)",
            (id_objetivo, descricao, _subtarefas_para_json(subtarefas), agora, agora),
        )
        self._conexao.commit()
        return id_objetivo

    def obter(self, id_objetivo: str) -> ObjetivoPersistido | None:
        linha = self._conexao.execute(
            "SELECT id, descricao, subtarefas_json, indice_atual, estado, replanejamentos "
            "FROM objetivos WHERE id = ?",
            (id_objetivo,),
        ).fetchone()
        return self._linha_para_objetivo(linha)

    def obter_em_andamento(self) -> ObjetivoPersistido | None:
        linha = self._conexao.execute(
            "SELECT id, descricao, subtarefas_json, indice_atual, estado, replanejamentos "
            "FROM objetivos WHERE estado = 'em_andamento' ORDER BY atualizado_em DESC LIMIT 1"
        ).fetchone()
        return self._linha_para_objetivo(linha)

    def _linha_para_objetivo(self, linha: tuple[Any, ...] | None) -> ObjetivoPersistido | None:
        if linha is None:
            return None
        return ObjetivoPersistido(
            id=linha[0],
            descricao=linha[1],
            subtarefas=_subtarefas_de_json(linha[2]),
            indice_atual=linha[3],
            estado=linha[4],
            replanejamentos=linha[5],
        )

    def salvar_checkpoint(self, objetivo: ObjetivoPersistido) -> None:
        self._conexao.execute(
            "UPDATE objetivos SET subtarefas_json = ?, indice_atual = ?, estado = ?, "
            "replanejamentos = ?, atualizado_em = ? WHERE id = ?",
            (
                _subtarefas_para_json(objetivo.subtarefas),
                objetivo.indice_atual,
                objetivo.estado,
                objetivo.replanejamentos,
                datetime.now(UTC).isoformat(),
                objetivo.id,
            ),
        )
        self._conexao.commit()

    def fechar(self) -> None:
        self._conexao.close()
