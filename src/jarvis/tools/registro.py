"""Registro declarativo das ferramentas disponíveis para o executor."""

from __future__ import annotations

from jarvis.tools.base import Ferramenta


class RegistroFerramentas:
    def __init__(self) -> None:
        self._ferramentas: dict[str, Ferramenta] = {}

    def registrar(self, ferramenta: Ferramenta) -> None:
        if ferramenta.nome in self._ferramentas:
            raise ValueError(f"ferramenta já registrada: {ferramenta.nome}")
        self._ferramentas[ferramenta.nome] = ferramenta

    def obter(self, nome: str) -> Ferramenta | None:
        return self._ferramentas.get(nome)

    def todas(self) -> list[Ferramenta]:
        return list(self._ferramentas.values())

    def descrever_para_prompt(self) -> str:
        linhas = []
        for ferramenta in self.todas():
            propriedades = ferramenta.schema_argumentos.get("properties", {})
            argumentos = ", ".join(propriedades.keys())
            linhas.append(f"- {ferramenta.nome}({argumentos}): {ferramenta.descricao}")
        return "\n".join(linhas)
