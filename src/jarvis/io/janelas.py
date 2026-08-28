"""Janelas do Hyprland via `hyprctl` (compositor-alvo do projeto): leitura e foco.

`listar_janelas` é só leitura (estado da tela para o agente ter contexto). `focar_janela` muda
o foco por seletor em dois passos: enumera as janelas pela API Lua desta build (`hl.get_windows()`
via `hyprctl eval`, mesma fonte onde `hl.dsp.focus` procura) e resolve o seletor no índice certo,
então dispara `hyprctl dispatch 'hl.dsp.focus({window=hl.get_windows()[N]})'` — a primitiva que de
fato muda o foco. Para Hyprland padrão (sem API Lua), `hyprctl dispatch focuswindow <seletor>`
entra como fallback (ver docs/DECISOES.md).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass


class ErroJanelas(Exception):
    """Levantada quando não é possível consultar ou alterar as janelas abertas."""


class SemApiLua(ErroJanelas):
    """A build do Hyprland não tem a API Lua (usa o dispatch clássico como fallback)."""


@dataclass(frozen=True)
class Janela:
    endereco: str
    classe: str
    titulo: str
    workspace: str
    ativa_no_momento: bool = False


def listar_janelas(binario: str = "hyprctl", timeout_segundos: int = 10) -> list[Janela]:
    try:
        processo = subprocess.run(
            [binario, "clients", "-j"],
            capture_output=True,
            text=True,
            timeout=timeout_segundos,
        )
    except FileNotFoundError as erro:
        raise ErroJanelas(f"binário '{binario}' não encontrado no PATH") from erro
    except subprocess.TimeoutExpired as erro:
        raise ErroJanelas("hyprctl não respondeu a tempo") from erro

    if processo.returncode != 0:
        raise ErroJanelas(f"{binario} falhou: {processo.stderr.strip()}")

    try:
        brutas = json.loads(processo.stdout)
    except json.JSONDecodeError as erro:
        raise ErroJanelas(f"saída inesperada de '{binario} clients -j': {erro}") from erro

    try:
        endereco_ativa = _endereco_janela_ativa(binario, timeout_segundos)
    except ErroJanelas:
        endereco_ativa = None

    return [
        Janela(
            endereco=bruta["address"],
            classe=bruta.get("class", ""),
            titulo=bruta.get("title", ""),
            workspace=str(bruta.get("workspace", {}).get("name", "")),
            ativa_no_momento=bruta["address"] == endereco_ativa,
        )
        for bruta in brutas
    ]


def _endereco_janela_ativa(binario: str, timeout_segundos: int) -> str | None:
    processo = subprocess.run(
        [binario, "activewindow", "-j"],
        capture_output=True,
        text=True,
        timeout=timeout_segundos,
    )
    if processo.returncode != 0 or not processo.stdout.strip():
        return None
    try:
        bruta = json.loads(processo.stdout)
    except json.JSONDecodeError:
        return None
    endereco = bruta.get("address")
    return str(endereco) if endereco else None


def focar_janela(seletor: str, binario: str = "hyprctl", timeout_segundos: int = 10) -> str:
    """Move o foco do teclado para a janela que casa com o seletor.

    O seletor é resolvido contra a lista de janelas da API Lua do próprio Hyprland; a primeira
    janela que casar recebe o foco via `hl.dsp.focus({window=...})` (dispatch). Formas aceitas:

    - `address:0x...` — endereço da janela (como em `hyprctl clients -j`/`listar_janelas`),
      com ou sem o prefixo `0x`;
    - `class:<nome>` — classe/WM_CLASS exata;
    - `title:<trecho>` — substring do título;
    - nome livre — casa com classe exata ou substring do título (case-insensitive).
    """
    if not seletor.strip():
        raise ErroJanelas("seletor de janela vazio")

    modo, alvo = _normalizar_seletor(seletor)
    if not alvo:
        raise ErroJanelas("seletor de janela vazio")

    try:
        janelas = _janelas_lua(binario, timeout_segundos)
    except SemApiLua:
        return _focar_classico(seletor, binario, timeout_segundos)

    indice = _indice_do_seletor(janelas, modo, alvo)
    if indice is None:
        raise ErroJanelas("nenhuma janela casa com o seletor")

    try:
        via_lua = _rodar(
            binario,
            ["dispatch", f"hl.dsp.focus({{window=hl.get_windows()[{indice}]}})"],
            timeout_segundos,
        )
    except FileNotFoundError as erro:
        raise ErroJanelas(f"binário '{binario}' não encontrado no PATH") from erro
    except subprocess.TimeoutExpired as erro:
        raise ErroJanelas("hyprctl não respondeu a tempo") from erro

    if not _falhou(via_lua):
        return "ok"

    saida_lua = via_lua.stderr.strip() or via_lua.stdout.strip()
    if _lua_api_ausente(saida_lua):
        return _focar_classico(seletor, binario, timeout_segundos)

    raise ErroJanelas(f"não foi possível focar '{seletor}': {saida_lua}")


def _normalizar_seletor(seletor: str) -> tuple[str, str]:
    for prefixo, modo in (("address:", "endereco"), ("class:", "classe"), ("title:", "titulo")):
        if seletor.startswith(prefixo):
            alvo = seletor[len(prefixo) :].strip()
            if prefixo == "address:":
                alvo = alvo[2:] if alvo[:2].lower() == "0x" else alvo
            elif alvo.startswith("(") and alvo.endswith(")"):
                alvo = alvo[1:-1]
            return modo, alvo
    return "livre", seletor.strip()


def _janelas_lua(binario: str, timeout_segundos: int) -> list[tuple[int, str, str, str]]:
    """Enumera as janelas pelo lado da API Lua (`hl.get_windows()`), fonte do `hl.dsp.focus`.

    Retorna `(indice, endereco, classe, titulo)` — o endereço sem o prefixo `0x`, para casar
    com o seletor normalizado. A enumeração usa o "truque do error": esta build do hyprctl não
    expõe valor de retorno do `eval` (só imprime "ok"), então o chunk termina em `error(s)` e a
    lista sai no corpo da mensagem.
    """
    chunk = (
        "local ws=hl.get_windows(); local s=''; "
        'for i=1,#ws do s=s..tostring(ws[i].address).."\\t"..tostring(ws[i].class).."\\t"..'
        'tostring(ws[i].title).."\\t"..tostring(i).."\\n" end; error(s)'
    )
    try:
        processo = _rodar(binario, ["eval", chunk], timeout_segundos)
    except FileNotFoundError as erro:
        raise ErroJanelas(f"binário '{binario}' não encontrado no PATH") from erro
    except subprocess.TimeoutExpired as erro:
        raise ErroJanelas("hyprctl não respondeu a tempo") from erro

    saida = processo.stdout.strip() or processo.stderr.strip()
    if _lua_api_ausente(saida):
        raise SemApiLua("sem API Lua do Hyprland (fallback para dispatch clássico)")

    corresponde = re.match(r"^error: \[string .*?\]:\d+: (?P<corpo>.*)$", saida, flags=re.DOTALL)
    if corresponde is None:
        raise ErroJanelas(f"saída inesperada de 'hyprctl eval': {saida[:200]}")

    janelas: list[tuple[int, str, str, str]] = []
    for linha in corresponde.group("corpo").split("\n"):
        campos = linha.split("\t")
        if len(campos) != 4:
            continue
        endereco, classe, titulo, indice = campos
        sem_prefixo = endereco[2:] if endereco[:2].lower() == "0x" else endereco
        janelas.append((int(indice), sem_prefixo, classe, titulo))
    return janelas


def _indice_do_seletor(
    janelas: list[tuple[int, str, str, str]], modo: str, alvo: str
) -> int | None:
    alvo_minusculo = alvo.lower()
    for indice, endereco, classe, titulo in janelas:
        if modo == "endereco":
            casa = alvo == endereco
        elif modo == "classe":
            casa = alvo == classe
        elif modo == "titulo":
            casa = alvo in titulo
        else:
            casa = (
                alvo == classe
                or alvo_minusculo in classe.lower()
                or alvo_minusculo in titulo.lower()
            )
        if casa:
            return indice
    return None


def _focar_classico(seletor: str, binario: str, timeout_segundos: int) -> str:
    try:
        classico = _rodar(binario, ["dispatch", "focuswindow", seletor], timeout_segundos)
    except FileNotFoundError as erro:
        raise ErroJanelas(f"binário '{binario}' não encontrado no PATH") from erro
    except subprocess.TimeoutExpired as erro:
        raise ErroJanelas("hyprctl não respondeu a tempo") from erro
    if not _falhou(classico):
        return "ok"
    raise ErroJanelas(
        f"não foi possível focar '{seletor}': {classico.stderr.strip() or classico.stdout.strip()}"
    )


def _falhou(processo: subprocess.CompletedProcess[str]) -> bool:
    saida = (processo.stderr or processo.stdout or "").strip().lower()
    return processo.returncode != 0 or saida.startswith(("error:", "warning:"))


def _lua_api_ausente(saida: str) -> bool:
    saida_minuscula = saida.lower()
    return (
        "global 'hl'" in saida
        or "nil value" in saida
        or "invalid command" in saida_minuscula
        or "unknown command" in saida_minuscula
    )


def _rodar(
    binario: str, argumentos: list[str], timeout_segundos: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [binario, *argumentos],
        capture_output=True,
        text=True,
        timeout=timeout_segundos,
    )
