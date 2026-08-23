"""Script manual de validação real do M9 (computer use): abre um terminal descartável que só
grava o que for digitado num arquivo, confirma foco, digita via evdev, envia Ctrl+D, lê o
arquivo de volta. Não faz parte da suíte de testes (efeitos reais no desktop, ainda que
controlados) — rodar manualmente com `.venv/bin/python scripts/validar_computador_real.py`.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jarvis.io.entrada import digitar as digitar_evdev  # noqa: E402
from jarvis.io.entrada import mover_mouse, tecla  # noqa: E402
from jarvis.io.janelas import listar_janelas  # noqa: E402

ARQUIVO_TESTE = Path("/tmp/jarvis_m9_teste.txt")
TEXTO_ESPERADO = "ola jarvis, teste do m9"

ARQUIVO_TESTE.unlink(missing_ok=True)

print("1) movendo o mouse (sem clicar em nada, so verificando que o cursor real se move)...")
antes = subprocess.run(["hyprctl", "cursorpos"], capture_output=True, text=True).stdout.strip()
mover_mouse(80, 40)
depois = subprocess.run(["hyprctl", "cursorpos"], capture_output=True, text=True).stdout.strip()
print(f"   posição antes: {antes} | depois: {depois} | {'OK' if antes != depois else 'FALHOU'}")

print("2) abrindo terminal descartável (so grava o que digitar num arquivo)...")
processo = subprocess.Popen(["kitty", "-e", "sh", "-c", f"cat > {ARQUIVO_TESTE}"])
time.sleep(1.5)

janelas = listar_janelas()
ativa = next((j for j in janelas if j.ativa_no_momento), None)
print(f"   janela ativa agora: classe={ativa.classe if ativa else '?'}")
if ativa is None or ativa.classe != "kitty":
    print("   AVISO: o terminal novo pode não ter ficado em foco — teste pode falhar por isso.")

print(f"3) digitando via evdev: {TEXTO_ESPERADO!r}")
digitar_evdev(TEXTO_ESPERADO)

print("4) enviando Enter + Ctrl+D (EOF de verdade) para fechar o cat/terminal...")
# Nota de quem rodou isso antes: Ctrl+D com uma linha pendente (sem Enter) so libera a linha
# pro `cat` ler, nao fecha o processo -- e preciso a linha vazia (Enter) antes do EOF de fato.
tecla("enter")
tecla("ctrl+d")
time.sleep(1.0)

processo.wait(timeout=5)

conteudo = ARQUIVO_TESTE.read_text(encoding="utf-8") if ARQUIVO_TESTE.exists() else None
print(f"conteúdo gravado: {conteudo!r}")
print("PASSOU" if conteudo and TEXTO_ESPERADO in conteudo else "FALHOU")

ARQUIVO_TESTE.unlink(missing_ok=True)
