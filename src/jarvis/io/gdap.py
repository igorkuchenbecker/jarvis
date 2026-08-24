"""Cliente HTTP para a API do GDAP (Global Data Automation Platform, projeto irmão em ~/gdap).

GDAP roda como servidor separado (`gdap system serve`), com seu próprio banco, controle de
acesso e sandbox de SQL. O JARVIS fala com ele só pela API HTTP -- nunca importa o pacote gdap
nem toca no banco dele diretamente -- exatamente como qualquer outro cliente da API (a própria
CLI/web UI do GDAP). Este módulo é só a camada de transporte, no mesmo espírito de
`providers/openai_compat.py`: `urllib` stdlib (zero dependência nova), transporte injetável para
testes sem rede, erros de rede/HTTP/JSON convertidos em `ErroGdap` com mensagem amigável. Quem
decide o que virar `Ferramenta` e com qual `NivelRisco` é `tools/gdap.py`.
"""

from __future__ import annotations

import importlib.metadata
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

Transporte = Callable[[str, str, dict[str, Any] | None, dict[str, str], int], dict[str, Any]]

try:
    VERSAO_JARVIS = importlib.metadata.version("jarvis")
except importlib.metadata.PackageNotFoundError:
    VERSAO_JARVIS = "0"

USER_AGENT = f"jarvis/{VERSAO_JARVIS}"


class ErroGdap(Exception):
    """Levantada quando o servidor GDAP não responde, responde com erro, ou recusa a chamada."""


def _mensagem_erro_gdap(corpo: str) -> str | None:
    """Extrai a mensagem amigável do envelope de erro uniforme do GDAP: {"error": {"code",
    "message", "details", "trace_id"}}. Retorna None se o corpo não seguir esse formato (ex.:
    um proxy na frente do GDAP respondendo HTML de erro).
    """
    try:
        dados = json.loads(corpo)
    except json.JSONDecodeError:
        return None
    erro = dados.get("error") if isinstance(dados, dict) else None
    if not isinstance(erro, dict) or not isinstance(erro.get("message"), str):
        return None
    codigo = erro.get("code")
    return f"{erro['message']} ({codigo})" if codigo else erro["message"]


def _requisitar_json(
    url: str,
    metodo: str,
    corpo: dict[str, Any] | None,
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    requisicao = urllib.request.Request(
        url, data=dados, headers={"User-Agent": USER_AGENT, **headers}, method=metodo
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            bruto = resposta.read().decode("utf-8")
    except urllib.error.HTTPError as erro:
        corpo_erro = erro.read().decode("utf-8", errors="replace")
        mensagem = _mensagem_erro_gdap(corpo_erro) or corpo_erro.strip()[:300]
        raise ErroGdap(f"GDAP respondeu HTTP {erro.code}: {mensagem}") from erro
    except urllib.error.URLError as erro:
        if isinstance(erro.reason, TimeoutError):
            raise ErroGdap(f"GDAP não respondeu em {timeout}s") from erro
        raise ErroGdap(
            f"não consegui conectar ao GDAP em {url} — o servidor está rodando? "
            f"('gdap system serve' no projeto ~/gdap) ({erro.reason})"
        ) from erro
    except TimeoutError as erro:
        raise ErroGdap(f"GDAP não respondeu em {timeout}s") from erro

    if not bruto.strip():
        return {}
    try:
        dados_resposta: dict[str, Any] = json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise ErroGdap(f"resposta do GDAP não é JSON válido: {bruto[:200]!r}") from erro
    return dados_resposta


class ClienteGdap:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: str | None = None,
        timeout_segundos: int = 30,
        _requisitar: Transporte | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_segundos
        self._requisitar: Transporte = _requisitar or _requisitar_json

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    def _chamar(
        self, metodo: str, caminho: str, corpo: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._requisitar(
            f"{self._base_url}{caminho}", metodo, corpo, self._headers(), self._timeout
        )

    def status(self) -> dict[str, Any]:
        return self._chamar("GET", "/health")

    def listar_datasets(self, limite: int = 50) -> list[dict[str, Any]]:
        consulta = urllib.parse.urlencode({"limit": limite})
        resposta = self._chamar("GET", f"/api/v1/datasets?{consulta}")
        itens = resposta.get("items", [])
        return itens if isinstance(itens, list) else []

    def consultar(self, sql: str, limite: int | None = None) -> dict[str, Any]:
        corpo: dict[str, Any] = {"sql": sql}
        if limite is not None:
            corpo["limit"] = limite
        return self._chamar("POST", "/api/v1/datasets/query", corpo)

    def perguntar(self, pergunta: str, dataset: str | None = None) -> dict[str, Any]:
        corpo: dict[str, Any] = {"question": pergunta}
        if dataset is not None:
            corpo["dataset"] = dataset
        return self._chamar("POST", "/api/v1/agents/ask", corpo)

    def executar_pipeline(
        self, nome: str, parametros: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        corpo = {"params": parametros or {}, "wait": True}
        caminho = f"/api/v1/pipelines/{urllib.parse.quote(nome, safe='')}/run"
        return self._chamar("POST", caminho, corpo)
