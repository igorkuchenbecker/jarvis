from pathlib import Path

from jarvis.observability.auditoria import RegistradorAuditoria, RegistroAuditoria


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


def test_e_append_only(tmp_path: Path) -> None:
    caminho = tmp_path / "auditoria.jsonl"
    registrador = RegistradorAuditoria(caminho)

    for indice in range(3):
        registrador.registrar(
            RegistroAuditoria(
                acao=f"acao-{indice}",
                argumentos_seguros={},
                resultado="sucesso",
                duracao_segundos=0.0,
            )
        )

    assert len(registrador.ler_todos()) == 3
