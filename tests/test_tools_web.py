"""Testes das ferramentas pesquisar/web.buscar: SB-primeiro, fallback web, executor."""

from __future__ import annotations

from pathlib import Path

from jarvis.io.web import ErroBuscaWeb
from jarvis.memory.conhecimento import RepositorioConhecimento
from jarvis.security.executor import Acao, Executor
from jarvis.tools.base import Ferramenta, NivelRisco
from jarvis.tools.registro import RegistroFerramentas
from jarvis.tools.web import criar_ferramentas_pesquisa


def _repositorio_com_conteudo(tmp_path: Path) -> RepositorioConhecimento:
    repositorio = RepositorioConhecimento(tmp_path / "conhecimento.db")
    arquivo = tmp_path / "notas.md"
    arquivo.write_text(
        "# Banco de dados\n\nSQLite guarda os dados em arquivos e usa FTS5 para busca.\n",
        encoding="utf-8",
    )
    repositorio.ingerir_arquivo(arquivo)
    return repositorio


def _repositorio_vazio(tmp_path: Path) -> RepositorioConhecimento:
    return RepositorioConhecimento(tmp_path / "conhecimento.db")


class AbrirFalso:
    """Dublê do transporte de rede: devolve HTML roteirizado (ou falha, se configurado)."""

    def __init__(self, html: str = "", falhar: bool = False) -> None:
        self._html = html
        self._falhar = falhar
        self.chamadas: list[tuple[str, int]] = []

    def __call__(self, url: str, timeout: int) -> str:
        self.chamadas.append((url, timeout))
        if self._falhar:
            raise ErroBuscaWeb("não consegui alcançar o DuckDuckGo: rede fora")
        return self._html


def _html_web() -> str:
    return (
        '<div class="results">'
        '<a rel="nofollow" class="result__a" '
        'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexterno.com%2Fartigo&amp;rut=1">'
        "Artigo externo</a>"
        '<a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexterno.com%2F'
        'artigo">Conteúdo de fora do Second Brain.</a>'
        "</div>"
    )


def _por_nome(
    repositorio: RepositorioConhecimento, abrir: AbrirFalso
) -> dict[str, Ferramenta]:
    return {f.nome: f for f in criar_ferramentas_pesquisa(repositorio, abrir=abrir)}


def _executor(tmp_path: Path, abrir: AbrirFalso) -> Executor:
    registro = RegistroFerramentas()
    for ferramenta in criar_ferramentas_pesquisa(
        _repositorio_com_conteudo(tmp_path), abrir=abrir
    ):
        registro.registrar(ferramenta)
    return Executor(registro, jail_paths=[tmp_path], nivel_autonomia=2)


def test_cria_as_duas_ferramentas_com_risco_read_only(tmp_path: Path) -> None:
    ferramentas = _por_nome(_repositorio_vazio(tmp_path), AbrirFalso())

    assert set(ferramentas) == {"pesquisar", "web.buscar"}
    for ferramenta in ferramentas.values():
        assert ferramenta.risco == NivelRisco.READ_ONLY


def test_pesquisar_usa_o_second_brain_e_nao_chama_a_web(tmp_path: Path) -> None:
    abrir = AbrirFalso(html=_html_web(), falhar=True)
    ferramentas = _por_nome(_repositorio_com_conteudo(tmp_path), abrir)

    resultado = ferramentas["pesquisar"].executar({"consulta": "sqlite"})

    assert isinstance(resultado, list)
    assert resultado and resultado[0].startswith("[notas.md § Banco de dados]:")
    assert "FTS5" in resultado[0]
    assert abrir.chamadas == []


def test_pesquisar_cai_na_web_quando_o_second_brain_nao_responde(tmp_path: Path) -> None:
    abrir = AbrirFalso(html=_html_web())
    ferramentas = _por_nome(_repositorio_vazio(tmp_path), abrir)

    resultado = ferramentas["pesquisar"].executar({"consulta": "algo novo"})

    assert abrir.chamadas, "web não foi consultada mesmo sem resultado local"
    assert isinstance(resultado, list)
    assert resultado and "web:" in resultado[0]
    assert "externo.com/artigo" in resultado[0]


def test_web_buscar_formata_titulo_url_e_trecho(tmp_path: Path) -> None:
    abrir = AbrirFalso(html=_html_web())
    ferramentas = _por_nome(_repositorio_vazio(tmp_path), abrir)

    resultado = ferramentas["web.buscar"].executar({"consulta": "algo novo"})

    assert isinstance(resultado, list)
    assert resultado[0].startswith("web: Artigo externo — https://externo.com/artigo.")


def test_executor_permite_pesquisar_no_nivel_de_autonomia_2(tmp_path: Path) -> None:
    executor = _executor(tmp_path, AbrirFalso(html=_html_web()))

    resultado = executor.executar_acao(Acao("pesquisar", {"consulta": "sqlite"}))

    assert resultado.sucesso
    assert isinstance(resultado.valor, list)


def test_executor_recusa_pesquisa_sem_consulta(tmp_path: Path) -> None:
    executor = _executor(tmp_path, AbrirFalso())

    resultado = executor.executar_acao(Acao("pesquisar", {}))

    assert not resultado.sucesso
    assert "consulta" in (resultado.erro or "")


def test_erro_de_rede_vira_mensagem_amigavel_sem_falhar(tmp_path: Path) -> None:
    executor = _executor(tmp_path, AbrirFalso(falhar=True))

    resultado = executor.executar_acao(Acao("pesquisar", {"consulta": "algo novo"}))

    assert resultado.sucesso
    assert isinstance(resultado.valor, list)
    assert resultado.valor and "web indisponível" in resultado.valor[0]


def test_pesquisar_sem_rede_e_sem_conteudo_local_menciona_o_second_brain(tmp_path: Path) -> None:
    ferramentas = _por_nome(_repositorio_vazio(tmp_path), AbrirFalso(falhar=True))

    resultado = ferramentas["pesquisar"].executar({"consulta": "algo novo"})

    assert isinstance(resultado, list)
    assert resultado and "web indisponível" in resultado[0]


def test_web_buscar_sem_rede_e_amigavel(tmp_path: Path) -> None:
    ferramentas = _por_nome(_repositorio_vazio(tmp_path), AbrirFalso(falhar=True))

    resultado = ferramentas["web.buscar"].executar({"consulta": "algo novo"})

    assert isinstance(resultado, list)
    assert resultado and "web indisponível" in resultado[0]