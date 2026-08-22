"""Testes do ClaudeCliVisionProvider com um executável 'claude' falso — nenhum toca a CLI real
nem custa dinheiro, no mesmo espírito de tests/test_providers_claude_cli.py.
"""

import json
import sys
from pathlib import Path

import pytest

from jarvis.providers.base import ErroProvider
from jarvis.providers.claude_cli import ClaudeCliVisionProvider

CORPO_CLAUDE_VISAO_FALSO = """\
import json
import os
import sys

entrada_stdin = sys.stdin.read()

log_caminho = os.environ.get("JARVIS_TESTE_LOG")
if log_caminho:
    with open(log_caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(entrada_stdin)

if os.environ.get("JARVIS_TESTE_ERRO"):
    print(json.dumps({"is_error": True, "result": "falha simulada"}))
    sys.exit(0)

print(json.dumps({"type": "system", "subtype": "init"}))
print(json.dumps({"is_error": False, "result": "há um gato dormindo no teclado"}))
"""


@pytest.fixture
def claude_visao_falso(tmp_path: Path) -> Path:
    caminho = tmp_path / "claude_visao_falso.py"
    caminho.write_text(f"#!{sys.executable}\n{CORPO_CLAUDE_VISAO_FALSO}", encoding="utf-8")
    caminho.chmod(0o755)
    return caminho


@pytest.fixture
def imagem_png_minima(tmp_path: Path) -> Path:
    caminho = tmp_path / "captura.png"
    caminho.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    return caminho


def test_analisar_retorna_resultado_da_ultima_linha(
    claude_visao_falso: Path, imagem_png_minima: Path
) -> None:
    provider = ClaudeCliVisionProvider(binario=str(claude_visao_falso))

    resposta = provider.analisar(imagem_png_minima, "o que tem na tela?")

    assert resposta == "há um gato dormindo no teclado"


def test_analisar_envia_imagem_em_base64_no_stdin(
    tmp_path: Path,
    claude_visao_falso: Path,
    imagem_png_minima: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caminho_log = tmp_path / "stdin_recebido.json"
    monkeypatch.setenv("JARVIS_TESTE_LOG", str(caminho_log))
    provider = ClaudeCliVisionProvider(binario=str(claude_visao_falso))

    provider.analisar(imagem_png_minima, "descreva")

    mensagem_recebida = json.loads(caminho_log.read_text(encoding="utf-8"))
    blocos = mensagem_recebida["message"]["content"]
    bloco_texto = next(b for b in blocos if b["type"] == "text")
    bloco_imagem = next(b for b in blocos if b["type"] == "image")

    assert bloco_texto["text"] == "descreva"
    assert bloco_imagem["source"]["media_type"] == "image/png"
    assert len(bloco_imagem["source"]["data"]) > 0


def test_recusa_formato_de_imagem_nao_suportado(
    claude_visao_falso: Path, tmp_path: Path
) -> None:
    caminho_gif = tmp_path / "captura.gif"
    caminho_gif.write_bytes(b"GIF89a")
    provider = ClaudeCliVisionProvider(binario=str(claude_visao_falso))

    with pytest.raises(ErroProvider, match="não suportado"):
        provider.analisar(caminho_gif, "descreva")


def test_levanta_erro_quando_cli_retorna_is_error(
    claude_visao_falso: Path, imagem_png_minima: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JARVIS_TESTE_ERRO", "1")
    provider = ClaudeCliVisionProvider(binario=str(claude_visao_falso))

    with pytest.raises(ErroProvider, match="falha simulada"):
        provider.analisar(imagem_png_minima, "descreva")


def test_levanta_erro_quando_binario_nao_existe(imagem_png_minima: Path) -> None:
    provider = ClaudeCliVisionProvider(binario="jarvis-claude-visao-que-nao-existe")

    with pytest.raises(ErroProvider, match="não encontrado"):
        provider.analisar(imagem_png_minima, "descreva")
