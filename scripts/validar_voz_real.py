"""Script manual de validação real do pipeline de voz (M8/V1-V3): TTS sintetiza uma frase,
STT transcreve o áudio de volta. Não faz parte da suíte de testes (baixa modelos reais, usa
rede na primeira vez) — rodar manualmente com `.venv/bin/python scripts/validar_voz_real.py`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jarvis.providers.stt import WhisperSTTProvider  # noqa: E402
from jarvis.providers.tts import PiperTTSProvider  # noqa: E402

DIRETORIO_MODELOS = Path.home() / "jarvis" / "dados" / "modelos_voz"
FRASE_ORIGINAL = "o rato roeu a roupa do rei de roma"

print("carregando Piper (pode baixar o modelo na primeira vez)...")
t0 = time.time()
tts = PiperTTSProvider(voz="pt_BR-faber-medium", diretorio_modelos=DIRETORIO_MODELOS)
print(f"  ok em {time.time() - t0:.1f}s")

print(f"sintetizando: '{FRASE_ORIGINAL}'")
t0 = time.time()
sinal, taxa = tts.sintetizar(FRASE_ORIGINAL)
print(f"  ok em {time.time() - t0:.1f}s — {sinal.shape[0]} amostras a {taxa}Hz")

print("carregando Whisper (pode baixar o modelo na primeira vez)...")
t0 = time.time()
stt = WhisperSTTProvider(modelo="small", idioma="pt")
print(f"  ok em {time.time() - t0:.1f}s")

print("transcrevendo o áudio sintetizado de volta...")
t0 = time.time()
# faster-whisper espera 16kHz; o Piper sintetiza a 22050Hz — resample simples pra validar.
import numpy as np  # noqa: E402

duracao_segundos = sinal.shape[0] / taxa
novas_amostras = int(duracao_segundos * 16000)
indices_originais = np.linspace(0, sinal.shape[0] - 1, novas_amostras)
sinal_16k = np.interp(indices_originais, np.arange(sinal.shape[0]), sinal).astype(np.float32)

texto_transcrito = stt.transcrever(sinal_16k, 16000)
print(f"  ok em {time.time() - t0:.1f}s")

print()
print(f"original:    {FRASE_ORIGINAL!r}")
print(f"transcrito:  {texto_transcrito!r}")
print()
print("PASSOU" if FRASE_ORIGINAL.split()[0] in texto_transcrito.lower() else "DIVERGIU (ver acima)")
