"""Busca na web sem chave de API via DuckDuckGo HTML, só stdlib.

Transporte `urllib` (zero dependência nova, mesmo espírito de `io/gdap.py`),
injetável nos testes (sem rede), erros de rede/HTTP convertidos em `ErroBuscaWeb`
com mensagem amigável. Só extrai dados — quem decide se algo vira `Ferramenta` e
com qual `NivelRisco` é `tools/web.py`.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser

URL_BASE = "https://html.duckduckgo.com/html/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

Transporte = Callable[[str, int], str]


class ErroBuscaWeb(Exception):
    """Levantada quando a busca na web falha (rede, HTTP ou resposta inválida)."""


@dataclass(frozen=True)
class BuscaWebResultado:
    titulo: str
    url: str
    trecho: str = ""


def _requisitar(url: str, timeout: int) -> str:
    requisicao = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            conteudo = resposta.read()
            if not isinstance(conteudo, bytes):
                raise ErroBuscaWeb("DuckDuckGo devolveu uma resposta inesperada")
            return conteudo.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as erro:
        raise ErroBuscaWeb(f"DuckDuckGo respondeu HTTP {erro.code}") from erro
    except urllib.error.URLError as erro:
        raise ErroBuscaWeb(f"não consegui alcançar o DuckDuckGo: {erro.reason}") from erro
    except TimeoutError as erro:
        raise ErroBuscaWeb(f"DuckDuckGo não respondeu em {timeout}s") from erro


def _decodificar_url_do_link_duck(link: str) -> str | None:
    """Converte o href de redirecionamento `//duckduckgo.com/l/?uddg=<url>` na URL real.

    Resultados orgânicos do DuckDuckGo apontam para um redirecionador interno com o alvo
    percent-encoded no parâmetro `uddg`. Propagandas (Bing/Ads) também passam por `uddg`,
    mas têm como alvo `duckduckgo.com/y.js?...` — esses são descartados junto com qualquer
    outro link cujo destino aponte para o próprio DuckDuckGo.
    """
    if not link.startswith("//duckduckgo.com/l/?"):
        return None
    parametros = urllib.parse.parse_qs(urllib.parse.urlparse("https:" + link).query)
    alvo = parametros.get("uddg")
    if not alvo:
        return None
    url = urllib.parse.unquote(alvo[0])
    destino = urllib.parse.urlparse(url)
    if destino.scheme not in {"http", "https"}:
        return None
    if destino.hostname and destino.hostname.endswith("duckduckgo.com"):
        return None
    return url


class _ParserResultados(HTMLParser):
    """Coleta `result__a` (título + URL) e `result__snippet` (trecho) do HTML do DuckDuckGo.

    Cada resultado orgânico traz os dois âncoras em sequência dentro do mesmo bloco; o
    estado acumula título e trecho do bloco atual e encerra o registro no próximo título.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.registros: list[dict[str, str]] = []
        self._atual: dict[str, str] | None = None
        self._campo_atual: str | None = None

    def _finalizar_atual(self) -> None:
        if self._atual is not None and self._atual["titulo"]:
            self.registros.append(self._atual)
        self._atual = None
        self._campo_atual = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        classes = set((atributos.get("class") or "").split())
        ligacao = atributos.get("href") or ""
        if tag == "a" and "result__a" in classes:
            url = _decodificar_url_do_link_duck(ligacao)
            if url is None:
                self._finalizar_atual()
                return
            self._finalizar_atual()
            self._atual = {"titulo": "", "url": url, "trecho": ""}
            self._campo_atual = "titulo"
        elif tag == "a" and "result__snippet" in classes and self._atual is not None:
            self._campo_atual = "trecho"

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._campo_atual = None

    def handle_data(self, data: str) -> None:
        if self._atual is None or self._campo_atual is None:
            return
        self._atual[self._campo_atual] += data

    def close(self) -> None:
        super().close()
        self._finalizar_atual()


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def buscar_web(
    consulta: str,
    limite: int = 4,
    timeout: int = 15,
    abrir: Transporte | None = None,
) -> list[BuscaWebResultado]:
    """Busca `consulta` no DuckDuckGo e devolve até `limite` resultados orgânicos."""
    url = f"{URL_BASE}?q={urllib.parse.quote(consulta)}"
    html_pagina = (abrir or _requisitar)(url, timeout)
    parser = _ParserResultados()
    parser.feed(html_pagina)
    parser.close()
    resultados = []
    for registro in parser.registros:
        resultado = BuscaWebResultado(
            titulo=_limpar(registro["titulo"]),
            url=registro["url"],
            trecho=_limpar(registro["trecho"]),
        )
        if resultado.titulo and resultado.url:
            resultados.append(resultado)
        if len(resultados) >= limite:
            break
    return resultados