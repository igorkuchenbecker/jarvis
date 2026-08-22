"""Runner de golden tasks (tests/golden/*.yaml): cada arquivo declara um objetivo, um roteiro de
respostas do LLM (via FakeProvider — determinístico, zero rede) e o trace de ações esperado, mais
trechos que a resposta final precisa conter. O runner compara o TRACE COMPLETO, não só se algo deu
certo no fim — regra do projeto: 100% de conclusão nas golden tasks é pré-requisito para abrir o
próximo marco.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from jarvis.core.loop import processar_turno
from jarvis.memory.conhecimento import RepositorioConhecimento
from jarvis.providers.fake import FakeProvider
from jarvis.security.executor import Executor
from jarvis.tools.conhecimento import criar_ferramentas_conhecimento
from jarvis.tools.registro import RegistroFerramentas

DIRETORIO_GOLDEN = Path(__file__).parent / "golden"


def _carregar_casos() -> list[dict[str, Any]]:
    return [
        yaml.safe_load(caminho.read_text(encoding="utf-8"))
        for caminho in sorted(DIRETORIO_GOLDEN.glob("*.yaml"))
    ]


@pytest.mark.parametrize("caso", _carregar_casos(), ids=lambda caso: caso["nome"])
def test_golden(caso: dict[str, Any], tmp_path: Path) -> None:
    for documento in caso.get("documentos", []):
        (tmp_path / documento["arquivo"]).write_text(documento["conteudo"], encoding="utf-8")

    repositorio = RepositorioConhecimento(tmp_path / "conhecimento.db")
    repositorio.ingerir_diretorio(tmp_path)

    registro = RegistroFerramentas()
    for ferramenta in criar_ferramentas_conhecimento(repositorio):
        registro.registrar(ferramenta)

    executor = Executor(registro, jail_paths=[tmp_path])
    provider = FakeProvider(caso["respostas_llm"])

    turno = processar_turno(provider, executor, caso["objetivo"])

    trace_obtido = [
        {"ferramenta": acao.ferramenta, "argumentos": acao.argumentos}
        for acao in turno.acoes_executadas
    ]
    assert trace_obtido == caso["acoes_esperadas"], f"trace divergente no golden '{caso['nome']}'"

    for trecho_esperado in caso.get("resposta_contem", []):
        assert trecho_esperado in turno.resposta_final, (
            f"resposta final do golden '{caso['nome']}' não contém {trecho_esperado!r}: "
            f"{turno.resposta_final!r}"
        )
