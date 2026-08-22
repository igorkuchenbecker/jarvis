from pathlib import Path

from jarvis.core.objetivos import RepositorioObjetivos, Subtarefa


def test_criar_e_obter_objetivo(tmp_path: Path) -> None:
    repositorio = RepositorioObjetivos(tmp_path / "jarvis.db")
    subtarefas = [Subtarefa("fazer a", "a feita"), Subtarefa("fazer b", "b feita")]

    id_objetivo = repositorio.criar("objetivo de teste", subtarefas)
    objetivo = repositorio.obter(id_objetivo)

    assert objetivo is not None
    assert objetivo.descricao == "objetivo de teste"
    assert objetivo.estado == "em_andamento"
    assert objetivo.indice_atual == 0
    assert [s.descricao for s in objetivo.subtarefas] == ["fazer a", "fazer b"]


def test_obter_em_andamento_retorna_o_mais_recente(tmp_path: Path) -> None:
    repositorio = RepositorioObjetivos(tmp_path / "jarvis.db")
    repositorio.criar("primeiro", [Subtarefa("x", "y")])
    segundo_id = repositorio.criar("segundo", [Subtarefa("x", "y")])

    em_andamento = repositorio.obter_em_andamento()

    assert em_andamento is not None
    assert em_andamento.id == segundo_id


def test_obter_em_andamento_ignora_objetivos_concluidos(tmp_path: Path) -> None:
    repositorio = RepositorioObjetivos(tmp_path / "jarvis.db")
    id_objetivo = repositorio.criar("objetivo", [Subtarefa("x", "y")])
    objetivo = repositorio.obter(id_objetivo)
    assert objetivo is not None
    objetivo.estado = "concluido"
    repositorio.salvar_checkpoint(objetivo)

    assert repositorio.obter_em_andamento() is None


def test_salvar_checkpoint_persiste_progresso(tmp_path: Path) -> None:
    caminho = tmp_path / "jarvis.db"
    repositorio = RepositorioObjetivos(caminho)
    id_objetivo = repositorio.criar(
        "objetivo", [Subtarefa("a", "a feita"), Subtarefa("b", "b feita")]
    )
    objetivo = repositorio.obter(id_objetivo)
    assert objetivo is not None
    objetivo.subtarefas[0].estado = "concluida"
    objetivo.indice_atual = 1
    repositorio.salvar_checkpoint(objetivo)

    reaberto = RepositorioObjetivos(caminho).obter(id_objetivo)

    assert reaberto is not None
    assert reaberto.indice_atual == 1
    assert reaberto.subtarefas[0].estado == "concluida"
