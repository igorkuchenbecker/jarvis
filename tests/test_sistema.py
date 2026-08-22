import os
import subprocess
from typing import Any

import pytest

from jarvis.tools.sistema import criar_ferramentas_sistema


def _executar(nome: str, argumentos: dict[str, Any], timeout_segundos: int = 5) -> Any:
    ferramentas = {f.nome: f for f in criar_ferramentas_sistema(timeout_segundos=timeout_segundos)}
    return ferramentas[nome].executar(argumentos)


def test_sys_info_retorna_campos_basicos() -> None:
    resultado = _executar("sys.info", {})

    assert resultado["cpus"] and resultado["cpus"] > 0
    assert resultado["disco_home_total_gb"] > 0
    assert isinstance(resultado["carga_media"], tuple)


def test_proc_list_inclui_o_proprio_processo_de_teste() -> None:
    resultado = _executar("proc.list", {})

    pids = {item["pid"] for item in resultado}
    assert os.getpid() in pids


def test_proc_kill_encerra_processo_real() -> None:
    processo = subprocess.Popen(["sleep", "30"])
    try:
        resultado = _executar("proc.kill", {"pid": processo.pid, "sinal": "SIGTERM"})
        assert "SIGTERM" in resultado
        processo.wait(timeout=5)
        assert processo.returncode is not None
    finally:
        if processo.poll() is None:
            processo.kill()


def test_proc_kill_recusa_pid_inexistente() -> None:
    with pytest.raises(ValueError, match="não existe"):
        _executar("proc.kill", {"pid": 999_999_999})


def test_proc_kill_recusa_sinal_nao_permitido() -> None:
    with pytest.raises(ValueError, match="não permitido"):
        _executar("proc.kill", {"pid": 1, "sinal": "SIGHUP"})


def test_terminal_exec_roda_binario_e_captura_saida() -> None:
    resultado = _executar("terminal.exec", {"comando": "echo", "argumentos": ["olá jarvis"]})

    assert resultado["codigo_saida"] == 0
    assert "olá jarvis" in resultado["saida"]


def test_terminal_exec_trunca_saida_grande() -> None:
    resultado = _executar(
        "terminal.exec", {"comando": "python3", "argumentos": ["-c", "print('x' * 10_000)"]}
    )

    assert len(resultado["saida"]) == 4000


def test_terminal_exec_timeout_levanta_excecao() -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        _executar(
            "terminal.exec", {"comando": "sleep", "argumentos": ["5"]}, timeout_segundos=1
        )


def test_terminal_exec_nao_usa_shell_entao_metacaracteres_sao_literais() -> None:
    resultado = _executar(
        "terminal.exec", {"comando": "echo", "argumentos": ["$(whoami)", "; ls"]}
    )

    assert "$(whoami)" in resultado["saida"]
    assert "; ls" in resultado["saida"]
