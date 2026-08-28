"""Testes das ferramentas de autoconhecimento e automanutenção (auto.*).

Cobrem leitura (auto.info, auto.mudancas), execução real das funções de alteração
(auto.atualizar, auto.editar) com subprocessos fictícios, o confinamento dos caminhos ao
repositório do JARVIS e a exigência de aprovação humana (HIGH/CRITICAL) exercida pelo Executor.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from jarvis.core.configuracao import Configuracao, ConfiguracaoOpenAiCompat
from jarvis.security.executor import Acao, Executor
from jarvis.tools import autor
from jarvis.tools.autor import criar_ferramentas_autoconsciencia
from jarvis.tools.registro import RegistroFerramentas


def _ferramentas(configuracao: Configuracao | None = None) -> dict[str, Any]:
    return {f.nome: f for f in criar_ferramentas_autoconsciencia(configuracao or Configuracao())}


def _git_falso(saidas: dict[tuple[str, ...], tuple[int, str, str]]) -> Callable[..., Any]:
    def _falso(argumentos: list[str], timeout_segundos: int = 90) -> tuple[int, str, str]:
        comando = tuple(argumentos[:2])
        if comando in saidas:
            return saidas[comando]
        return 0, "", ""

    return _falso


def test_auto_info_claude_cli_padrao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)
    ferramentas = _ferramentas()

    resultado = ferramentas["auto.info"].executar({})

    assert resultado["provedor"] == "claude_cli"
    assert resultado["detalhe_provedor"] == {"binario": "claude"}
    assert isinstance(resultado["versao"], str) and resultado["versao"]
    assert resultado["git"] is None


def test_auto_info_openai_compat_detalha_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    configuracao = Configuracao(
        llm_padrao="openai_compat",
        openai_compat=ConfiguracaoOpenAiCompat(base_url="http://127.0.0.1:11434/v1", modelo="mm"),
    )
    ferramentas = _ferramentas(configuracao)

    sem_chave = ferramentas["auto.info"].executar({})
    assert sem_chave["provedor"] == "openai_compat"
    assert sem_chave["detalhe_provedor"]["api_key_definida"] is False

    monkeypatch.setenv("CHAVE_FAKE", "valor")
    configuracao = Configuracao(
        llm_padrao="openai_compat",
        openai_compat=ConfiguracaoOpenAiCompat(api_key_env="CHAVE_FAKE"),
    )
    ferramentas = _ferramentas(configuracao)
    assert ferramentas["auto.info"].executar({})["detalhe_provedor"]["api_key_definida"] is True


def test_auto_info_inclui_estado_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)
    monkeypatch.setattr(
        autor,
        "_git",
        _git_falso(
            {
                ("rev-parse", "--abbrev-ref"): (0, "main\n", ""),
                ("log", "-1"): (0, "a1b2c3|2026-08-28T10:00:00+00:00|atualiza docs\n", ""),
                ("status", "--porcelain"): (0, " M config.yaml\n", ""),
            }
        ),
    )

    resultado = _ferramentas()["auto.info"].executar({})

    assert resultado["git"]["branch"] == "main"
    assert resultado["git"]["head"] == "a1b2c3"
    assert resultado["git"]["arquivos_nao_commitados"] == [" M config.yaml"]


def test_auto_mudancas_parseia_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        autor,
        "_git",
        _git_falso(
            {
                ("log", "-10"): (
                    0,
                    "abc123|2026-08-28T10:00:00+00:00|adiciona modo 100% local (Ollama)\n"
                    "def456|2026-08-27T09:00:00+00:00|implementa busca web sem chave\n",
                    "",
                )
            }
        ),
    )

    resultado = _ferramentas()["auto.mudancas"].executar({})

    assert len(resultado) == 2
    assert resultado[0]["hash"] == "abc123"
    assert resultado[0]["mensagem"] == "adiciona modo 100% local (Ollama)"
    assert resultado[1]["hash"] == "def456"


def test_auto_mudancas_respeita_limite(monkeypatch: pytest.MonkeyPatch) -> None:
    chamados: list[list[str]] = []

    def _grab(argumentos: list[str], timeout_segundos: int = 90) -> tuple[int, str, str]:
        chamados.append(argumentos)
        return 0, "a1|2026-08-28T00:00:00+00:00|um\n", ""

    monkeypatch.setattr(autor, "_git", _grab)
    ferramentas = _ferramentas()

    ferramentas["auto.mudancas"].executar({"limite": 2})
    ferramentas["auto.mudancas"].executar({"limite": 99})

    assert chamados[0][1] == "-2"
    assert chamados[1][1] == "-50"


def test_auto_mudancas_falha_no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        autor, "_git", _git_falso({("log", "-10"): (128, "", "fatal: not a git repository")})
    )

    with pytest.raises(ValueError, match="fatal"):
        _ferramentas()["auto.mudancas"].executar({})


def test_auto_editar_escreve_e_relata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)
    caminho = "src/jarvis/tools/novo.py"

    resultado = _ferramentas()["auto.editar"].executar(
        {"caminho": caminho, "conteudo": "def nova():\n    pass\n"}
    )

    assert (tmp_path / caminho).read_text("utf-8") == "def nova():\n    pass\n"
    assert "novo.py" in resultado


def test_auto_editar_recusa_caminho_fora_do_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)

    with pytest.raises(ValueError, match="fora do repositório"):
        _ferramentas()["auto.editar"].executar({"caminho": "/tmp/fora.py", "conteudo": "x"})


def test_auto_editar_recusa_dentro_do_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)

    with pytest.raises(ValueError, match="\\.git"):
        _ferramentas()["auto.editar"].executar({"caminho": ".git/config", "conteudo": "x"})


def test_auto_editar_rollback_restaura_e_remove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)
    arquivo = "src/jarvis/tools/existente.py"
    destino = tmp_path / arquivo
    destino.parent.mkdir(parents=True)
    destino.write_text("original")

    ferramenta = _ferramentas()["auto.editar"]
    argumentos = {"caminho": arquivo, "conteudo": "novo"}

    estado = ferramenta.capturar_estado(argumentos)
    ferramenta.executar(argumentos)
    assert destino.read_text("utf-8") == "novo"
    ferramenta.reverter(argumentos, estado)
    assert destino.read_text("utf-8") == "original"

    argumentos_novo = {"caminho": "src/jarvis/novo2.py", "conteudo": "x"}
    estado_novo = ferramenta.capturar_estado(argumentos_novo)
    ferramenta.executar(argumentos_novo)
    assert (tmp_path / "src/jarvis/novo2.py").exists()
    ferramenta.reverter(argumentos_novo, estado_novo)
    assert not (tmp_path / "src/jarvis/novo2.py").exists()


def test_auto_atualizar_bloqueia_com_mudancas_locais(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)
    monkeypatch.setattr(
        autor, "_git", _git_falso({("status", "--porcelain"): (0, " M config.yaml\n", "")})
    )

    resultado = _ferramentas()["auto.atualizar"].executar({})

    assert resultado["atualizado"] is False
    assert "commit" in resultado["motivo"]
    assert resultado["arquivos_nao_commitados"] == [" M config.yaml"]


def test_auto_atualizar_fetch_falha_sem_internet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)
    monkeypatch.setattr(
        autor,
        "_git",
        _git_falso(
            {
                ("status", "--porcelain"): (0, "", ""),
                ("fetch", "origin"): (128, "", "fatal: unable to access '...'"),
            }
        ),
    )

    resultado = _ferramentas()["auto.atualizar"].executar({})

    assert resultado["atualizado"] is False
    assert "sem internet" in resultado["motivo"]


def test_auto_atualizar_ja_atualizado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)
    monkeypatch.setattr(
        autor,
        "_git",
        _git_falso(
            {
                ("status", "--porcelain"): (0, "", ""),
                ("fetch", "origin"): (0, "", ""),
                ("rev-parse", "--abbrev-ref"): (0, "main\n", ""),
                ("rev-list", "--count"): (0, "0\n", ""),
            }
        ),
    )
    chamadas_rodar: list[list[str]] = []

    def _rodar_falso(comando: list[str], timeout_segundos: int) -> tuple[int, str, str]:
        chamadas_rodar.append(comando)
        return 0, "ok\n", ""

    monkeypatch.setattr(autor, "_rodar", _rodar_falso)

    resultado = _ferramentas()["auto.atualizar"].executar({})

    assert resultado["atualizado"] is True
    assert resultado["verificacao"] == "verde"
    assert len(resultado["passos"]) == 4
    assert resultado["passos"][1]["detalhe"] == "já atualizado"
    assert chamadas_rodar[0][1:5] == ["-m", "pip", "install", "--no-build-isolation"]
    assert chamadas_rodar[1][0] == "bash"


def test_auto_atualizar_aplica_pull_quando_atrasado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)
    monkeypatch.setattr(
        autor,
        "_git",
        _git_falso(
            {
                ("status", "--porcelain"): (0, "", ""),
                ("fetch", "origin"): (0, "", ""),
                ("rev-parse", "--abbrev-ref"): (0, "main\n", ""),
                ("rev-list", "--count"): (0, "3\n", ""),
                ("pull", "--ff-only"): (0, "3 arquivos alterados\n", ""),
            }
        ),
    )
    monkeypatch.setattr(autor, "_rodar", lambda comando, timeout_segundos: (0, "ok\n", ""))

    resultado = _ferramentas()["auto.atualizar"].executar({})

    assert resultado["atualizado"] is True
    assert resultado["passos"][1]["passo"] == "git pull --ff-only origin main"


def test_auto_commit_faz_add_e_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)
    chamados: list[list[str]] = []

    def _git_commit(argumentos: list[str], timeout_segundos: int = 90) -> tuple[int, str, str]:
        chamados.append(argumentos)
        if argumentos[0] == "add":
            return 0, "", ""
        if argumentos[0] == "commit":
            return 0, "", ""
        if argumentos[0] == "log":
            return 0, "cafe123 refatora loops\n", ""
        return 0, "", ""

    monkeypatch.setattr(autor, "_git", _git_commit)

    resultado = _ferramentas()["auto.commit"].executar({"mensagem": "ajusta ferramenta"})

    assert chamados[0] == ["add", "-A"]
    assert chamados[1][:3] == ["commit", "-m", "ajusta ferramenta"]
    assert resultado["commit"] == "cafe123 refatora loops"
    assert resultado["mensagem"] == "ajusta ferramenta"


def test_auto_commit_recusa_mensagem_vazia() -> None:
    with pytest.raises(ValueError, match="vazia"):
        _ferramentas()["auto.commit"].executar({"mensagem": "   "})


def test_auto_atualizar_sem_aprovacao_e_recusado_por_padrao(
    tmp_path: Path,
) -> None:
    registro = RegistroFerramentas()
    for ferramenta in criar_ferramentas_autoconsciencia(Configuracao()):
        registro.registrar(ferramenta)
    executor = Executor(registro, jail_paths=[tmp_path], nivel_autonomia=5)

    argumentos_por_nome = {
        "auto.atualizar": {},
        "auto.editar": {"caminho": "x.py", "conteudo": "y"},
        "auto.commit": {"mensagem": "m"},
    }
    for nome, argumentos in argumentos_por_nome.items():
        resultado = executor.executar_acao(Acao(nome, argumentos))

        assert not resultado.sucesso
        assert "aprovação" in (resultado.erro or "")


def test_auto_atualizar_roda_com_aprovacao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(autor, "RAIZ_JARVIS_PADRAO", tmp_path)
    monkeypatch.setattr(
        autor,
        "_git",
        _git_falso(
            {
                ("status", "--porcelain"): (0, "", ""),
                ("fetch", "origin"): (0, "", ""),
                ("rev-parse", "--abbrev-ref"): (0, "main\n", ""),
                ("rev-list", "--count"): (0, "0\n", ""),
            }
        ),
    )
    monkeypatch.setattr(autor, "_rodar", lambda comando, timeout_segundos: (0, "ok\n", ""))

    registro = RegistroFerramentas()
    for ferramenta in criar_ferramentas_autoconsciencia(Configuracao()):
        registro.registrar(ferramenta)
    executor = Executor(
        registro,
        jail_paths=[tmp_path],
        nivel_autonomia=5,
        solicitar_aprovacao=lambda acao, ferramenta: True,
    )

    resultado = executor.executar_acao(Acao("auto.atualizar", {}))

    assert resultado.sucesso
    assert resultado.valor["atualizado"] is True


def test_auto_editar_schema_invalido_e_recusado_pelo_executor(tmp_path: Path) -> None:
    registro = RegistroFerramentas()
    for ferramenta in criar_ferramentas_autoconsciencia(Configuracao()):
        registro.registrar(ferramenta)
    executor = Executor(
        registro,
        jail_paths=[tmp_path],
        solicitar_aprovacao=lambda acao, ferramenta: True,
    )

    resultado = executor.executar_acao(Acao("auto.editar", {"caminho": "x.py"}))

    assert not resultado.sucesso
    assert "conteudo" in (resultado.erro or "")