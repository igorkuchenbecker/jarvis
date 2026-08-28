#!/usr/bin/env python3
"""Benchmark de aderência do LLM ativo ao protocolo de ação do JARVIS.

Roda uma conversa real (processar_turno) para cada pergunta golden e classifica a primeira
resposta do modelo em: canônica ({"tipo":"acao",...}), nativa (tool/args, function...), JSON
solto sem ação, ou texto. A medida de aderência é quantas vezes a ferramenta esperada foi de
fato executada automaticamente. Exige o provider ativo no config.yaml (ex.: Ollama local).

Uso: .venv/bin/python scripts/benchmark_aderencia.py [--vezes N] [--json /tmp/saida.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from jarvis.core.configuracao import carregar_configuracao  # noqa: E402
from jarvis.core.loop import processar_turno  # noqa: E402
from jarvis.io import cli as cli_mod  # noqa: E402
from jarvis.providers import criar_provider_llm  # noqa: E402
from jarvis.security.executor import Executor  # noqa: E402
from jarvis.tools import criar_registro_ferramentas_padrao  # noqa: E402

PERGUNTAS: list[tuple[str, set[str]]] = [
    ("quais foram as últimas mudanças no seu software?", {"auto.mudancas"}),
    ("qual provider de LLM você está usando agora?", {"auto.info"}),
    ("o que o seu Second Brain sabe sobre código limpo?", {"conhecimento.buscar", "pesquisar"}),
    ("o que o Second Brain sabe sobre git?", {"conhecimento.buscar", "pesquisar"}),
    ("liste os arquivos do meu workspace de trabalho.", {"fs.list"}),
    (
        "que habilidades de programação o Second Brain conhece?",
        {"conhecimento.buscar", "pesquisar"},
    ),
]


def _classificar(texto: str) -> str:
    bruto = texto.strip()
    if bruto.startswith("```"):
        bruto = bruto.strip("`").strip()
        if bruto.startswith("json"):
            bruto = bruto[len("json") :].strip()
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError:
        return "texto"
    if not isinstance(dados, dict):
        return "texto"
    if dados.get("tipo") == "acao":
        return "canonica"
    if any(chave in dados for chave in ("tool", "function", "function_call", "name")):
        return "nativa"
    return "json_solto"


def _primeira_resposta_assistant(provider: Any) -> str:
    for mensagem in getattr(provider, "_mensagens", []):
        if mensagem.get("role") == "assistant":
            return str(mensagem.get("content", ""))
    return ""


def _rodar(pergunta: str, max_iteracoes: int) -> dict[str, Any]:
    configuracao = carregar_configuracao()
    registro = criar_registro_ferramentas_padrao(configuracao)
    executor = Executor(
        registro,
        jail_paths=list(configuracao.seguranca.jail_paths),
        jail_paths_leitura=list(configuracao.seguranca.jail_paths_leitura),
        allowlist_binarios=configuracao.seguranca.allowlist_binarios,
        nivel_autonomia=1,
    )
    prompt_sistema = cli_mod.PROMPT_SISTEMA_COM_FERRAMENTAS.format(
        ferramentas=registro.descrever_para_prompt()
    )
    provider = criar_provider_llm(configuracao, prompt_sistema=prompt_sistema)
    turno = processar_turno(provider, executor, pergunta, max_iteracoes=max_iteracoes)
    executadas = [acao.ferramenta for acao in turno.acoes_executadas]
    return {
        "primeira_resposta": _classificar(_primeira_resposta_assistant(provider)),
        "executadas": executadas,
        "resposta_final": turno.resposta_final,
    }


def principal() -> None:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--vezes", type=int, default=2, help="execuções por pergunta")
    analisador.add_argument("--max-iteracoes", type=int, default=6)
    analisador.add_argument("--json", default="", help="caminho opcional p/ salvar relatório JSON")
    argumentos = analisador.parse_args()

    seletor_perguntas = list(range(len(PERGUNTAS)))
    resultados: list[dict[str, Any]] = []
    print(f"Benchmark de aderência ao protocolo — {len(seletor_perguntas)} perguntas "
          f"x {argumentos.vezes} execuções\n")
    for indice in seletor_perguntas:
        pergunta, aceitas = PERGUNTAS[indice]
        for execucao in range(1, argumentos.vezes + 1):
            print(f"[{indice + 1}/{len(seletor_perguntas)} exec {execucao}/{argumentos.vezes}] "
                  f"{pergunta[:60]}... ", end="", flush=True)
            dado = _rodar(pergunta, argumentos.max_iteracoes)
            acertou = bool(set(dado["executadas"]) & aceitas)
            dado.update({"pergunta": pergunta, "aceitas": sorted(aceitas), "acertou": acertou})
            resultados.append(dado)
            print(f"1ª={dado['primeira_resposta']} exec={dado['executadas'] or '—'} "
                  f"acerto={'OK' if acertou else 'FALHOU'}")

    acertos = sum(1 for dado in resultados if dado["acertou"])
    total = len(resultados)
    aderencia = acertos / total if total else 0.0
    resumo = {
        "aderencia_total": round(aderencia, 4),
        "acertos": acertos,
        "total": total,
        "por_formato": {
            formato: sum(1 for dado in resultados if dado["primeira_resposta"] == formato)
            for formato in ("canonica", "nativa", "json_solto", "texto")
        },
        "resultados": resultados,
    }
    print(f"\nAderência: {acertos}/{total} ({aderencia:.1%}) "
          f"— 1ª resposta: {resumo['por_formato']}")
    if argumentos.json:
        destino = Path(argumentos.json)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"relatório salvo em {destino}")
    sys.exit(0 if acertos == total else 1)


if __name__ == "__main__":
    principal()