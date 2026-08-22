"""Ferramentas nativas do JARVIS, prontas para o executor rodar via RegistroFerramentas."""

from __future__ import annotations

from jarvis.core.configuracao import Configuracao
from jarvis.memory.armazenamento import RepositorioMemoria
from jarvis.tools.base import Ferramenta, NivelRisco
from jarvis.tools.fs import criar_ferramentas_fs
from jarvis.tools.memoria import criar_ferramentas_memoria
from jarvis.tools.registro import RegistroFerramentas
from jarvis.tools.sistema import criar_ferramentas_sistema

__all__ = [
    "Ferramenta",
    "NivelRisco",
    "RegistroFerramentas",
    "criar_registro_ferramentas_padrao",
]


def criar_registro_ferramentas_padrao(configuracao: Configuracao) -> RegistroFerramentas:
    registro = RegistroFerramentas()
    for ferramenta in criar_ferramentas_fs():
        registro.registrar(ferramenta)

    repositorio_memoria = RepositorioMemoria(configuracao.caminhos.banco_dados)
    for ferramenta in criar_ferramentas_memoria(repositorio_memoria):
        registro.registrar(ferramenta)

    for ferramenta in criar_ferramentas_sistema(configuracao.limites.timeout_por_passo_segundos):
        registro.registrar(ferramenta)

    return registro
