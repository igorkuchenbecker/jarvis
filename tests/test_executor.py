from pathlib import Path

import pytest

from jarvis.observability.auditoria import RegistradorAuditoria
from jarvis.security.executor import Acao, ErroExecucao, Executor
from jarvis.tools.base import Ferramenta, NivelRisco
from jarvis.tools.fs import criar_ferramentas_fs
from jarvis.tools.registro import RegistroFerramentas


def _registro_com_fs() -> RegistroFerramentas:
    registro = RegistroFerramentas()
    for ferramenta in criar_ferramentas_fs():
        registro.registrar(ferramenta)
    return registro


def test_executa_fs_list_dentro_do_jail(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    executor = Executor(_registro_com_fs(), jail_paths=[tmp_path])

    resultado = executor.executar_acao(Acao("fs.list", {"caminho": str(tmp_path)}))

    assert resultado.sucesso
    assert resultado.valor == ["a.txt", "b.txt"]


def test_executa_fs_read_dentro_do_jail(tmp_path: Path) -> None:
    arquivo = tmp_path / "notas.txt"
    arquivo.write_text("conteúdo da nota")
    executor = Executor(_registro_com_fs(), jail_paths=[tmp_path])

    resultado = executor.executar_acao(Acao("fs.read", {"caminho": str(arquivo)}))

    assert resultado.sucesso
    assert resultado.valor == "conteúdo da nota"


def test_executa_fs_write_e_reverte_para_conteudo_anterior(tmp_path: Path) -> None:
    arquivo = tmp_path / "notas.txt"
    arquivo.write_text("versão original")
    executor = Executor(_registro_com_fs(), jail_paths=[tmp_path])
    acao = Acao("fs.write", {"caminho": str(arquivo), "conteudo": "versão nova"})

    resultado = executor.executar_acao(acao)
    assert resultado.sucesso
    assert arquivo.read_text() == "versão nova"

    executor.reverter(acao, resultado.estado_anterior)
    assert arquivo.read_text() == "versão original"


def test_fs_write_em_arquivo_novo_reverte_removendo(tmp_path: Path) -> None:
    arquivo = tmp_path / "novo.txt"
    executor = Executor(_registro_com_fs(), jail_paths=[tmp_path])
    acao = Acao("fs.write", {"caminho": str(arquivo), "conteudo": "conteúdo"})

    resultado = executor.executar_acao(acao)
    assert resultado.sucesso
    assert arquivo.exists()

    executor.reverter(acao, resultado.estado_anterior)
    assert not arquivo.exists()


def test_recusa_ferramenta_desconhecida(tmp_path: Path) -> None:
    executor = Executor(_registro_com_fs(), jail_paths=[tmp_path])

    resultado = executor.executar_acao(Acao("fs.destroi_tudo", {}))

    assert not resultado.sucesso
    assert "desconhecida" in (resultado.erro or "")


def test_recusa_schema_invalido(tmp_path: Path) -> None:
    executor = Executor(_registro_com_fs(), jail_paths=[tmp_path])

    resultado = executor.executar_acao(Acao("fs.read", {}))

    assert not resultado.sucesso
    assert "obrigatório" in (resultado.erro or "")


def test_recusa_travessia_de_caminho_maliciosa(tmp_path: Path) -> None:
    jail = tmp_path / "workspace"
    jail.mkdir()
    executor = Executor(_registro_com_fs(), jail_paths=[jail])

    resultado = executor.executar_acao(
        Acao("fs.read", {"caminho": str(jail / ".." / ".." / "etc" / "passwd")})
    )

    assert not resultado.sucesso
    assert "fora dos diretórios autorizados" in (resultado.erro or "")


def test_fs_read_permite_raiz_de_leitura_extra_fora_do_jail_de_escrita(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fora = tmp_path / "home"
    fora.mkdir()
    (fora / "notas.txt").write_text("fora do workspace")
    executor = Executor(
        _registro_com_fs(), jail_paths=[workspace], jail_paths_leitura=(fora,)
    )

    resultado = executor.executar_acao(Acao("fs.read", {"caminho": str(fora / "notas.txt")}))

    assert resultado.sucesso
    assert resultado.valor == "fora do workspace"


def test_fs_list_permite_raiz_de_leitura_extra_fora_do_jail_de_escrita(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fora = tmp_path / "home"
    fora.mkdir()
    (fora / "a.txt").write_text("a")
    executor = Executor(
        _registro_com_fs(), jail_paths=[workspace], jail_paths_leitura=(fora,)
    )

    resultado = executor.executar_acao(Acao("fs.list", {"caminho": str(fora)}))

    assert resultado.sucesso
    assert resultado.valor == ["a.txt"]


def test_fs_write_recusa_raiz_de_leitura_extra_mesmo_sendo_legivel(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fora = tmp_path / "home"
    fora.mkdir()
    executor = Executor(
        _registro_com_fs(), jail_paths=[workspace], jail_paths_leitura=(fora,)
    )

    resultado = executor.executar_acao(
        Acao("fs.write", {"caminho": str(fora / "novo.txt"), "conteudo": "x"})
    )

    assert not resultado.sucesso
    assert "fora dos diretórios autorizados" in (resultado.erro or "")
    assert not (fora / "novo.txt").exists()


def test_registra_auditoria_de_sucesso_e_erro(tmp_path: Path) -> None:
    caminho_auditoria = tmp_path / "auditoria.jsonl"
    (tmp_path / "workspace").mkdir()
    registrador = RegistradorAuditoria(caminho_auditoria)
    executor = Executor(
        _registro_com_fs(), jail_paths=[tmp_path / "workspace"], auditoria=registrador
    )

    executor.executar_acao(Acao("fs.read", {}))

    registros = registrador.ler_todos()
    assert len(registros) == 1
    assert registros[0].acao == "fs.read"
    assert "erro" in registros[0].resultado


def _registro_com_ferramenta_de_risco(risco: NivelRisco) -> RegistroFerramentas:
    registro = RegistroFerramentas()
    registro.registrar(
        Ferramenta(
            nome="teste.arriscada",
            descricao="",
            risco=risco,
            schema_argumentos={"type": "object", "properties": {}},
            executar=lambda argumentos: "executou",
        )
    )
    return registro


@pytest.mark.parametrize(
    ("nivel_autonomia", "risco", "deveria_rodar"),
    [
        (0, NivelRisco.READ_ONLY, False),
        (1, NivelRisco.READ_ONLY, True),
        (1, NivelRisco.LOW, False),
        (2, NivelRisco.LOW, True),
        (2, NivelRisco.MEDIUM, False),
        (3, NivelRisco.MEDIUM, True),
        (5, NivelRisco.MEDIUM, True),
    ],
)
def test_teto_de_risco_por_nivel_de_autonomia(
    tmp_path: Path, nivel_autonomia: int, risco: NivelRisco, deveria_rodar: bool
) -> None:
    executor = Executor(
        _registro_com_ferramenta_de_risco(risco),
        jail_paths=[tmp_path],
        nivel_autonomia=nivel_autonomia,
    )

    resultado = executor.executar_acao(Acao("teste.arriscada", {}))

    assert resultado.sucesso is deveria_rodar
    if not deveria_rodar:
        assert "autonomia" in (resultado.erro or "")


def test_ferramenta_high_sem_callback_de_aprovacao_e_recusada_por_padrao(tmp_path: Path) -> None:
    executor = Executor(
        _registro_com_ferramenta_de_risco(NivelRisco.HIGH),
        jail_paths=[tmp_path],
        nivel_autonomia=5,
    )

    resultado = executor.executar_acao(Acao("teste.arriscada", {}))

    assert not resultado.sucesso
    assert "aprovação" in (resultado.erro or "")


def test_ferramenta_high_e_recusada_mesmo_com_autonomia_maxima_se_callback_negar(
    tmp_path: Path,
) -> None:
    executor = Executor(
        _registro_com_ferramenta_de_risco(NivelRisco.HIGH),
        jail_paths=[tmp_path],
        nivel_autonomia=5,
        solicitar_aprovacao=lambda acao, ferramenta: False,
    )

    resultado = executor.executar_acao(Acao("teste.arriscada", {}))

    assert not resultado.sucesso


def test_ferramenta_high_roda_quando_callback_aprova(tmp_path: Path) -> None:
    executor = Executor(
        _registro_com_ferramenta_de_risco(NivelRisco.HIGH),
        jail_paths=[tmp_path],
        nivel_autonomia=0,
        solicitar_aprovacao=lambda acao, ferramenta: True,
    )

    resultado = executor.executar_acao(Acao("teste.arriscada", {}))

    assert resultado.sucesso
    assert resultado.valor == "executou"


def test_recusa_binario_fora_da_allowlist(tmp_path: Path) -> None:
    registro = RegistroFerramentas()
    registro.registrar(
        Ferramenta(
            nome="teste.exec",
            descricao="",
            risco=NivelRisco.MEDIUM,
            schema_argumentos={
                "type": "object",
                "properties": {"comando": {"type": "string"}},
                "required": ["comando"],
            },
            executar=lambda argumentos: "rodou",
            campo_binario="comando",
        )
    )
    executor = Executor(
        registro, jail_paths=[tmp_path], allowlist_binarios=("git",), nivel_autonomia=3
    )

    resultado = executor.executar_acao(Acao("teste.exec", {"comando": "curl"}))

    assert not resultado.sucesso
    assert "allowlist" in (resultado.erro or "")


def test_ferramenta_sem_suporte_a_reverter_levanta_erro(tmp_path: Path) -> None:
    registro = RegistroFerramentas()
    registro.registrar(
        Ferramenta(
            nome="teste.sem_reverter",
            descricao="",
            risco=NivelRisco.READ_ONLY,
            schema_argumentos={"type": "object", "properties": {}},
            executar=lambda argumentos: "ok",
        )
    )
    executor = Executor(registro, jail_paths=[tmp_path])
    acao = Acao("teste.sem_reverter", {})
    executor.executar_acao(acao)

    with pytest.raises(ErroExecucao):
        executor.reverter(acao, None)
