from pathlib import Path

import pytest

from jarvis.security.jail import ErroForaDoJail, resolver_dentro_do_jail


def test_aceita_caminho_dentro_do_jail(tmp_path: Path) -> None:
    arquivo = tmp_path / "notas.txt"

    resolvido = resolver_dentro_do_jail(str(arquivo), [tmp_path])

    assert resolvido == arquivo.resolve()


def test_aceita_subdiretorio_do_jail(tmp_path: Path) -> None:
    subdiretorio = tmp_path / "sub" / "arquivo.txt"

    resolvido = resolver_dentro_do_jail(str(subdiretorio), [tmp_path])

    assert resolvido == subdiretorio.resolve()


def test_recusa_travessia_para_fora_do_jail(tmp_path: Path) -> None:
    caminho_malicioso = str(tmp_path / ".." / "fora.txt")

    with pytest.raises(ErroForaDoJail):
        resolver_dentro_do_jail(caminho_malicioso, [tmp_path])


def test_recusa_caminho_absoluto_fora_do_jail(tmp_path: Path) -> None:
    with pytest.raises(ErroForaDoJail):
        resolver_dentro_do_jail("/etc/passwd", [tmp_path])


def test_recusa_symlink_que_escapa_do_jail(tmp_path: Path) -> None:
    fora_do_jail = tmp_path.parent / "arquivo_fora_do_jail_teste.txt"
    fora_do_jail.write_text("segredo")
    jail = tmp_path / "workspace"
    jail.mkdir()
    link = jail / "atalho"
    link.symlink_to(fora_do_jail)

    try:
        with pytest.raises(ErroForaDoJail):
            resolver_dentro_do_jail(str(link), [jail])
    finally:
        fora_do_jail.unlink()
