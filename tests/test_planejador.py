import json
from pathlib import Path

import pytest

from jarvis.core.objetivos import RepositorioObjetivos
from jarvis.core.planejador import executar_objetivo, planejar
from jarvis.providers.base import ErroProvider
from jarvis.providers.fake import FakeProvider
from jarvis.security.executor import Executor
from jarvis.tools.registro import RegistroFerramentas


def _plano_json(*descricoes: str) -> str:
    return json.dumps(
        {
            "tipo": "plano",
            "subtarefas": [
                {"descricao": descricao, "criterio_sucesso": f"{descricao} concluída"}
                for descricao in descricoes
            ],
        }
    )


def _executor_vazio(tmp_path: Path) -> Executor:
    return Executor(RegistroFerramentas(), jail_paths=[tmp_path])


def test_planejar_decompoe_objetivo_em_subtarefas() -> None:
    provider = FakeProvider([_plano_json("passo 1", "passo 2")])

    subtarefas = planejar(provider, "fazer alguma coisa")

    assert [s.descricao for s in subtarefas] == ["passo 1", "passo 2"]


def test_planejar_levanta_erro_quando_resposta_nao_e_plano_valido() -> None:
    provider = FakeProvider(["isso não é json nem plano"])

    with pytest.raises(ErroProvider, match="não consegui decompor"):
        planejar(provider, "fazer alguma coisa")


def test_executa_objetivo_com_duas_subtarefas_bem_sucedidas(tmp_path: Path) -> None:
    provider = FakeProvider(
        [
            _plano_json("passo 1", "passo 2"),
            "SUCESSO: passo 1 feito",
            "SUCESSO: passo 2 feito",
        ]
    )
    repositorio = RepositorioObjetivos(tmp_path / "jarvis.db")

    resultado = executar_objetivo(provider, _executor_vazio(tmp_path), repositorio, "objetivo x")

    assert resultado.estado == "concluido"
    assert [s.estado for s in resultado.subtarefas] == ["concluida", "concluida"]


def test_executa_objetivo_replaneja_apos_falha_e_conclui(tmp_path: Path) -> None:
    provider = FakeProvider(
        [
            _plano_json("tentar de um jeito"),
            "FALHA: não funcionou desse jeito",
            _plano_json("tentar de outro jeito"),
            "SUCESSO: funcionou dessa vez",
        ]
    )
    repositorio = RepositorioObjetivos(tmp_path / "jarvis.db")

    resultado = executar_objetivo(provider, _executor_vazio(tmp_path), repositorio, "objetivo y")

    assert resultado.estado == "concluido"
    assert len(resultado.subtarefas) == 1
    assert resultado.subtarefas[0].descricao == "tentar de outro jeito"
    assert resultado.subtarefas[0].estado == "concluida"


def test_objetivo_falha_definitivamente_apos_esgotar_replanejamentos(tmp_path: Path) -> None:
    respostas = [_plano_json("tentativa 0")]
    for indice in range(1, 6):
        respostas.append("FALHA: continua não funcionando")
        respostas.append(_plano_json(f"tentativa {indice}"))
    provider = FakeProvider(respostas)
    repositorio = RepositorioObjetivos(tmp_path / "jarvis.db")

    resultado = executar_objetivo(
        provider, _executor_vazio(tmp_path), repositorio, "objetivo impossível",
        max_replanejamentos=3,
    )

    assert resultado.estado == "falhou"


def test_retoma_objetivo_apos_crash_sem_replanejar_nem_reexecutar(tmp_path: Path) -> None:
    caminho_db = tmp_path / "jarvis.db"
    repositorio_antes_do_crash = RepositorioObjetivos(caminho_db)
    id_objetivo = repositorio_antes_do_crash.criar(
        "objetivo retomavel",
        planejar(FakeProvider([_plano_json("passo 1", "passo 2")]), "objetivo retomavel"),
    )
    objetivo = repositorio_antes_do_crash.obter(id_objetivo)
    assert objetivo is not None
    objetivo.subtarefas[0].estado = "concluida"
    objetivo.indice_atual = 1
    repositorio_antes_do_crash.salvar_checkpoint(objetivo)

    # "crash": nova conexão ao mesmo banco, novo provider (sem memória do que já rodou)
    repositorio_depois_do_crash = RepositorioObjetivos(caminho_db)
    provider_novo_processo = FakeProvider(["SUCESSO: passo 2 feito"])

    resultado = executar_objetivo(
        provider_novo_processo,
        _executor_vazio(tmp_path),
        repositorio_depois_do_crash,
        "objetivo retomavel",
    )

    assert resultado.estado == "concluido"
    assert len(provider_novo_processo.historico) == 1
    assert "passo 2" in provider_novo_processo.historico[0]
    assert resultado.subtarefas[0].estado == "concluida"
    assert resultado.subtarefas[1].estado == "concluida"
