"""Testes do transporte de busca na web (DuckDuckGo) — HTML falso injetado, zero rede."""

from __future__ import annotations

import pytest

from jarvis.io.web import (
    ErroBuscaWeb,
    _decodificar_url_do_link_duck,
    buscar_web,
)


def _resultado_ddg(titulo: str, url: str, trecho: str = "") -> str:
    """Monta o bloco de um resultado orgânico igual ao que o DuckDuckGo emite."""
    import urllib.parse

    alvo = urllib.parse.quote(url, safe="")
    sipnete = (
        f'<a class="result__snippet" href="//duckduckgo.com/l/?uddg={alvo}">'
        f"{trecho}</a>"
        if trecho
        else ""
    )
    return (
        '<div class="result results_links results_links_deep web-result ">'
        f'<a rel="nofollow" class="result__a" '
        f'href="//duckduckgo.com/l/?uddg={alvo}&amp;rut=abc">{titulo}</a>'
        f"{sipnete}</div>"
    )


def _pagina_simples() -> str:
    return (
        '<html><div class="results">'
        + _resultado_ddg(
            "Primeiro Resultado",
            "https://exemplo.com/pagina?a=1&b=2",
            "Trecho do primeiro resultado com mais texto.",
        )
        + _resultado_ddg("Segundo Resultado", "https://exemplo.com/outro", "")
        + "</div></html>"
    )


class AbrirFalso:
    """Dublê do transporte de rede: registra chamadas e devolve HTML roteirizado."""

    def __init__(self, html: str) -> None:
        self._html = html
        self.chamadas: list[tuple[str, int]] = []

    def __call__(self, url: str, timeout: int) -> str:
        self.chamadas.append((url, timeout))
        return self._html


def test_decodifica_link_organico() -> None:
    link = (
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexemplo.com%2Fpagina%3Fa%3D1%26b%3D2"
        "&rut=6f87e3c4"
    )
    assert _decodificar_url_do_link_duck(link) == "https://exemplo.com/pagina?a=1&b=2"


def test_decodifica_descarta_anuncio() -> None:
    assert _decodificar_url_do_link_duck("//duckduckgo.com/y.js?ad_type=1") is None
    assert _decodificar_url_do_link_duck("//duckduckgo.com/l/?rut=abc") is None
    assert _decodificar_url_do_link_duck("https://externo.com/direto") is None
    anuncio = (
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fduckduckgo.com%2Fy.js%3Fad_domain%3D"
        "airbnb.com.br%26ad_type%3Dtxad&rut=x"
    )
    assert _decodificar_url_do_link_duck(anuncio) is None


def test_buscar_web_extrai_titulo_url_e_trecho() -> None:
    abrir = AbrirFalso(_pagina_simples())

    resultados = buscar_web("exemplo", abrir=abrir)

    assert [r.url for r in resultados] == [
        "https://exemplo.com/pagina?a=1&b=2",
        "https://exemplo.com/outro",
    ]
    assert resultados[0].titulo == "Primeiro Resultado"
    assert resultados[0].trecho == "Trecho do primeiro resultado com mais texto."
    assert resultados[1].trecho == ""


def test_buscar_web_limita_quantidade_de_resultados() -> None:
    abrir = AbrirFalso(_pagina_simples())

    resultados = buscar_web("exemplo", limite=1, abrir=abrir)

    assert len(resultados) == 1


def test_buscar_web_monta_url_com_a_consulta() -> None:
    abrir = AbrirFalso(_pagina_simples())

    buscar_web("sqlite fts5", abrir=abrir)

    url, timeout = abrir.chamadas[0]
    assert url.startswith("https://html.duckduckgo.com/html/?q=")
    assert "sqlite" in url
    assert timeout == 15


def test_buscar_web_colapsa_espacos_e_descarta_blocos_invalidos() -> None:
    pagina = (
        '<div class="results">'
        + _resultado_ddg(
            "Título\n com  quebras", "https://exemplo.com/espaco", "trecho  com    espacos"
        )
        + '<div class="result"><a class="result__a" href="//duckduckgo.com/y.js?ad=1">'
        "Anúncio</a></div>"
        + "</div>"
    )
    abrir = AbrirFalso(pagina)

    resultados = buscar_web("x", abrir=abrir)

    assert len(resultados) == 1
    assert resultados[0].titulo == "Título com quebras"
    assert resultados[0].url == "https://exemplo.com/espaco"
    assert resultados[0].trecho == "trecho com espacos"


def test_buscar_web_sem_resultados_devolve_lista_vazia() -> None:
    abrir = AbrirFalso('<div class="results"></div>')

    assert buscar_web("nada", abrir=abrir) == []


def test_erro_de_rede_vira_erro_busca_web() -> None:
    def abrir_falhando(url: str, timeout: int) -> str:
        raise ErroBuscaWeb("não consegui alcançar o DuckDuckGo: rede fora")

    with pytest.raises(ErroBuscaWeb, match="não consegui alcançar"):
        buscar_web("x", abrir=abrir_falhando)