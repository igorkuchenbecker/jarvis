import sys
from pathlib import Path

import pytest

from jarvis.io.janelas import ErroJanelas, Janela, listar_janelas


def test_listar_janelas_real_devolve_lista_com_formato_esperado() -> None:
    """Roda o hyprctl de verdade (sempre presente no alvo do projeto, sem side effects para
    'clients -j'/'activewindow -j') — mesmo espírito do teste real de captura de tela (M7)."""
    janelas = listar_janelas()

    assert isinstance(janelas, list)
    for janela in janelas:
        assert isinstance(janela, Janela)
        assert janela.endereco.startswith("0x")


def test_erro_quando_binario_nao_existe() -> None:
    with pytest.raises(ErroJanelas, match="não encontrado"):
        listar_janelas(binario="hyprctl-que-nao-existe-de-verdade")


def test_erro_quando_binario_falha(tmp_path: Path) -> None:
    script_falho = tmp_path / "hyprctl_falso.py"
    script_falho.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stderr.write('sem hyprland rodando')\nsys.exit(1)\n",
        encoding="utf-8",
    )
    script_falho.chmod(0o755)

    with pytest.raises(ErroJanelas, match="sem hyprland rodando"):
        listar_janelas(binario=str(script_falho))


def test_erro_com_saida_json_invalida(tmp_path: Path) -> None:
    script_ruim = tmp_path / "hyprctl_ruim.py"
    script_ruim.write_text(
        f"#!{sys.executable}\nprint('isso nao e json')\n",
        encoding="utf-8",
    )
    script_ruim.chmod(0o755)

    with pytest.raises(ErroJanelas, match="saída inesperada"):
        listar_janelas(binario=str(script_ruim))


def test_erro_apos_timeout(tmp_path: Path) -> None:
    script_lento = tmp_path / "hyprctl_lento.py"
    script_lento.write_text(
        f"#!{sys.executable}\nimport time\ntime.sleep(2)\n",
        encoding="utf-8",
    )
    script_lento.chmod(0o755)

    with pytest.raises(ErroJanelas, match="não respondeu"):
        listar_janelas(binario=str(script_lento), timeout_segundos=1)


def test_marca_janela_ativa_quando_disponivel(tmp_path: Path) -> None:
    """hyprctl é chamado 2x (clients -j, activewindow -j) — um script falso que responde
    diferente conforme o argumento simula isso sem depender do estado real da sessão."""
    script = tmp_path / "hyprctl_script.py"
    script.write_text(
        f"""#!{sys.executable}
import sys, json
if "activewindow" in sys.argv:
    print(json.dumps({{"address": "0x2"}}))
else:
    print(json.dumps([
        {{"address": "0x1", "class": "a", "title": "A", "workspace": {{"name": "1"}}}},
        {{"address": "0x2", "class": "b", "title": "B", "workspace": {{"name": "1"}}}},
    ]))
""",
        encoding="utf-8",
    )
    script.chmod(0o755)

    janelas = listar_janelas(binario=str(script))

    assert [j.ativa_no_momento for j in janelas] == [False, True]
