"""Utilitário interno compartilhado por memory/armazenamento.py e memory/conhecimento.py."""

from __future__ import annotations

import re


def construir_consulta_fts5(consulta: str) -> str:
    """Transforma uma pergunta em linguagem natural numa consulta FTS5 com OR entre os termos.

    O MATCH padrão do FTS5 exige TODOS os termos na mesma linha (AND implícito) — péssimo para
    perguntas naturais, onde palavras relevantes costumam cair em trechos/seções diferentes.
    Com OR, qualquer trecho que bata pelo menos um termo entra, e o `rank` (bm25) do FTS5 já
    prioriza os que batem mais termos.
    """
    termos = re.findall(r"\w+", consulta, flags=re.UNICODE)
    if not termos:
        return consulta
    return " OR ".join(termos)
