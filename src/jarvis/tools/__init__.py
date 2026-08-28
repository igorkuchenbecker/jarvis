"""Ferramentas nativas do JARVIS, prontas para o executor rodar via RegistroFerramentas."""

from __future__ import annotations

import os

from jarvis.core.configuracao import Configuracao
from jarvis.io.gdap import ClienteGdap
from jarvis.memory.armazenamento import RepositorioMemoria
from jarvis.memory.conhecimento import RepositorioConhecimento
from jarvis.providers import ErroProvider, criar_provider_visao
from jarvis.tools.base import Ferramenta, NivelRisco
from jarvis.tools.computador import criar_ferramentas_computador
from jarvis.tools.conhecimento import criar_ferramentas_conhecimento
from jarvis.tools.fs import criar_ferramentas_fs
from jarvis.tools.gdap import criar_ferramentas_gdap
from jarvis.tools.memoria import criar_ferramentas_memoria
from jarvis.tools.registro import RegistroFerramentas
from jarvis.tools.sistema import criar_ferramentas_sistema
from jarvis.tools.visao import criar_ferramentas_visao
from jarvis.tools.web import criar_ferramentas_pesquisa

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

    if configuracao.web.habilitada:
        for ferramenta in criar_ferramentas_pesquisa(
            repositorio_conhecimento,
            timeout_segundos=configuracao.web.timeout_segundos,
            limite_padrao=configuracao.web.limite_padrao,
        ):
            registro.registrar(ferramenta)

    try:
        provider_visao = criar_provider_visao(configuracao)
    except ErroProvider:
        provider_visao = None
    if provider_visao is not None:
        for ferramenta in criar_ferramentas_visao(provider_visao):
            registro.registrar(ferramenta)

    if configuracao.computador.habilitada:
        for ferramenta in criar_ferramentas_computador():
            registro.registrar(ferramenta)

    if configuracao.gdap.habilitada:
        ajustes_gdap = configuracao.gdap
        api_key = os.environ.get(ajustes_gdap.api_key_env) if ajustes_gdap.api_key_env else None
        if ajustes_gdap.api_key_env and not api_key:
            raise ErroProvider(
                f"variável de ambiente '{ajustes_gdap.api_key_env}' não definida — exporte a "
                "API key do GDAP ('gdap system key create jarvis --role engineer') ou remova "
                "'api_key_env' de gdap no config.yaml"
            )
        cliente_gdap = ClienteGdap(
            base_url=ajustes_gdap.base_url,
            api_key=api_key,
            timeout_segundos=ajustes_gdap.timeout_segundos,
        )
        for ferramenta in criar_ferramentas_gdap(cliente_gdap, ajustes_gdap.pipelines_permitidos):
            registro.registrar(ferramenta)

    return registro
