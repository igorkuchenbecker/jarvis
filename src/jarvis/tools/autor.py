"""Ferramentas de autoconhecimento e automanutenção do próprio JARVIS.

Permitem ao agente saber como está configurado e instalado (provedor, versão, estado do git) e
aplicar mudanças dentro do próprio repositório (~/jarvis). Alterações são sempre HIGH — aprovação
humana interativa — e jamais saem do repositório: os caminhos são confinados à raiz do projeto
aqui dentro, e os comandos git/pip/bash são fixos (sem shell livre).
"""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from jarvis.core.configuracao import RAIZ_JARVIS_PADRAO, Configuracao
from jarvis.tools.base import Ferramenta, NivelRisco
from jarvis.tools.sistema import TAMANHO_MAXIMO_SAIDA

SCHEMA_VAZIO = {"type": "object", "properties": {}, "additionalProperties": False}

SCHEMA_MUDANCAS = {
    "type": "object",
    "properties": {"limite": {"type": "integer"}},
    "additionalProperties": False,
}

SCHEMA_EDITAR = {
    "type": "object",
    "properties": {"caminho": {"type": "string"}, "conteudo": {"type": "string"}},
    "required": ["caminho", "conteudo"],
    "additionalProperties": False,
}

SCHEMA_COMMIT = {
    "type": "object",
    "properties": {"mensagem": {"type": "string"}},
    "required": ["mensagem"],
    "additionalProperties": False,
}


def _ambiente_codigo() -> dict[str, str]:
    ambiente = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(Path.home()),
        "LANG": "C.UTF-8",
    }
    if "SSH_AUTH_SOCK" in os.environ:
        ambiente["SSH_AUTH_SOCK"] = os.environ["SSH_AUTH_SOCK"]
    return ambiente


def _rodar(comando: list[str], timeout_segundos: int) -> tuple[int, str, str]:
    processo = subprocess.run(
        comando,
        capture_output=True,
        text=True,
        timeout=timeout_segundos,
        env=_ambiente_codigo(),
    )
    return (
        processo.returncode,
        processo.stdout[:TAMANHO_MAXIMO_SAIDA],
        processo.stderr[:TAMANHO_MAXIMO_SAIDA],
    )


def _git(argumentos: list[str], timeout_segundos: int = 90) -> tuple[int, str, str]:
    return _rodar(
        ["git", "-C", str(RAIZ_JARVIS_PADRAO), *argumentos],
        timeout_segundos=timeout_segundos,
    )


def _caminho_no_repo(caminho_bruto: str) -> Path:
    """Resolve e confina um caminho dentro da raiz do repositório do JARVIS."""
    raiz = RAIZ_JARVIS_PADRAO.resolve()
    bruto = Path(caminho_bruto)
    if not bruto.is_absolute():
        bruto = RAIZ_JARVIS_PADRAO / bruto
    caminho = bruto.expanduser().resolve()
    if caminho != raiz and raiz not in caminho.parents:
        raise ValueError(f"caminho '{caminho_bruto}' está fora do repositório do JARVIS")
    if ".git" in caminho.relative_to(raiz).parts:
        raise ValueError("não edito arquivos dentro de .git")
    return caminho


def _obter_versao() -> str:
    try:
        return importlib.metadata.version("jarvis")
    except importlib.metadata.PackageNotFoundError:
        return "0"


def _estado_git() -> dict[str, Any]:
    _, saida, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    branch = saida.strip()
    _, saida, _ = _git(["log", "-1", "--format=%h|%ad|%s", "--date=iso"])
    partes = saida.strip().split("|", 2)
    _, saida, _ = _git(["status", "--porcelain", "--untracked-files=no"])
    pendentes = [linha for linha in saida.splitlines() if linha.strip()]
    return {
        "branch": branch or None,
        "head": partes[0] if partes and partes[0] else None,
        "data": partes[1] if len(partes) > 1 else None,
        "mensagem": partes[2] if len(partes) > 2 else None,
        "arquivos_nao_commitados": pendentes,
    }


def _criar_info(configuracao: Configuracao) -> Any:
    def _info(argumentos: dict[str, Any]) -> dict[str, Any]:
        detalhe: dict[str, Any]
        if configuracao.llm_padrao == "claude_cli":
            detalhe = {"binario": configuracao.claude_cli.binario}
        elif configuracao.llm_padrao == "openai_compat":
            ajustes = configuracao.openai_compat
            detalhe = {
                "base_url": ajustes.base_url,
                "modelo": ajustes.modelo,
                "api_key_env": ajustes.api_key_env or None,
                "api_key_definida": bool(
                    ajustes.api_key_env and os.environ.get(ajustes.api_key_env)
                ),
            }
        else:
            detalhe = {}
        if (RAIZ_JARVIS_PADRAO / ".git").exists():
            git: dict[str, Any] | None = _estado_git()
        else:
            git = None
        return {
            "versao": _obter_versao(),
            "provedor": configuracao.llm_padrao,
            "detalhe_provedor": detalhe,
            "config_yaml": str(RAIZ_JARVIS_PADRAO / "config.yaml"),
            "git": git,
        }

    return _info


def _mudancas(argumentos: dict[str, Any]) -> list[dict[str, str | None]]:
    limite = int(argumentos.get("limite", 10))
    limite = max(1, min(limite, 50))
    codigo, saida, erro = _git(["log", f"-{limite}", "--format=%h|%ad|%s", "--date=iso"])
    if codigo != 0:
        raise ValueError(erro or saida or "git log falhou")
    mudancas: list[dict[str, str | None]] = []
    for linha in saida.splitlines():
        if not linha.strip():
            continue
        partes = linha.split("|", 2)
        mudancas.append(
            {
                "hash": partes[0] or None,
                "data": partes[1] if len(partes) > 1 else None,
                "mensagem": partes[2] if len(partes) > 2 else None,
            }
        )
    return mudancas


def _atualizar(argumentos: dict[str, Any]) -> dict[str, Any]:
    passos: list[dict[str, Any]] = []

    codigo, saida, erro = _git(["status", "--porcelain", "--untracked-files=no"])
    arquivos_pendentes = [linha for linha in saida.splitlines() if linha.strip()]
    if arquivos_pendentes:
        return {
            "atualizado": False,
            "motivo": (
                f"repositório com {len(arquivos_pendentes)} arquivo(s) não commitado(s); "
                "faça commit antes"
            ),
            "arquivos_nao_commitados": arquivos_pendentes,
            "passos": passos,
        }

    codigo, saida, erro = _git(["fetch", "origin"])
    passos.append(
        {"passo": "git fetch origin", "codigo": codigo, "detalhe": (saida or erro).strip()[:400]}
    )
    if codigo != 0:
        return {
            "atualizado": False,
            "motivo": "fetch falhou — sem internet ou remote inacessível",
            "passos": passos,
        }

    _, saida, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    branch = saida.strip() or "main"
    _, saida, _ = _git(["rev-list", "--count", f"HEAD..origin/{branch}"])
    try:
        commits_atrasados = int(saida.strip() or "0")
    except ValueError:
        commits_atrasados = 0

    if commits_atrasados > 0:
        codigo, saida, erro = _git(
            ["pull", "--ff-only", "origin", branch], timeout_segundos=120
        )
        passos.append(
            {
                "passo": f"git pull --ff-only origin {branch}",
                "codigo": codigo,
                "detalhe": (saida or erro).strip()[:400],
            }
        )
        if codigo != 0:
            return {"atualizado": False, "motivo": "pull falhou", "passos": passos}
    else:
        passos.append(
            {
                "passo": f"git pull --ff-only origin {branch}",
                "codigo": 0,
                "detalhe": "já atualizado",
            }
        )

    codigo, saida, erro = _rodar(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            "-e",
            str(RAIZ_JARVIS_PADRAO),
        ],
        timeout_segundos=180,
    )
    passos.append(
        {
            "passo": "pip install --no-build-isolation -e .",
            "codigo": codigo,
            "detalhe": (saida or erro).strip()[:400],
        }
    )

    codigo, saida, erro = _rodar(
        ["bash", str(RAIZ_JARVIS_PADRAO / "scripts" / "check.sh")], timeout_segundos=180
    )
    passos.append(
        {"passo": "scripts/check.sh", "codigo": codigo, "detalhe": (saida or erro).strip()[:400]}
    )

    return {
        "atualizado": True,
        "motivo": (
            "repositório atualizado e reinstalado; reinicie a sessão (sair) para carregar "
            "o novo código"
        ),
        "verificacao": "verde" if codigo == 0 else "falhou — inspecione o detalhe do check.sh",
        "passos": passos,
    }


def _editar_estado(argumentos: dict[str, Any]) -> str | None:
    caminho = _caminho_no_repo(str(argumentos["caminho"]))
    if caminho.exists():
        return caminho.read_text("utf-8")
    return None


def _editar(argumentos: dict[str, Any]) -> str:
    caminho = _caminho_no_repo(str(argumentos["caminho"]))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(str(argumentos["conteudo"]), encoding="utf-8")
    relativo = caminho.relative_to(RAIZ_JARVIS_PADRAO.resolve())
    return f"arquivo {relativo} atualizado no repositório do JARVIS"


def _editar_reverter(argumentos: dict[str, Any], estado: Any) -> None:
    caminho = _caminho_no_repo(str(argumentos["caminho"]))
    if estado is None:
        caminho.unlink(missing_ok=True)
    else:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(str(estado), encoding="utf-8")


def _commit(argumentos: dict[str, Any]) -> dict[str, Any]:
    mensagem = str(argumentos["mensagem"]).strip()
    if not mensagem:
        raise ValueError("mensagem de commit vazia")
    codigo, saida, erro = _git(["add", "-A"])
    if codigo != 0:
        raise ValueError(erro or saida or "git add falhou")
    codigo, saida, erro = _git(["commit", "-m", mensagem])
    if codigo != 0:
        combinado = f"{erro}\n{saida}"
        if "nothing to commit" in combinado:
            return {"commit": None, "mensagem": mensagem, "observacao": "nada para commitar"}
        raise ValueError(erro or saida or "git commit falhou")
    _, saida, _ = _git(["log", "-1", "--oneline"])
    return {"commit": saida.strip(), "mensagem": mensagem}


def criar_ferramentas_autoconsciencia(configuracao: Configuracao) -> list[Ferramenta]:
    return [
        Ferramenta(
            nome="auto.info",
            descricao=(
                "Mostra como o JARVIS está configurado e instalado: versão do pacote, provedor "
                "de LLM ativo (claude_cli, openai_compat...) com seus detalhes, endereço do "
                "config.yaml e estado do git do repositório (branch, head, arquivos não "
                "commitados)."
            ),
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_VAZIO,
            executar=_criar_info(configuracao),
        ),
        Ferramenta(
            nome="auto.mudancas",
            descricao=(
                "Lista as últimas mudanças (commits) no repositório do JARVIS, com hash, "
                "data e mensagem."
            ),
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_MUDANCAS,
            executar=_mudancas,
        ),
        Ferramenta(
            nome="auto.atualizar",
            descricao=(
                "Busca e aplica as últimas mudanças do repositório do JARVIS (git fetch + "
                "pull --ff-only quando houver), reinstala o pacote e roda scripts/check.sh. "
                "Exige aprovação humana."
            ),
            risco=NivelRisco.HIGH,
            schema_argumentos=SCHEMA_VAZIO,
            executar=_atualizar,
        ),
        Ferramenta(
            nome="auto.editar",
            descricao=(
                "Cria ou sobrescreve um arquivo do código-fonte do próprio JARVIS, dentro do "
                "repositório — com rollback automático em caso de erro. Exige aprovação humana."
            ),
            risco=NivelRisco.HIGH,
            schema_argumentos=SCHEMA_EDITAR,
            executar=_editar,
            capturar_estado=_editar_estado,
            reverter=_editar_reverter,
        ),
        Ferramenta(
            nome="auto.commit",
            descricao=(
                "Cria um commit no repositório do JARVIS com as alterações atuais "
                "(git add -A + commit). Exige aprovação humana."
            ),
            risco=NivelRisco.HIGH,
            schema_argumentos=SCHEMA_COMMIT,
            executar=_commit,
        ),
    ]