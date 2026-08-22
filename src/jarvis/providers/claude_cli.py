"""Provider padrão do JARVIS: conversa chamando a CLI `claude` via subprocess.

Usa a assinatura já autenticada do usuário (sem exigir ANTHROPIC_API_KEY). `--tools=""` desliga
as ferramentas nativas do Claude Code: o provider só gera texto, nunca executa nada — isso é
quem chama (o executor do JARVIS, a partir do M2) que decide o que rodar de fato.
"""

from __future__ import annotations

import json
import subprocess
import uuid

from jarvis.providers.base import ErroProvider

PROMPT_SISTEMA_PADRAO = (
    "Você é o JARVIS, o agente pessoal autônomo do usuário, rodando localmente no Linux dele. "
    "Responda de forma direta, útil e concisa."
)


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

        try:
            resposta = json.loads(processo.stdout)
        except json.JSONDecodeError as erro:
            raise ErroProvider(
                f"resposta inesperada da CLI do claude: {processo.stdout[:200]!r}"
            ) from erro

        if resposta.get("is_error"):
            raise ErroProvider(f"a CLI do claude retornou erro: {resposta.get('result')}")

        return str(resposta.get("result", ""))

    def reiniciar(self) -> None:
        self._sessao_id = None
