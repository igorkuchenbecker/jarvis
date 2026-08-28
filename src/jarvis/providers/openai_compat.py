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

# Famílias de modelo que emitem um campo `reasoning` antes do `content`: consomem
# do teto de max_tokens, então merecem um piso maior (ver piso_max_tokens_raciocinio).
MODELOS_DE_RACIOCINIO = frozenset(
    {
        "qwen3",
        "qwq",
        "deepseek-r1",
        "gpt-oss",
        "kimi",
        "glm-4.5",
        "gemini-2.5",
        "reasoning",
        "thinking",
    }
)


def _e_modelo_de_raciocinio(modelo: str) -> bool:
    nome = modelo.lower()
    return any(marca in nome for marca in MODELOS_DE_RACIOCINIO)


PROMPT_SISTEMA_RESUMO = (
    "Você comprime conversas de um assistente. Receba um histórico e devolva um resumo em "
    "pt-BR, sem cabeçalhos nem listas numeradas, preservando fatos, intenções, decisões e "
    'nomes de pessoas/ferramentas. Formato: "Resumo: <3-6 frases>".'
)


def _tokens_aproximados(mensagens: list[dict[str, str]]) -> int:
    total = 0
    for mensagem in mensagens:
        total += max(1, len(mensagem.get("content", "")) // 4)
    return total


def _formatar_historico(mensagens: list[dict[str, str]]) -> str:
    linhas = []
    for mensagem in mensagens:
        papel = "usuário" if mensagem["role"] == "user" else "assistente"
        linhas.append(f"{papel}: {mensagem['content']}")
    return "\n".join(linhas)


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
        desabilitar_ferramentas_nativas: bool = True,
        piso_max_tokens_raciocinio: int = 16384,
        historico_teto_tokens: int = 3000,
        _postar: Transporte | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._modelo = modelo
        self._timeout_segundos = timeout_segundos
        self._prompt_sistema = prompt_sistema
        self._api_key = api_key
        self._max_tokens = max_tokens
        if (
            max_tokens > 0
            and piso_max_tokens_raciocinio > 0
            and _e_modelo_de_raciocinio(modelo)
        ):
            self._max_tokens = max(max_tokens, piso_max_tokens_raciocinio)
        self._desabilitar_ferramentas_nativas = desabilitar_ferramentas_nativas
        self._tentativas_sem_conteudo = tentativas_sem_conteudo
        self._teto_tokens_historico = historico_teto_tokens
        self._postar: Transporte = _postar or _postar_json
        self._mensagens: list[dict[str, str]] = []

    def _solicitar_resumo(self) -> str:
        corpo: dict[str, Any] = {
            "model": self._modelo,
            "messages": [
                {"role": "system", "content": f"{self._prompt_sistema}\n\n{PROMPT_SISTEMA_RESUMO}"},
                {"role": "user", "content": _formatar_historico(self._mensagens)},
            ],
        }
        if self._desabilitar_ferramentas_nativas:
            corpo["tools"] = []
            corpo["tool_choice"] = "none"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        url = f"{self._base_url}/chat/completions"
        try:
            return _extrair_conteudo(self._postar(url, corpo, headers, self._timeout_segundos))
        except ErroProvider:
            return ""

    def _comprimir_historico_se_necessario(self) -> None:
        if self._teto_tokens_historico <= 0:
            return
        if _tokens_aproximados(self._mensagens) <= self._teto_tokens_historico:
            return
        if len(self._mensagens) <= 2:
            return
        resumo = self._solicitar_resumo()
        if not resumo:
            return
        recentes = self._mensagens[-2:]
        self._mensagens = [
            {"role": "system", "content": f"Resumo da conversa anterior: {resumo}"},
            *recentes,
        ]

    def enviar(self, mensagem: str) -> str:
        self._mensagens.append({"role": "user", "content": mensagem})
        self._comprimir_historico_se_necessario()

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
        if self._desabilitar_ferramentas_nativas:
            corpo["tools"] = []
            corpo["tool_choice"] = "none"

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
