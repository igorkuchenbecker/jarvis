from pathlib import Path

import pytest

from jarvis.core.configuracao import Configuracao, ConfiguracaoCaminhos
from jarvis.tools import criar_registro_ferramentas_padrao
from jarvis.tools.base import Ferramenta, NivelRisco
from jarvis.tools.registro import RegistroFerramentas


def test_registrar_e_obter_ferramenta() -> None:
    registro = RegistroFerramentas()
    ferramenta = Ferramenta(
        nome="teste.eco",
        descricao="devolve o que recebeu",
        risco=NivelRisco.READ_ONLY,
        schema_argumentos={"type": "object", "properties": {}},
        executar=lambda argumentos: argumentos,
    )

    registro.registrar(ferramenta)

    assert registro.obter("teste.eco") is ferramenta
    assert registro.obter("nao.existe") is None


def test_nao_permite_registrar_nome_duplicado() -> None:
    registro = RegistroFerramentas()
    ferramenta = Ferramenta(
        nome="teste.eco",
        descricao="",
        risco=NivelRisco.READ_ONLY,
        schema_argumentos={},
        executar=lambda argumentos: None,
    )
    registro.registrar(ferramenta)

    with pytest.raises(ValueError, match="já registrada"):
        registro.registrar(ferramenta)


def test_descrever_para_prompt_lista_todas_as_ferramentas() -> None:
    registro = RegistroFerramentas()
    registro.registrar(
        Ferramenta(
            nome="fs.read",
            descricao="lê um arquivo",
            risco=NivelRisco.READ_ONLY,
            schema_argumentos={"type": "object", "properties": {"caminho": {"type": "string"}}},
            executar=lambda argumentos: None,
        )
    )

    descricao = registro.descrever_para_prompt()

    assert "fs.read(caminho)" in descricao
    assert "lê um arquivo" in descricao


def test_criar_registro_ferramentas_padrao_inclui_fs_e_memoria(tmp_path: Path) -> None:
    configuracao = Configuracao(
        caminhos=ConfiguracaoCaminhos(banco_dados=tmp_path / "jarvis.db")
    )

    registro = criar_registro_ferramentas_padrao(configuracao)

    nomes = {ferramenta.nome for ferramenta in registro.todas()}
    assert {"fs.read", "fs.write", "fs.list", "memory.store", "memory.search"} <= nomes
