from pathlib import Path

from jarvis.observability.auditoria import RegistradorAuditoria, RegistroAuditoria


def _registro(acao: str) -> RegistroAuditoria:
    return RegistroAuditoria(
        acao=acao,
        argumentos_seguros={},
        resultado="sucesso",
        duracao_segundos=0.0,
    )


def test_registra_e_le_de_volta(tmp_path: Path) -> None:
    caminho = tmp_path / "auditoria.jsonl"
    registrador = RegistradorAuditoria(caminho)

    registrador.registrar(
        RegistroAuditoria(
            acao="fs.read",
            argumentos_seguros={"caminho": "notas.txt"},
            resultado="sucesso",
            duracao_segundos=0.01,
        )
    )

    registros = registrador.ler_todos()

    assert len(registros) == 1
    assert registros[0].acao == "fs.read"
    assert registros[0].resultado == "sucesso"
    assert registros[0].indice == 1


def test_indices_sao_sequenciais_e_estaveis_entre_sessoes(tmp_path: Path) -> None:
    caminho = tmp_path / "auditoria.jsonl"
    registrador = RegistradorAuditoria(caminho)

    registrador.registrar(_registro("primeira"))
    registrador.registrar(_registro("segunda"))

    consulta_antiga = {r.indice: r.acao for r in registrador.ler_todos()}
    assert consulta_antiga[1] == "primeira"
    assert consulta_antiga[2] == "segunda"

    registrador.registrar(_registro("terceira"))

    consulta_nova = {r.indice: r.acao for r in registrador.ler_todos()}
    assert consulta_nova[1] == "primeira"
    assert consulta_nova[2] == "segunda"
    assert consulta_nova[3] == "terceira"


def test_arquivo_legado_sem_indice_recebe_ordem_de_posicao(tmp_path: Path) -> None:
    caminho = tmp_path / "auditoria.jsonl"
    caminho.write_text(
        '{"acao":"velha-1","argumentos_seguros":{},"resultado":"ok","duracao_segundos":0.0,"custo_estimado_usd":0.0,"quando":"x"}\n'
        '{"acao":"velha-2","argumentos_seguros":{},"resultado":"ok","duracao_segundos":0.0,"custo_estimado_usd":0.0,"quando":"y"}\n'
    )
    registrador = RegistradorAuditoria(caminho)

    registros = registrador.ler_todos()

    assert [r.indice for r in registros] == [1, 2]
    registrador.registrar(_registro("nova"))
    assert [r.indice for r in registrador.ler_todos()] == [1, 2, 3]
    assert registrador.ler_todos()[2].acao == "nova"


def test_e_append_only(tmp_path: Path) -> None:
    caminho = tmp_path / "auditoria.jsonl"
    registrador = RegistradorAuditoria(caminho)

    for indice in range(3):
        registrador.registrar(_registro(f"acao-{indice}"))

    assert len(registrador.ler_todos()) == 3
