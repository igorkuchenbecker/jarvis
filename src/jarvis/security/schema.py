"""Validação mínima de argumentos de ferramenta contra um subconjunto simples de JSON Schema.

Cobre só o que as ferramentas do JARVIS precisam (object/properties/required/additionalProperties
e os tipos string/integer/number/boolean/array/object) — não é um validador de JSON Schema
completo. Decisão registrada em docs/DECISOES.md: evita puxar a biblioteca `jsonschema` (e a
cadeia de dependências dela) só para schemas simples e planos.
"""

from __future__ import annotations

from typing import Any

_TIPOS_JSON: dict[str, type] = {
    "string": str,
    "boolean": bool,
    "array": list,
    "object": dict,
}


class ErroValidacao(Exception):
    """Levantada quando os argumentos de uma ação não batem com o schema da ferramenta."""


def _tipo_compativel(valor: Any, tipo_esperado: str) -> bool:
    if tipo_esperado == "integer":
        return isinstance(valor, int) and not isinstance(valor, bool)
    if tipo_esperado == "number":
        return isinstance(valor, int | float) and not isinstance(valor, bool)
    tipo_python = _TIPOS_JSON.get(tipo_esperado)
    if tipo_python is None:
        return True
    return isinstance(valor, tipo_python)


def validar_schema(argumentos: dict[str, Any], schema: dict[str, Any]) -> None:
    if not isinstance(argumentos, dict):
        raise ErroValidacao("argumentos devem ser um objeto")

    propriedades = schema.get("properties", {})
    for campo in schema.get("required", []):
        if campo not in argumentos:
            raise ErroValidacao(f"campo obrigatório ausente: '{campo}'")

    permite_extras = schema.get("additionalProperties", True)
    for chave, valor in argumentos.items():
        if chave not in propriedades:
            if not permite_extras:
                raise ErroValidacao(f"campo não permitido: '{chave}'")
            continue
        tipo_esperado = propriedades[chave].get("type")
        if tipo_esperado and not _tipo_compativel(valor, tipo_esperado):
            raise ErroValidacao(f"campo '{chave}' deveria ser do tipo '{tipo_esperado}'")
