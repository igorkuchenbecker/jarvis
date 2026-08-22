"""Testes do ClaudeCliProvider usando um executável falso no lugar da CLI real.

Nenhum destes testes toca rede, custa dinheiro ou depende do binário `claude` de verdade — o
"claude" chamado aqui é um script Python de fixture que só ecoa o que recebeu, no espírito de
"zero rede nos testes" do projeto.
"""

import json
import sys
import time
from pathlib import Path

import pytest

from jarvis.providers.base import ErroProvider
from jarvis.providers.claude_cli import ClaudeCliProvider

CORPO_CLAUDE_FALSO = """\
import json
import os
import sys

argv = sys.argv[1:]
mensagem = argv[-1] if argv else ""

log_caminho = os.environ.get("JARVIS_TESTE_LOG")
if log_caminho:
    with open(log_caminho, "a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(argv) + "\\n")

demora = os.environ.get("JARVIS_TESTE_DEMORA")
if demora:
    import time as _time
    _time.sleep(float(demora))

if os.environ.get("JARVIS_TESTE_EXIT_NAO_ZERO"):
    sys.stderr.write("falha simulada\\n")
    sys.exit(1)

if os.environ.get("JARVIS_TESTE_SAIDA_INVALIDA"):
    print("isso não é json")
    sys.exit(0)

sessao_id = None
if "--session-id" in argv:
    sessao_id = argv[argv.index("--session-id") + 1]
elif "--resume" in argv:
    sessao_id = argv[argv.index("--resume") + 1]

if os.environ.get("JARVIS_TESTE_ERRO"):
    print(json.dumps({"is_error": True, "result": "algo deu errado", "session_id": sessao_id}))
    sys.exit(0)

print(json.dumps({"is_error": False, "result": f"eco: {mensagem}", "session_id": sessao_id}))
"""


@pytest.fixture
def claude_falso(tmp_path: Path) -> Path:
    caminho = tmp_path / "claude_falso.py"
    caminho.write_text(f"#!{sys.executable}\n{CORPO_CLAUDE_FALSO}", encoding="utf-8")
    caminho.chmod(0o755)
    return caminho


def _ler_chamadas(caminho_log: Path) -> list[list[str]]:
    if not caminho_log.exists():
        return []
    linhas = caminho_log.read_text(encoding="utf-8").splitlines()
    return [json.loads(linha) for linha in linhas]


def test_levanta_erro_quando_binario_nao_existe() -> None:
    provider = ClaudeCliProvider(binario="jarvis-claude-que-nao-existe-de-verdade")

    with pytest.raises(ErroProvider, match="não encontrado"):
        provider.enviar("oi")


def test_envia_mensagem_e_recebe_resposta(claude_falso: Path) -> None:
    provider = ClaudeCliProvider(binario=str(claude_falso))

    resposta = provider.enviar("qual é a capital do brasil?")

    assert resposta == "eco: qual é a capital do brasil?"


def test_primeira_chamada_usa_session_id_e_segunda_usa_resume(
    tmp_path: Path, claude_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caminho_log = tmp_path / "chamadas.jsonl"
    monkeypatch.setenv("JARVIS_TESTE_LOG", str(caminho_log))
    provider = ClaudeCliProvider(binario=str(claude_falso))

    provider.enviar("primeira mensagem")
    provider.enviar("segunda mensagem")

    chamadas = _ler_chamadas(caminho_log)
    assert "--session-id" in chamadas[0]
    assert "--resume" in chamadas[1]

    sessao_primeira = chamadas[0][chamadas[0].index("--session-id") + 1]
    sessao_segunda = chamadas[1][chamadas[1].index("--resume") + 1]
    assert sessao_primeira == sessao_segunda


def test_reiniciar_gera_nova_sessao(
    tmp_path: Path, claude_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caminho_log = tmp_path / "chamadas.jsonl"
    monkeypatch.setenv("JARVIS_TESTE_LOG", str(caminho_log))
    provider = ClaudeCliProvider(binario=str(claude_falso))

    provider.enviar("primeira mensagem")
    provider.reiniciar()
    provider.enviar("mensagem após reiniciar")

    chamadas = _ler_chamadas(caminho_log)
    sessao_primeira = chamadas[0][chamadas[0].index("--session-id") + 1]
    assert "--session-id" in chamadas[1]
    sessao_depois_de_reiniciar = chamadas[1][chamadas[1].index("--session-id") + 1]
    assert sessao_primeira != sessao_depois_de_reiniciar


def test_levanta_erro_quando_cli_retorna_is_error(
    claude_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JARVIS_TESTE_ERRO", "1")
    provider = ClaudeCliProvider(binario=str(claude_falso))

    with pytest.raises(ErroProvider, match="algo deu errado"):
        provider.enviar("oi")


def test_levanta_erro_quando_saida_nao_e_json(
    claude_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JARVIS_TESTE_SAIDA_INVALIDA", "1")
    provider = ClaudeCliProvider(binario=str(claude_falso))

    with pytest.raises(ErroProvider, match="resposta inesperada"):
        provider.enviar("oi")


def test_levanta_erro_quando_exit_code_nao_zero(
    claude_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JARVIS_TESTE_EXIT_NAO_ZERO", "1")
    provider = ClaudeCliProvider(binario=str(claude_falso))

    with pytest.raises(ErroProvider, match="falha simulada"):
        provider.enviar("oi")


def test_levanta_erro_apos_timeout(claude_falso: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_TESTE_DEMORA", "2")
    provider = ClaudeCliProvider(binario=str(claude_falso), timeout_segundos=1)

    inicio = time.monotonic()
    with pytest.raises(ErroProvider, match="não respondeu"):
        provider.enviar("oi")
    assert time.monotonic() - inicio < 2
