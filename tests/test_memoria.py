from pathlib import Path

from jarvis.memory.armazenamento import RepositorioMemoria


def test_armazena_e_busca_por_relevancia(tmp_path: Path) -> None:
    repositorio = RepositorioMemoria(tmp_path / "jarvis.db")

    repositorio.armazenar("o usuário prefere café sem açúcar")
    repositorio.armazenar("a reunião de sexta foi cancelada")

    resultados = repositorio.buscar("café")

    assert resultados == ["o usuário prefere café sem açúcar"]


def test_busca_sem_resultado_retorna_lista_vazia(tmp_path: Path) -> None:
    repositorio = RepositorioMemoria(tmp_path / "jarvis.db")

    assert repositorio.buscar("nada por aqui") == []


def test_busca_com_sintaxe_invalida_nao_lanca(tmp_path: Path) -> None:
    repositorio = RepositorioMemoria(tmp_path / "jarvis.db")
    repositorio.armazenar("qualquer coisa")

    assert repositorio.buscar('"aspas sem fechar') == []


def test_persiste_entre_conexoes(tmp_path: Path) -> None:
    caminho = tmp_path / "jarvis.db"
    RepositorioMemoria(caminho).armazenar("lembrar de regar as plantas")

    resultados = RepositorioMemoria(caminho).buscar("plantas")

    assert resultados == ["lembrar de regar as plantas"]
