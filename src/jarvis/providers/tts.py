"""Provider de TTS (texto → fala) usando Piper, rodando localmente."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from piper.download_voices import download_voice
from piper.voice import PiperVoice

from jarvis.providers.base import ErroProvider


class PiperTTSProvider:
    """TTS local via Piper (ONNX). Baixa o modelo da voz automaticamente no primeiro uso,
    salvando em `diretorio_modelos` — não requer rede depois disso."""

    def __init__(
        self, voz: str = "pt_BR-faber-medium", diretorio_modelos: Path | None = None
    ) -> None:
        diretorio = diretorio_modelos or (Path.home() / "jarvis" / "dados" / "modelos_voz")
        caminho_modelo = diretorio / f"{voz}.onnx"
        caminho_config = diretorio / f"{voz}.onnx.json"

        if not caminho_modelo.exists() or not caminho_config.exists():
            diretorio.mkdir(parents=True, exist_ok=True)
            try:
                download_voice(voz, diretorio)
            except Exception as erro:
                raise ErroProvider(f"não foi possível baixar a voz Piper '{voz}': {erro}") from erro

        try:
            self._voz = PiperVoice.load(caminho_modelo, caminho_config)
        except Exception as erro:
            raise ErroProvider(f"não foi possível carregar a voz Piper '{voz}': {erro}") from erro

    def sintetizar(self, texto: str) -> tuple[np.ndarray, int]:
        if not texto.strip():
            raise ErroProvider("texto vazio, nada para sintetizar")

        try:
            pedacos = list(self._voz.synthesize(texto))
        except Exception as erro:
            raise ErroProvider(f"falha ao sintetizar fala: {erro}") from erro

        if not pedacos:
            raise ErroProvider("Piper não gerou nenhum áudio para o texto")

        sinal = np.concatenate([pedaco.audio_float_array for pedaco in pedacos])
        taxa_amostragem = pedacos[0].sample_rate
        return sinal, taxa_amostragem
