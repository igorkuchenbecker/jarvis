"""Provider de STT (fala → texto) usando faster-whisper, rodando localmente."""

from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel

from jarvis.providers.base import ErroProvider


class WhisperSTTProvider:
    """STT local via faster-whisper (CTranslate2). Espera áudio mono float32 a 16kHz.

    Compute type "int8" em CPU é a combinação padrão do faster-whisper para bom desempenho sem
    GPU — usar CUDA exigiria validar cuDNN/cuBLAS na máquina, o que não foi feito ainda (ver
    docs/DECISOES.md); CPU é a escolha simples que funciona sem essa validação extra.
    """

    def __init__(
        self,
        modelo: str = "small",
        idioma: str | None = "pt",
        dispositivo: str = "cpu",
        tipo_computo: str = "int8",
        diretorio_download: str | None = None,
    ) -> None:
        try:
            self._modelo = WhisperModel(
                modelo,
                device=dispositivo,
                compute_type=tipo_computo,
                download_root=diretorio_download,
            )
        except Exception as erro:
            raise ErroProvider(
                f"não foi possível carregar o modelo Whisper '{modelo}': {erro}"
            ) from erro
        self._idioma = idioma

    def transcrever(self, sinal: np.ndarray, taxa_amostragem: int) -> str:
        if sinal.size == 0:
            raise ErroProvider("áudio vazio, nada para transcrever")
        if taxa_amostragem != 16000:
            raise ErroProvider(
                f"faster-whisper espera áudio a 16000Hz, recebido {taxa_amostragem}Hz"
            )

        try:
            segmentos, _info = self._modelo.transcribe(sinal, language=self._idioma)
            texto = " ".join(segmento.text.strip() for segmento in segmentos).strip()
        except Exception as erro:
            raise ErroProvider(f"falha ao transcrever áudio: {erro}") from erro

        if not texto:
            raise ErroProvider("nenhuma fala detectada no áudio")
        return texto
