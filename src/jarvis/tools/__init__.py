"""Ferramentas nativas do JARVIS, prontas para o executor rodar via RegistroFerramentas."""

from __future__ import annotations

from jarvis.core.configuracao import Configuracao
from jarvis.memory.armazenamento import RepositorioMemoria
from jarvis.memory.conhecimento import RepositorioConhecimento
from jarvis.providers import ErroProvider, criar_provider_visao
from jarvis.tools.base import Ferramenta, NivelRisco
from jarvis.tools.conhecimento import criar_ferramentas_conhecimento
from jarvis.tools.fs import criar_ferramentas_fs
from jarvis.tools.memoria import criar_ferramentas_memoria
from jarvis.tools.registro import RegistroFerramentas
from jarvis.tools.sistema import criar_ferramentas_sistema
from jarvis.tools.visao import criar_ferramentas_visao

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

    repositorio_conhecimento = RepositorioConhecimento(configuracao.caminhos.banco_dados)
    for ferramenta in criar_ferramentas_conhecimento(repositorio_conhecimento):
        registro.registrar(ferramenta)

    try:
        provider_visao = criar_provider_visao(configuracao)
    except ErroProvider:
        provider_visao = None
    if provider_visao is not None:
        for ferramenta in criar_ferramentas_visao(provider_visao):
            registro.registrar(ferramenta)

    return registro
