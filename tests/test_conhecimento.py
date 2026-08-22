"""Testes de memory/conhecimento.py. O PDF de teste é escrito à mão (formato mínimo bem
conhecido) para não depender de nenhuma biblioteca de geração de PDF — só o `pypdf` que já é
dependência de produção para LER.
"""

import os
import time
from pathlib import Path

from jarvis.memory.conhecimento import RepositorioConhecimento


def _escrever_pdf_minimo(caminho: Path, texto: str) -> None:
    conteudo_stream = f"BT /F1 24 Tf 72 700 Td ({texto}) Tj ET".encode()
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(conteudo_stream)).encode()
        + b" >>\nstream\n"
        + conteudo_stream
        + b"\nendstream",
    ]

    partes = [b"%PDF-1.4\n"]
    posicoes = []
    for indice, corpo in enumerate(objetos, start=1):
        posicoes.append(sum(len(p) for p in partes))
        partes.append(f"{indice} 0 obj\n".encode() + corpo + b"\nendobj\n")

    inicio_xref = sum(len(p) for p in partes)
    partes.append(f"xref\n0 {len(objetos) + 1}\n".encode())
    partes.append(b"0000000000 65535 f \n")
    for posicao in posicoes:
        partes.append(f"{posicao:010d} 00000 n \n".encode())
    partes.append(
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n"
        "%%EOF".encode()
    )

    caminho.write_bytes(b"".join(partes))


def test_ingerir_markdown_divide_por_cabecalho(tmp_path: Path) -> None:
    arquivo = tmp_path / "notas.md"
    arquivo.write_text(
        "# Introdução\ntexto da introdução\n\n## Instalação\npara instalar, rode X\n",
        encoding="utf-8",
    )
    repositorio = RepositorioConhecimento(tmp_path / "jarvis.db")

    quantidade = repositorio.ingerir_arquivo(arquivo)

    assert quantidade == 2
    resultados = repositorio.buscar("instalar")
    assert len(resultados) == 1
    assert resultados[0].secao == "Instalação"
    assert resultados[0].arquivo == "notas.md"
    assert resultados[0].citacao() == "[notas.md § Instalação]"


def test_ingerir_txt_e_um_trecho_unico_sem_secao(tmp_path: Path) -> None:
    arquivo = tmp_path / "lembrete.txt"
    arquivo.write_text("não esquecer de regar as plantas", encoding="utf-8")
    repositorio = RepositorioConhecimento(tmp_path / "jarvis.db")

    repositorio.ingerir_arquivo(arquivo)

    resultados = repositorio.buscar("plantas")
    assert len(resultados) == 1
    assert resultados[0].secao == ""
    assert resultados[0].citacao() == "[lembrete.txt]"


def test_ingerir_pdf_extrai_texto_por_pagina(tmp_path: Path) -> None:
    arquivo = tmp_path / "documento.pdf"
    _escrever_pdf_minimo(arquivo, "conteudo do pdf de teste")
    repositorio = RepositorioConhecimento(tmp_path / "jarvis.db")

    quantidade = repositorio.ingerir_arquivo(arquivo)

    assert quantidade == 1
    resultados = repositorio.buscar("conteudo")
    assert len(resultados) == 1
    assert resultados[0].secao == "página 1"
    assert resultados[0].arquivo == "documento.pdf"


def test_reindexar_sem_mudanca_de_mtime_nao_duplica(tmp_path: Path) -> None:
    arquivo = tmp_path / "notas.md"
    arquivo.write_text("# Título\nconteúdo original\n", encoding="utf-8")
    repositorio = RepositorioConhecimento(tmp_path / "jarvis.db")

    repositorio.ingerir_arquivo(arquivo)
    quantidade_segunda_vez = repositorio.ingerir_arquivo(arquivo)

    assert quantidade_segunda_vez == 0
    assert len(repositorio.buscar("conteúdo")) == 1


def test_reindexar_apos_mudanca_de_mtime_atualiza_conteudo(tmp_path: Path) -> None:
    arquivo = tmp_path / "notas.md"
    arquivo.write_text("# Título\nconteúdo velho\n", encoding="utf-8")
    repositorio = RepositorioConhecimento(tmp_path / "jarvis.db")
    repositorio.ingerir_arquivo(arquivo)

    time.sleep(0.01)
    arquivo.write_text("# Título\nconteúdo novo\n", encoding="utf-8")
    os.utime(arquivo, (arquivo.stat().st_atime, arquivo.stat().st_mtime + 5))
    repositorio.ingerir_arquivo(arquivo)

    assert repositorio.buscar("velho") == []
    assert len(repositorio.buscar("novo")) == 1


def test_ingerir_diretorio_pega_todos_os_arquivos_suportados(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# A\nconteúdo a\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("conteúdo b", encoding="utf-8")
    (tmp_path / "c.bin").write_bytes(b"\x00\x01")
    repositorio = RepositorioConhecimento(tmp_path / "jarvis.db")

    total = repositorio.ingerir_diretorio(tmp_path)

    assert total == 2
    assert len(repositorio.buscar("conteúdo")) == 2


def test_busca_sem_resultado_retorna_lista_vazia(tmp_path: Path) -> None:
    repositorio = RepositorioConhecimento(tmp_path / "jarvis.db")

    assert repositorio.buscar("nada disso existe") == []
