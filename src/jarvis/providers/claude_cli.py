"""Providers padrão do JARVIS: conversa e visão chamando a CLI `claude` via subprocess.

Usa a assinatura já autenticada do usuário (sem exigir ANTHROPIC_API_KEY). `--tools=""` desliga
as ferramentas nativas do Claude Code: o provider só gera texto, nunca executa nada — isso é
quem chama (o executor do JARVIS, a partir do M2) que decide o que rodar de fato.
"""

from __future__ import annotations

import base64
import json
import subprocess
import uuid
from pathlib import Path

from jarvis.providers.base import ErroProvider

PROMPT_SISTEMA_PADRAO = (
    "Você é o JARVIS, o agente pessoal autônomo do usuário, rodando localmente no Linux dele. "
    "Responda de forma direta, útil e concisa."
)

PROMPT_SISTEMA_VISAO_PADRAO = (
    "Você é o JARVIS analisando uma captura de tela do computador do usuário. "
    "Descreva o que for pedido de forma direta e concisa, em português."
)

MEDIA_TYPE_POR_EXTENSAO = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _extrair_resultado_da_ultima_linha(saida: str) -> str:
    linhas = [linha for linha in saida.splitlines() if linha.strip()]
    if not linhas:
        raise ErroProvider("a CLI do claude não retornou nenhuma saída")

    try:
        resposta = json.loads(linhas[-1])
    except json.JSONDecodeError as erro:
        raise ErroProvider(
            f"resposta inesperada da CLI do claude: {linhas[-1][:200]!r}"
        ) from erro

    if resposta.get("is_error"):
        raise ErroProvider(f"a CLI do claude retornou erro: {resposta.get('result')}")

    return str(resposta.get("result", ""))


class ClaudeCliProvider:
    def __init__(
        self,
        binario: str = "claude",
        timeout_segundos: int = 120,
        prompt_sistema: str = PROMPT_SISTEMA_PADRAO,
    ) -> None:
        self._binario = binario
        self._timeout_segundos = timeout_segundos
        self._prompt_sistema = prompt_sistema
        self._sessao_id: str | None = None

    def enviar(self, mensagem: str) -> str:
        comando = [
            self._binario,
            "-p",
            "--output-format",
            "json",
            "--tools=",
            "--system-prompt",
            self._prompt_sistema,
        ]
        if self._sessao_id is None:
            self._sessao_id = str(uuid.uuid4())
            comando += ["--session-id", self._sessao_id]
        else:
            comando += ["--resume", self._sessao_id]
        comando.append(mensagem)

        try:
            processo = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                timeout=self._timeout_segundos,
            )
        except FileNotFoundError as erro:
            raise ErroProvider(
                f"binário '{self._binario}' não encontrado no PATH — instale a CLI do Claude "
                "ou ajuste provedor.claude_cli.binario em config.yaml"
            ) from erro
        except subprocess.TimeoutExpired as erro:
            raise ErroProvider(
                f"a CLI do claude não respondeu em {self._timeout_segundos}s"
            ) from erro

        if processo.returncode != 0:
            detalhe = processo.stderr.strip() or processo.stdout.strip()
            raise ErroProvider(f"CLI do claude falhou: {detalhe}")

        return _extrair_resultado_da_ultima_linha(processo.stdout)

    def reiniciar(self) -> None:
        self._sessao_id = None


class ClaudeCliVisionProvider:
    """Visão via `claude -p --input-format stream-json`: cada chamada é uma sessão nova (sem
    `--resume`) — análise de imagem não é uma conversa contínua no design do M7.
    """

    def __init__(
        self,
        binario: str = "claude",
        timeout_segundos: int = 120,
        prompt_sistema: str = PROMPT_SISTEMA_VISAO_PADRAO,
    ) -> None:
        self._binario = binario
        self._timeout_segundos = timeout_segundos
        self._prompt_sistema = prompt_sistema

    def analisar(self, caminho_imagem: Path, pergunta: str) -> str:
        media_type = MEDIA_TYPE_POR_EXTENSAO.get(caminho_imagem.suffix.lower())
        if media_type is None:
            raise ErroProvider(f"formato de imagem não suportado: {caminho_imagem.suffix}")

        dados_base64 = base64.b64encode(caminho_imagem.read_bytes()).decode("ascii")
        mensagem = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "text", "text": pergunta},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": dados_base64,
                        },
                    },
                ],
            },
        }

        comando = [
            self._binario,
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--tools=",
            "--system-prompt",
            self._prompt_sistema,
        ]

        try:
            processo = subprocess.run(
                comando,
                input=json.dumps(mensagem) + "\n",
                capture_output=True,
                text=True,
                timeout=self._timeout_segundos,
            )
        except FileNotFoundError as erro:
            raise ErroProvider(
                f"binário '{self._binario}' não encontrado no PATH — instale a CLI do Claude"
            ) from erro
        except subprocess.TimeoutExpired as erro:
            raise ErroProvider(
                f"a CLI do claude não respondeu em {self._timeout_segundos}s"
            ) from erro

        if processo.returncode != 0:
            detalhe = processo.stderr.strip() or processo.stdout.strip()
            raise ErroProvider(f"CLI do claude falhou: {detalhe}")

        return _extrair_resultado_da_ultima_linha(processo.stdout)
