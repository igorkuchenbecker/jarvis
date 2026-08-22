"""Canal de entrada/saída de áudio do JARVIS: dispositivos, captura, reprodução e corte de silêncio.

Nenhuma função aqui decide nada sobre o agente — é infraestrutura pura de E/S, no mesmo espírito
do restante de `io`: sem acesso a `security`, sem lógica de negócio.
"""

from __future__ import annotations

import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import sounddevice as sd

TAXA_AMOSTRAGEM_PADRAO = 16000


class AudioIndisponivel(Exception):
    """Levantada quando não há dispositivo de áudio utilizável ou uma operação de E/S falha."""


@dataclass(frozen=True)
class DispositivoAudio:
    indice: int
    nome: str
    canais_entrada: int
    canais_saida: int


def listar_dispositivos() -> list[DispositivoAudio]:
    """Lista os dispositivos de áudio conhecidos pelo PortAudio. Nunca lança por ausência de mic."""
    try:
        dispositivos_brutos = sd.query_devices()
    except Exception as erro:
        raise AudioIndisponivel(
            f"não foi possível consultar dispositivos de áudio: {erro}"
        ) from erro

    return [
        DispositivoAudio(
            indice=indice,
            nome=str(bruto["name"]),
            canais_entrada=int(bruto["max_input_channels"]),
            canais_saida=int(bruto["max_output_channels"]),
        )
        for indice, bruto in enumerate(dispositivos_brutos)
    ]


def dispositivo_entrada_padrao(dispositivos: list[DispositivoAudio]) -> DispositivoAudio | None:
    return next((d for d in dispositivos if d.canais_entrada > 0), None)


def dispositivo_saida_padrao(dispositivos: list[DispositivoAudio]) -> DispositivoAudio | None:
    return next((d for d in dispositivos if d.canais_saida > 0), None)


def dispositivo_padrao_do_sistema(tipo: Literal["input", "output"]) -> DispositivoAudio | None:
    """Pergunta ao PortAudio qual dispositivo ele usaria por padrão para `tipo`.

    Isto respeita o roteamento do PipeWire/Pulse (o pseudo-dispositivo "default", que faz
    resample conforme necessário), ao contrário de simplesmente pegar o primeiro item de
    `listar_dispositivos()` — que pode ser um dispositivo ALSA cru com taxa de amostragem fixa
    (ex.: uma saída HDMI a 44100Hz que rejeita 16000Hz). Ver decisão em docs/DECISOES.md.
    """
    try:
        bruto = sd.query_devices(kind=tipo)
    except Exception:
        return None
    return DispositivoAudio(
        indice=int(bruto["index"]),
        nome=str(bruto["name"]),
        canais_entrada=int(bruto["max_input_channels"]),
        canais_saida=int(bruto["max_output_channels"]),
    )


def gerar_beep(
    frequencia_hz: float = 880.0,
    duracao_segundos: float = 0.2,
    taxa_amostragem: int = TAXA_AMOSTRAGEM_PADRAO,
) -> np.ndarray:
    """Gera um tom senoidal simples em memória, sem depender de nenhum arquivo de áudio externo."""
    quantidade_amostras = int(duracao_segundos * taxa_amostragem)
    tempo = np.linspace(0, duracao_segundos, quantidade_amostras, endpoint=False)
    onda = 0.3 * np.sin(2 * math.pi * frequencia_hz * tempo)
    return onda.astype(np.float32)


def aparar_silencio(
    sinal: np.ndarray,
    taxa_amostragem: int = TAXA_AMOSTRAGEM_PADRAO,
    limiar_rms: float = 0.01,
    tamanho_janela_segundos: float = 0.02,
) -> np.ndarray:
    """Corta o silêncio das pontas de um sinal usando energia (RMS) por janela.

    Decisão registrada em docs/DECISOES.md: substitui webrtcvad/silero-vad, que trariam uma
    dependência não mantida (pkg_resources removido do setuptools moderno) ou peso desproporcional
    (torch) só para esta finalidade de aparar as pontas de uma gravação push-to-talk.
    """
    if sinal.size == 0:
        return sinal

    tamanho_janela = max(1, int(tamanho_janela_segundos * taxa_amostragem))
    quantidade_janelas = math.ceil(sinal.size / tamanho_janela)

    indices_com_voz = []
    for indice_janela in range(quantidade_janelas):
        inicio = indice_janela * tamanho_janela
        fim = min(inicio + tamanho_janela, sinal.size)
        janela = sinal[inicio:fim]
        rms = float(np.sqrt(np.mean(np.square(janela))))
        if rms >= limiar_rms:
            indices_com_voz.append(indice_janela)

    if not indices_com_voz:
        return sinal[:0]

    primeira_janela_com_voz = indices_com_voz[0]
    ultima_janela_com_voz = indices_com_voz[-1]
    inicio_corte = primeira_janela_com_voz * tamanho_janela
    fim_corte = min((ultima_janela_com_voz + 1) * tamanho_janela, sinal.size)
    return sinal[inicio_corte:fim_corte]


def capturar(
    duracao_segundos: float,
    taxa_amostragem: int = TAXA_AMOSTRAGEM_PADRAO,
    dispositivo: int | None = None,
) -> np.ndarray:
    """Grava `duracao_segundos` de áudio mono do microfone, traduzindo falhas do PortAudio."""
    try:
        gravacao = sd.rec(
            int(duracao_segundos * taxa_amostragem),
            samplerate=taxa_amostragem,
            channels=1,
            dtype="float32",
            device=dispositivo,
        )
        sd.wait()
    except Exception as erro:
        raise AudioIndisponivel(f"não foi possível capturar áudio do microfone: {erro}") from erro
    resultado: np.ndarray = gravacao.reshape(-1)
    return resultado


def tocar(
    sinal: np.ndarray,
    taxa_amostragem: int = TAXA_AMOSTRAGEM_PADRAO,
    dispositivo: int | None = None,
) -> None:
    """Reproduz um sinal mono na saída de áudio. Nunca deixa a exceção do PortAudio vazar crua."""
    try:
        sd.play(sinal, samplerate=taxa_amostragem, device=dispositivo)
        sd.wait()
    except Exception as erro:
        raise AudioIndisponivel(f"não foi possível reproduzir áudio: {erro}") from erro


def salvar_wav(
    caminho: Path, sinal: np.ndarray, taxa_amostragem: int = TAXA_AMOSTRAGEM_PADRAO
) -> None:
    amostras_limitadas = np.clip(sinal, -1.0, 1.0)
    amostras_inteiras = (amostras_limitadas * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa_amostragem)
        arquivo.writeframes(amostras_inteiras.tobytes())


def carregar_wav(caminho: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(caminho), "rb") as arquivo:
        taxa_amostragem = arquivo.getframerate()
        quadros = arquivo.readframes(arquivo.getnframes())
    amostras_inteiras = np.frombuffer(quadros, dtype=np.int16)
    sinal = amostras_inteiras.astype(np.float32) / 32767.0
    return sinal, taxa_amostragem
