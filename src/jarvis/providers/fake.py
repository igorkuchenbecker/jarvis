"""Providers determinísticos usados só nos testes: nunca tocam rede, disco ou CLI real."""

from __future__ import annotations

from pathlib import Path

from jarvis.providers.base import ErroProvider


class FakeProvider:
    def __init__(self, respostas: list[str]) -> None:
        self._respostas = list(respostas)
        self.historico: list[str] = []

    def enviar(self, mensagem: str) -> str:
        self.historico.append(mensagem)
        if not self._respostas:
            raise ErroProvider("FakeProvider ficou sem respostas roteirizadas")
        return self._respostas.pop(0)

    def reiniciar(self) -> None:
        self.historico.clear()


class FakeVisionProvider:
    def __init__(self, respostas: list[str]) -> None:
        self._respostas = list(respostas)
        self.historico: list[tuple[Path, str]] = []

    def analisar(self, caminho_imagem: Path, pergunta: str) -> str:
        self.historico.append((caminho_imagem, pergunta))
        if not self._respostas:
            raise ErroProvider("FakeVisionProvider ficou sem respostas roteirizadas")
        return self._respostas.pop(0)
