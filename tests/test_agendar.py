"""Testes do agendador (systemd user timers) sem tocar em systemctl real."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.io.agendador import (
    PREFIJO_UNIDADE,
    ErroAgendador,
    SistemaSystemctl,
    criar_tarefa,
    listar_tarefas,
    remover_tarefa,
    slugificar,
)
from jarvis.io.agendador import (
    testar_tarefa as disparar_tarefa,
)


def _systemctl_falso() -> tuple[list[list[str]], SistemaSystemctl]:
    chamadas: list[list[str]] = []

    def executar(args: list[str]) -> str:
        chamadas.append(args)
        return ""

    return chamadas, executar


def test_criar_tarefa_gera_units_e_ativa_timer(tmp_path: Path) -> None:
    chamadas, systemctl = _systemctl_falso()

    timer = criar_tarefa(
        "Revisar Second Brain!",
        "revisar as notas do second brain",
        diarias="08:30",
        diretorio=tmp_path,
        systemctl=systemctl,
        execstart='/home/igor/.venv/bin/jarvis run "revisar as notas do second brain"',
    )

    assert timer.name == f"{PREFIJO_UNIDADE}revisar-second-brain.timer"
    servico = tmp_path / f"{PREFIJO_UNIDADE}revisar-second-brain.service"
    assert 'jarvis run "revisar as notas do second brain"' in servico.read_text()
    assert "OnCalendar=*-*-* 08:30:00" in timer.read_text()
    assert ["daemon-reload"] in chamadas
    assert ["enable", "--now", timer.name] in chamadas


def test_criar_tarefa_a_cada_minutos(tmp_path: Path) -> None:
    chamadas, systemctl = _systemctl_falso()

    timer = criar_tarefa(
        "x",
        "objetivo",
        a_cada=15,
        diretorio=tmp_path,
        systemctl=systemctl,
        execstart="E {objetivo}",
    )

    assert "OnCalendar=*:0/15" in timer.read_text()


def test_criar_tarefa_quando_customizado(tmp_path: Path) -> None:
    chamadas, systemctl = _systemctl_falso()
    timer = criar_tarefa(
        "x",
        "objetivo",
        quando="Mon..Fri 09:00:00",
        diretorio=tmp_path,
        systemctl=systemctl,
        execstart="E {objetivo}",
    )

    assert "OnCalendar=Mon..Fri 09:00:00" in timer.read_text()


def test_criar_tarefa_recusa_nome_duplicado_sem_sobrescrever(tmp_path: Path) -> None:
    chamadas, systemctl = _systemctl_falso()
    criar_tarefa(
        "x",
        "objetivo",
        diarias="10:00",
        diretorio=tmp_path,
        systemctl=systemctl,
        execstart="E {objetivo}",
    )

    with pytest.raises(ErroAgendador, match="já existe"):
        criar_tarefa(
            "x",
            "outro",
            diarias="11:00",
            diretorio=tmp_path,
            systemctl=systemctl,
            execstart="E {objetivo}",
        )


def test_criar_tarefa_sobrescreve_com_flag(tmp_path: Path) -> None:
    chamadas, systemctl = _systemctl_falso()
    criar_tarefa(
        "x",
        "objetivo",
        diarias="10:00",
        diretorio=tmp_path,
        systemctl=systemctl,
        execstart="E {objetivo}",
    )

    criar_tarefa(
        "x",
        "outro",
        diarias="11:00",
        diretorio=tmp_path,
        systemctl=systemctl,
        execstart="E {objetivo}",
        sobrescrever=True,
    )

    assert "11:00" in (tmp_path / f"{PREFIJO_UNIDADE}x.timer").read_text()


def test_diarias_invalidas_dao_erro(tmp_path: Path) -> None:
    chamadas, systemctl = _systemctl_falso()
    for invalida in ("8h30", "25:00", "08:61", ""):
        with pytest.raises(ErroAgendador):
            criar_tarefa(
                "x",
                "objetivo",
                diarias=invalida,
                diretorio=tmp_path,
                systemctl=systemctl,
                execstart="E {objetivo}",
            )


def test_a_cada_invalido_da_erro(tmp_path: Path) -> None:
    chamadas, systemctl = _systemctl_falso()
    with pytest.raises(ErroAgendador):
        criar_tarefa(
            "x",
            "objetivo",
            a_cada=0,
            diretorio=tmp_path,
            systemctl=systemctl,
            execstart="E {objetivo}",
        )


def test_listar_tarefas_por_unidades_na_pasta(tmp_path: Path) -> None:
    chamadas, systemctl = _systemctl_falso()
    criar_tarefa(
        "Alpha",
        "a",
        diarias="08:00",
        diretorio=tmp_path,
        systemctl=systemctl,
        execstart="E {objetivo}",
    )
    criar_tarefa(
        "Beta",
        "b",
        diarias="09:00",
        diretorio=tmp_path,
        systemctl=systemctl,
        execstart="E {objetivo}",
    )

    nomes = listar_tarefas(diretorio=tmp_path)

    assert nomes == ["alpha", "beta"]


def test_remover_tarefa_desativa_e_apaga_units(tmp_path: Path) -> None:
    chamadas, systemctl = _systemctl_falso()
    criar_tarefa(
        "x",
        "objetivo",
        diarias="08:00",
        diretorio=tmp_path,
        systemctl=systemctl,
        execstart="E {objetivo}",
    )

    remover_tarefa("x", diretorio=tmp_path, systemctl=systemctl)

    assert not list((tmp_path).glob(f"{PREFIJO_UNIDADE}x.*"))
    assert ["disable", "--now", f"{PREFIJO_UNIDADE}x.timer"] in chamadas
    assert ["daemon-reload"] in chamadas


def test_testar_tarefa_dispara_servico() -> None:
    chamadas, systemctl = _systemctl_falso()

    disparar_tarefa("x", systemctl=systemctl)

    assert ["start", f"{PREFIJO_UNIDADE}x.service"] in chamadas


def test_slugificar_normaliza_nome() -> None:
    assert slugificar("Revisar Second Brain 3x!") == "revisar-second-brain-3x"
    with pytest.raises(ErroAgendador):
        slugificar("!!!")
