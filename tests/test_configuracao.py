from pathlib import Path

from jarvis.core.configuracao import (
    Configuracao,
    ConfiguracaoClaudeCli,
    ConfiguracaoComputador,
    ConfiguracaoVoz,
    carregar_configuracao,
)


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


def test_carregar_configuracao_sem_arquivo_usa_jail_paths_leitura_vazio(tmp_path: Path) -> None:
    configuracao = carregar_configuracao(tmp_path / "nao-existe.yaml")

    assert configuracao.seguranca.jail_paths_leitura == ()


def test_carregar_configuracao_le_jail_paths_leitura_do_arquivo(tmp_path: Path) -> None:
    caminho = tmp_path / "config.yaml"
    caminho.write_text(
        "seguranca:\n"
        "  jail_paths:\n"
        "    - ~/jarvis/workspace\n"
        "  jail_paths_leitura:\n"
        "    - /home/igor\n",
        encoding="utf-8",
    )

    configuracao = carregar_configuracao(caminho)

    assert configuracao.seguranca.jail_paths_leitura == (Path("/home/igor"),)


def test_carregar_configuracao_sem_arquivo_usa_padroes_de_voz(tmp_path: Path) -> None:
    configuracao = carregar_configuracao(tmp_path / "nao-existe.yaml")

    assert configuracao.voz == ConfiguracaoVoz()
    assert configuracao.voz.habilitada is False
    assert configuracao.voz.stt_modelo == "small"


def test_carregar_configuracao_le_secao_voz_do_arquivo(tmp_path: Path) -> None:
    caminho = tmp_path / "config.yaml"
    caminho.write_text(
        "voz:\n"
        "  habilitada: true\n"
        "  stt_modelo: medium\n"
        "  idioma: en\n"
        "  tts_voz: en_US-lessac-medium\n"
        "  duracao_captura_segundos: 4.5\n",
        encoding="utf-8",
    )

    configuracao = carregar_configuracao(caminho)

    assert configuracao.voz.habilitada is True
    assert configuracao.voz.stt_modelo == "medium"
    assert configuracao.voz.idioma == "en"
    assert configuracao.voz.tts_voz == "en_US-lessac-medium"
    assert configuracao.voz.duracao_captura_segundos == 4.5
    assert configuracao.voz.dispositivo == "auto"  # não especificado, mantém padrão


def test_carregar_configuracao_sem_arquivo_usa_padroes_de_computador(tmp_path: Path) -> None:
    configuracao = carregar_configuracao(tmp_path / "nao-existe.yaml")

    assert configuracao.computador == ConfiguracaoComputador()
    assert configuracao.computador.habilitada is False


def test_carregar_configuracao_le_secao_computador_do_arquivo(tmp_path: Path) -> None:
    caminho = tmp_path / "config.yaml"
    caminho.write_text("computador:\n  habilitada: true\n", encoding="utf-8")

    configuracao = carregar_configuracao(caminho)

    assert configuracao.computador.habilitada is True


def test_carregar_configuracao_sem_arquivo_usa_padroes_de_openai_compat(
    tmp_path: Path,
) -> None:
    configuracao = carregar_configuracao(tmp_path / "nao-existe.yaml")

    assert configuracao.openai_compat.base_url == "http://localhost:11434/v1"
    assert configuracao.openai_compat.modelo == "llama3"
    assert configuracao.openai_compat.api_key_env == ""
    assert configuracao.openai_compat.timeout_segundos == 120
    assert configuracao.openai_compat.max_tokens == 8192


def test_carregar_configuracao_le_secao_openai_compat_do_arquivo(tmp_path: Path) -> None:
    caminho = tmp_path / "config.yaml"
    caminho.write_text(
        "provedor:\n"
        "  openai_compat:\n"
        "    base_url: https://api.groq.com/openai/v1\n"
        "    modelo: llama-3.3-70b-versatile\n"
        "    api_key_env: GROQ_API_KEY\n"
        "    timeout_segundos: 45\n"
        "    max_tokens: 16384\n",
        encoding="utf-8",
    )

    configuracao = carregar_configuracao(caminho)

    assert configuracao.openai_compat.base_url == "https://api.groq.com/openai/v1"
    assert configuracao.openai_compat.modelo == "llama-3.3-70b-versatile"
    assert configuracao.openai_compat.api_key_env == "GROQ_API_KEY"
    assert configuracao.openai_compat.timeout_segundos == 45
    assert configuracao.openai_compat.max_tokens == 16384
