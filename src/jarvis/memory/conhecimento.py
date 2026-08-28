"""RAG leve: ingestão de .md/.txt/.pdf de diretórios autorizados, indexados por FTS5, com
citação [arquivo § seção] e atualização por mtime (arquivo sem mudança não é reindexado).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from jarvis.memory._fts5 import construir_consulta_fts5

EXTENSOES_SUPORTADAS = (".md", ".txt", ".pdf")


def _caminho_de_exibicao(caminho_bruto: str) -> str:
    """Caminho original abreviado para '~/...' quando estiver dentro do home — o modelo pode
    ler o arquivo citado com fs.read (o caminho resolvido está no jail de leitura)."""
    caminho = Path(caminho_bruto)
    try:
        relativo = caminho.relative_to(Path.home())
    except ValueError:
        return caminho.as_posix()
    return f"~/{relativo.as_posix()}"


@dataclass(frozen=True)
class Trecho:
    arquivo: str
    secao: str
    texto: str

    def citacao(self) -> str:
        nome = _caminho_de_exibicao(self.arquivo)
        if self.secao:
            return f"[{nome} § {self.secao}]"
        return f"[{nome}]"


def _dividir_markdown_por_cabecalho(conteudo: str) -> list[tuple[str, str]]:
    linhas = conteudo.splitlines()
    secoes: list[tuple[str, list[str]]] = [("", [])]
    for linha in linhas:
        if re.match(r"^#{1,6}\s+\S", linha):
            titulo = linha.lstrip("#").strip()
            secoes.append((titulo, []))
        else:
            secoes[-1][1].append(linha)
    return [
        (titulo, "\n".join(corpo).strip())
        for titulo, corpo in secoes
        if "\n".join(corpo).strip()
    ]


def _extrair_trechos(caminho: Path) -> list[tuple[str, str]]:
    sufixo = caminho.suffix.lower()
    if sufixo == ".md":
        return _dividir_markdown_por_cabecalho(caminho.read_text(encoding="utf-8"))
    if sufixo == ".txt":
        texto = caminho.read_text(encoding="utf-8").strip()
        return [("", texto)] if texto else []
    if sufixo == ".pdf":
        leitor = PdfReader(str(caminho))
        trechos = []
        for indice, pagina in enumerate(leitor.pages, start=1):
            texto = (pagina.extract_text() or "").strip()
            if texto:
                trechos.append((f"página {indice}", texto))
        return trechos
    raise ValueError(f"extensão não suportada: {sufixo}")


class RepositorioConhecimento:
    def __init__(self, caminho_banco: Path) -> None:
        caminho_banco.parent.mkdir(parents=True, exist_ok=True)
        self._conexao = sqlite3.connect(caminho_banco)
        self._conexao.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS conhecimento USING fts5("
            "texto, secao, arquivo UNINDEXED)"
        )
        self._conexao.execute(
            "CREATE TABLE IF NOT EXISTS conhecimento_arquivos ("
            "caminho TEXT PRIMARY KEY, mtime REAL NOT NULL)"
        )
        self._conexao.commit()

    def ingerir_arquivo(self, caminho: Path, forcar: bool = False) -> int:
        caminho = caminho.expanduser().resolve()
        mtime_atual = caminho.stat().st_mtime
        linha = self._conexao.execute(
            "SELECT mtime FROM conhecimento_arquivos WHERE caminho = ?", (str(caminho),)
        ).fetchone()

        if linha is not None and linha[0] == mtime_atual and not forcar:
            return 0

        self._conexao.execute("DELETE FROM conhecimento WHERE arquivo = ?", (str(caminho),))
        trechos = _extrair_trechos(caminho)
        for secao, texto in trechos:
            self._conexao.execute(
                "INSERT INTO conhecimento(texto, arquivo, secao) VALUES (?, ?, ?)",
                (texto, str(caminho), secao),
            )
        self._conexao.execute(
            "INSERT INTO conhecimento_arquivos(caminho, mtime) VALUES (?, ?) "
            "ON CONFLICT(caminho) DO UPDATE SET mtime = excluded.mtime",
            (str(caminho), mtime_atual),
        )
        self._conexao.commit()
        return len(trechos)

    def ingerir_diretorio(self, diretorio: Path) -> int:
        total = 0
        for caminho in sorted(diretorio.rglob("*")):
            if caminho.is_file() and caminho.suffix.lower() in EXTENSOES_SUPORTADAS:
                total += self.ingerir_arquivo(caminho)
        return total

    def buscar(self, consulta: str, limite: int = 5) -> list[Trecho]:
        try:
            cursor = self._conexao.execute(
                "SELECT texto, arquivo, secao FROM conhecimento "
                "WHERE conhecimento MATCH ? ORDER BY rank LIMIT ?",
                (construir_consulta_fts5(consulta), limite),
            )
        except sqlite3.OperationalError:
            return []
        return [
            Trecho(arquivo=arquivo, secao=secao, texto=texto)
            for texto, arquivo, secao in cursor.fetchall()
        ]

    def fechar(self) -> None:
        self._conexao.close()
