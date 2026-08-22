"""Benchmark FTS5 (produção) vs embeddings locais (fastembed) — M6.

Decide se vale adotar embeddings/rerank no lugar de (ou além de) FTS5 para a busca de
conhecimento. Corpus pequeno e proposital: metade das perguntas tem sobreposição léxica com o
trecho certo (onde FTS5 já deveria ir bem) e metade usa sinônimos/parafraseamento sem nenhuma
palavra em comum com o trecho certo (o cenário em que embeddings deveriam ganhar, se ganharem).

Resultado registrado em docs/DECISOES.md. Rodar de novo com
`python scripts/benchmark_embeddings.py` se o corpus real de conhecimento crescer o bastante para
valer reavaliar a decisão.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

from jarvis.memory.conhecimento import RepositorioConhecimento

MODELO_EMBEDDING = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# (arquivo, [(secao, texto), ...])
CORPUS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "manual_carro.md",
        [
            (
                "Troca de óleo",
                "É recomendado trocar o óleo do motor a cada 10 mil quilômetros rodados.",
            ),
            ("Calibragem dos pneus", "A pressão ideal dos pneus é 32 PSI quando frios."),
        ],
    ),
    (
        "receitas.md",
        [("Bolo de cenoura", "Bata no liquidificador 3 cenouras, 4 ovos e 1 xícara de óleo.")],
    ),
    (
        "financas.md",
        [
            (
                "Cartão de crédito",
                "A fatura do cartão vence todo dia 10 e o pagamento mínimo é de 15% do total.",
            ),
            (
                "Investimentos",
                "Uma reserva de emergência deve cobrir de 6 a 12 meses de despesas.",
            ),
        ],
    ),
    (
        "trabalho.md",
        [
            (
                "Reunião semanal",
                "Toda segunda-feira às 10h temos alinhamento de equipe pelo Google Meet.",
            )
        ],
    ),
    (
        "saude.md",
        [
            (
                "Consulta médica",
                "O check-up anual inclui exame de sangue e aferição da pressão arterial.",
            )
        ],
    ),
]

# (consulta, texto_esperado, tem_sobreposicao_lexical)
CASOS: list[tuple[str, str, bool]] = [
    ("qual a pressão correta para encher os pneus?", "pressão ideal dos pneus", True),
    ("como faço um bolo usando cenoura?", "Bata no liquidificador", True),
    ("quando vence minha fatura do cartão?", "fatura do cartão vence", True),
    (
        "a cada quantos km preciso fazer a manutenção do veículo?",
        "trocar o óleo do motor",
        False,
    ),
    (
        "quantos meses de gastos minha poupança de segurança deveria cobrir?",
        "reserva de emergência",
        False,
    ),
    ("em que dia da semana é o encontro do time?", "alinhamento de equipe", False),
    ("o que é avaliado no exame de rotina anual?", "check-up anual", False),
]


def _montar_corpus_fts5(diretorio: Path) -> RepositorioConhecimento:
    for arquivo, secoes in CORPUS:
        linhas = []
        for secao, texto in secoes:
            linhas.append(f"## {secao}\n\n{texto}\n")
        (diretorio / arquivo).write_text("\n".join(linhas), encoding="utf-8")

    repositorio = RepositorioConhecimento(diretorio / "conhecimento.db")
    repositorio.ingerir_diretorio(diretorio)
    return repositorio


def _todos_os_trechos_com_texto_esperado() -> list[str]:
    return [texto for _, secoes in CORPUS for _, texto in secoes]


def _rank_fts5(repositorio: RepositorioConhecimento, consulta: str, k: int) -> list[str]:
    return [t.texto for t in repositorio.buscar(consulta, limite=k)]


def _rank_embeddings(
    modelo: TextEmbedding,
    embeddings_corpus: np.ndarray,
    textos_corpus: list[str],
    consulta: str,
    k: int,
) -> list[str]:
    (embedding_consulta,) = list(modelo.query_embed(consulta))
    similaridades = embeddings_corpus @ embedding_consulta
    indices_ordenados = np.argsort(-similaridades)[:k]
    return [textos_corpus[i] for i in indices_ordenados]


def main() -> None:
    with tempfile.TemporaryDirectory() as diretorio_str:
        diretorio = Path(diretorio_str)
        repositorio = _montar_corpus_fts5(diretorio)

        textos_corpus = _todos_os_trechos_com_texto_esperado()
        modelo = TextEmbedding(model_name=MODELO_EMBEDDING)
        embeddings_corpus = np.array(list(modelo.passage_embed(textos_corpus)))

        acertos_fts5_top1 = acertos_fts5_top3 = 0
        acertos_emb_top1 = acertos_emb_top3 = 0
        acertos_fts5_top1_gap = acertos_emb_top1_gap = 0
        total_gap = 0

        print(f"{'consulta':<65} {'FTS5@1':<8} {'FTS5@3':<8} {'EMB@1':<8} {'EMB@3':<8}")
        for consulta, trecho_esperado, tem_sobreposicao in CASOS:
            top3_fts5 = _rank_fts5(repositorio, consulta, k=3)
            top3_emb = _rank_embeddings(modelo, embeddings_corpus, textos_corpus, consulta, k=3)

            fts5_top1 = bool(top3_fts5) and trecho_esperado in top3_fts5[0]
            fts5_top3 = any(trecho_esperado in t for t in top3_fts5)
            emb_top1 = bool(top3_emb) and trecho_esperado in top3_emb[0]
            emb_top3 = any(trecho_esperado in t for t in top3_emb)

            acertos_fts5_top1 += fts5_top1
            acertos_fts5_top3 += fts5_top3
            acertos_emb_top1 += emb_top1
            acertos_emb_top3 += emb_top3

            if not tem_sobreposicao:
                total_gap += 1
                acertos_fts5_top1_gap += fts5_top1
                acertos_emb_top1_gap += emb_top1

            print(
                f"{consulta:<65} {str(fts5_top1):<8} {str(fts5_top3):<8} "
                f"{str(emb_top1):<8} {str(emb_top3):<8}"
            )

        n = len(CASOS)
        print()
        print(f"FTS5  — hit@1: {acertos_fts5_top1}/{n}   hit@3: {acertos_fts5_top3}/{n}")
        print(f"EMB   — hit@1: {acertos_emb_top1}/{n}   hit@3: {acertos_emb_top3}/{n}")
        print(
            f"Só nas consultas SEM sobreposição léxica (n={total_gap}): "
            f"FTS5 hit@1 {acertos_fts5_top1_gap}/{total_gap}  "
            f"EMB hit@1 {acertos_emb_top1_gap}/{total_gap}"
        )


if __name__ == "__main__":
    main()
