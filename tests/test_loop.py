import json
from pathlib import Path
from typing import Any

from jarvis.core.loop import processar_turno
from jarvis.providers.fake import FakeProvider
from jarvis.security.executor import Executor
from jarvis.tools.fs import criar_ferramentas_fs
from jarvis.tools.registro import RegistroFerramentas


def _json_acao(ferramenta: str, **argumentos: Any) -> str:
    return json.dumps({"tipo": "acao", "ferramenta": ferramenta, "argumentos": argumentos})


def _executor_fs(tmp_path: Path) -> Executor:
    registro = RegistroFerramentas()
    for ferramenta in criar_ferramentas_fs():
        registro.registrar(ferramenta)
    return Executor(registro, jail_paths=[tmp_path])


def test_sem_acao_retorna_texto_direto(tmp_path: Path) -> None:
    provider = FakeProvider(["Brasília é a capital do Brasil."])
    executor = _executor_fs(tmp_path)

    turno = processar_turno(provider, executor, "qual é a capital do brasil?")

    assert turno.resposta_final == "Brasília é a capital do Brasil."
    assert turno.acoes_executadas == []


def test_executa_uma_acao_e_finaliza(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    provider = FakeProvider(
        [
            _json_acao("fs.list", caminho=str(tmp_path)),
            "O único arquivo é a.txt.",
        ]
    )
    executor = _executor_fs(tmp_path)

    turno = processar_turno(provider, executor, "liste os arquivos do meu workspace")

    assert turno.resposta_final == "O único arquivo é a.txt."
    assert len(turno.acoes_executadas) == 1
    assert turno.acoes_executadas[0].ferramenta == "fs.list"


def test_encadeia_duas_acoes_antes_de_responder(tmp_path: Path) -> None:
    caminho_nota = str(tmp_path / "nota.txt")
    provider = FakeProvider(
        [
            _json_acao("fs.write", caminho=caminho_nota, conteudo="nota"),
            _json_acao("fs.read", caminho=caminho_nota),
            "Salvei e conferi a nota.",
        ]
    )
    executor = _executor_fs(tmp_path)

    turno = processar_turno(provider, executor, "salve uma nota e confira o conteúdo")

    assert turno.resposta_final == "Salvei e conferi a nota."
    assert [acao.ferramenta for acao in turno.acoes_executadas] == ["fs.write", "fs.read"]


def test_ferramenta_com_erro_e_informada_ao_llm(tmp_path: Path) -> None:
    provider = FakeProvider(
        [
            _json_acao("fs.read", caminho=str(tmp_path / "nao-existe.txt")),
            "Esse arquivo não existe, quer que eu crie?",
        ]
    )
    executor = _executor_fs(tmp_path)

    turno = processar_turno(provider, executor, "leia nao-existe.txt")

    assert turno.resposta_final == "Esse arquivo não existe, quer que eu crie?"
    assert "falhou" in provider.historico[1]


def test_para_no_maximo_de_iteracoes(tmp_path: Path) -> None:
    acao_infinita = _json_acao("fs.list", caminho=str(tmp_path))
    provider = FakeProvider([acao_infinita] * 5)
    executor = _executor_fs(tmp_path)

    turno = processar_turno(provider, executor, "faça algo", max_iteracoes=3)

    assert len(turno.acoes_executadas) == 3
    assert turno.resposta_final == acao_infinita
