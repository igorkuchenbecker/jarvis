import pytest

from jarvis.security.schema import ErroValidacao, validar_schema

SCHEMA = {
    "type": "object",
    "properties": {
        "caminho": {"type": "string"},
        "limite": {"type": "integer"},
    },
    "required": ["caminho"],
    "additionalProperties": False,
}


def test_aceita_argumentos_validos() -> None:
    validar_schema({"caminho": "notas.txt", "limite": 3}, SCHEMA)


def test_recusa_campo_obrigatorio_ausente() -> None:
    with pytest.raises(ErroValidacao, match="obrigatório"):
        validar_schema({}, SCHEMA)


def test_recusa_tipo_errado() -> None:
    with pytest.raises(ErroValidacao, match="tipo"):
        validar_schema({"caminho": 123}, SCHEMA)


def test_recusa_campo_extra_quando_nao_permitido() -> None:
    with pytest.raises(ErroValidacao, match="não permitido"):
        validar_schema({"caminho": "notas.txt", "hack": "1=1"}, SCHEMA)


def test_permite_campo_extra_quando_schema_nao_restringe() -> None:
    schema_permissivo = {"type": "object", "properties": {}, "required": []}
    validar_schema({"qualquer": "coisa"}, schema_permissivo)


def test_booleano_nao_e_aceito_como_inteiro() -> None:
    with pytest.raises(ErroValidacao, match="tipo"):
        validar_schema({"caminho": "a", "limite": True}, SCHEMA)
