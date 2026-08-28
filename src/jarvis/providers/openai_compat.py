"""Provider LLM compatível com a API OpenAI (POST {base_url}/chat/completions).

Funciona com qualquer servidor que exponha esse formato: Ollama local (sem custo, offline),
Groq, Gemini (endpoint OpenAI-compat), OpenRouter e afins. Diferente do ClaudeCliProvider —
onde o histórico vive na sessão da CLI via `--resume` — aqui o histórico da conversa é
mantido pelo próprio provider, em memória. O protocolo de ações do JARVIS é texto puro
(JSON `{"tipo":"acao",...}` no corpo da resposta), então qualquer modelo que devolva texto
consegue participar do loop de ferramentas sem suporte nativo a tool-calling.
"""

from __future__ import annotations

import importlib.metadata
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from jarvis.providers.base import ErroProvider
from jarvis.providers.claude_cli import PROMPT_SISTEMA_PADRAO

Transporte = Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]]

try:
    VERSAO_JARVIS = importlib.metadata.version("jarvis")
except importlib.metadata.PackageNotFoundError:
    VERSAO_JARVIS = "0"

USER_AGENT = f"jarvis/{VERSAO_JARVIS}"


def _postar_json(
    url: str, corpo: dict[str, Any], headers: dict[str, str], timeout: int
) -> dict[str, Any]:
    requisicao = urllib.request.Request(
        url,
        data=json.dumps(corpo).encode("utf-8"),
        headers={"User-Agent": USER_AGENT, **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            bruto = resposta.read().decode("utf-8")
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", errors="replace").strip()[:200]
        raise ErroProvider(f"o servidor respondeu HTTP {erro.code}: {detalhe}") from erro
    except urllib.error.URLError as erro:
        if isinstance(erro.reason, TimeoutError):
            raise ErroProvider(f"o servidor não respondeu em {timeout}s") from erro
        raise ErroProvider(
            f"não consegui conectar em {url} — servidor fora do ar ou endereço errado? "
            f"({erro.reason})"
        ) from erro
    except TimeoutError as erro:
        raise ErroProvider(f"o servidor não respondeu em {timeout}s") from erro

    try:
        dados: dict[str, Any] = json.loads(bruto)
        return dados
    except json.JSONDecodeError as erro:
        raise ErroProvider(f"resposta não é JSON válido: {bruto[:200]!r}") from erro


def _extrair_conteudo(resposta: dict[str, Any]) -> str:
    choices = resposta.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ErroProvider(f"resposta sem 'choices': {json.dumps(resposta)[:200]!r}")

    mensagem = choices[0].get("message") or {}
    conteudo = mensagem.get("content")
    if conteudo is None:
        return ""
    if not isinstance(conteudo, str):
        raise ErroProvider("resposta chegou com conteúdo não textual")
    return conteudo


class OpenAICompatProvider:
    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        modelo: str = "llama3",
        timeout_segundos: int = 120,
        prompt_sistema: str = PROMPT_SISTEMA_PADRAO,
        api_key: str | None = None,
        max_tokens: int = 8192,
        tentativas_sem_conteudo: int = 2,
        _postar: Transporte | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._modelo = modelo
        self._timeout_segundos = timeout_segundos
        self._prompt_sistema = prompt_sistema
        self._api_key = api_key
        self._max_tokens = max_tokens
        self._tentativas_sem_conteudo = tentativas_sem_conteudo
        self._postar: Transporte = _postar or _postar_json
        self._mensagens: list[dict[str, str]] = []

    def enviar(self, mensagem: str) -> str:
        self._mensagens.append({"role": "user", "content": mensagem})

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        corpo: dict[str, Any] = {
            "model": self._modelo,
            "messages": [
                {"role": "system", "content": self._prompt_sistema},
                *self._mensagens,
            ],
        }
        if self._max_tokens > 0:
            corpo["max_tokens"] = self._max_tokens

        url = f"{self._base_url}/chat/completions"
        try:
            for _ in range(self._tentativas_sem_conteudo):
                conteudo = _extrair_conteudo(
                    self._postar(url, corpo, headers, self._timeout_segundos)
                )
                if conteudo:
                    self._mensagens.append({"role": "assistant", "content": conteudo})
                    return conteudo
        except ErroProvider:
            self._mensagens.pop()
            raise

        self._mensagens.pop()
        raise ErroProvider(
            f"resposta chegou sem conteúdo textual {self._tentativas_sem_conteudo}x no modelo "
            f"'{self._modelo}' ({self._base_url}) — pode ser o raciocínio do modelo estourando "
            "o teto de tokens: aumente 'max_tokens' em provedor.openai_compat no config.yaml"
        )

    def reiniciar(self) -> None:
        self._mensagens.clear()
