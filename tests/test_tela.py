import sys
from pathlib import Path

import pytest

from jarvis.io.tela import ErroCaptura, capturar_tela


def test_captura_tela_real_gera_arquivo_png(tmp_path: Path) -> None:
    caminho = capturar_tela(diretorio_destino=tmp_path)

    assert caminho.exists()
    assert caminho.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    caminho.unlink()


def test_erro_quando_binario_nao_existe(tmp_path: Path) -> None:
    with pytest.raises(ErroCaptura, match="não encontrado"):
        capturar_tela(diretorio_destino=tmp_path, binario="grim-que-nao-existe-de-verdade")


def test_erro_quando_binario_falha(tmp_path: Path) -> None:
    script_falho = tmp_path / "grim_falso.py"
    script_falho.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stderr.write('sem sessão wayland')\nsys.exit(1)\n",
        encoding="utf-8",
    )
    script_falho.chmod(0o755)

    with pytest.raises(ErroCaptura, match="sem sessão wayland"):
        capturar_tela(diretorio_destino=tmp_path, binario=str(script_falho))


def test_erro_apos_timeout(tmp_path: Path) -> None:
    script_lento = tmp_path / "grim_lento.py"
    script_lento.write_text(
        f"#!{sys.executable}\nimport time\ntime.sleep(2)\n",
        encoding="utf-8",
    )
    script_lento.chmod(0o755)

    with pytest.raises(ErroCaptura, match="não respondeu"):
        capturar_tela(diretorio_destino=tmp_path, binario=str(script_lento), timeout_segundos=1)
