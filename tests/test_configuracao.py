from pathlib import Path

from jarvis.core.configuracao import Configuracao, ConfiguracaoClaudeCli, carregar_configuracao


def test_carregar_configuracao_sem_arquivo_usa_padroes(tmp_path: Path) -> None:
    configuracao = carregar_configuracao(tmp_path / "nao-existe.yaml")

    assert configuracao == Configuracao()
    assert configuracao.llm_padrao == "claude_cli"
    assert configuracao.claude_cli == ConfiguracaoClaudeCli(binario="claude", timeout_segundos=120)


def test_carregar_configuracao_le_valores_do_arquivo(tmp_path: Path) -> None:
    caminho = tmp_path / "config.yaml"
    caminho.write_text(
        "provedor:\n"
        "  llm_padrao: claude_cli\n"
        "  claude_cli:\n"
        "    binario: /usr/local/bin/claude\n"
        "    timeout_segundos: 30\n",
        encoding="utf-8",
    )

    configuracao = carregar_configuracao(caminho)

    assert configuracao.claude_cli.binario == "/usr/local/bin/claude"
    assert configuracao.claude_cli.timeout_segundos == 30


def test_carregar_configuracao_arquivo_vazio_usa_padroes(tmp_path: Path) -> None:
    caminho = tmp_path / "config.yaml"
    caminho.write_text("", encoding="utf-8")

    assert carregar_configuracao(caminho) == Configuracao()


def test_carregar_configuracao_secao_parcial_usa_padroes_para_o_resto(tmp_path: Path) -> None:
    caminho = tmp_path / "config.yaml"
    caminho.write_text("provedor:\n  llm_padrao: fake\n", encoding="utf-8")

    configuracao = carregar_configuracao(caminho)

    assert configuracao.llm_padrao == "fake"
    assert configuracao.claude_cli.binario == "claude"
