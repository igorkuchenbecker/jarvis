# Registro de decisões técnicas

Formato: data | decisão | motivo | alternativas consideradas | consequências

---

**2026-08-22** | Estrutura em `src/jarvis/` (src layout) em vez de pastas soltas na raiz | O
master prompt nomeia um módulo `io`, que colidiria com o módulo `io` da stdlib do Python se
ficasse solto no topo do sys.path; empacotar tudo sob `jarvis.io` elimina o conflito sem mudar
o nome pedido | (a) manter `io/` na raiz e confiar que nunca haveria colisão de import — rejeitada
por fragilidade; (b) renomear o módulo para `interface/` — rejeitada por contrariar o master
prompt sem necessidade | Todo import interno passa a ser `from jarvis.core import ...` etc.;
`pyproject.toml` usa `tool.setuptools.packages.find` com `where = ["src"]`.

**2026-08-22** | `target-version`/`python_version` do ruff e mypy fixados em 3.14 | A máquina-alvo
tem Python 3.14.6 instalado e o ambiente é criado com `python3.14 -m venv`; testado manualmente que
ruff 0.16.4 e mypy 2.3.1 aceitam `py314`/`"3.14"` sem erro | Usar 3.13 como teto "seguro" —
rejeitada por não refletir o ambiente real da máquina-alvo | Nenhuma sintaxe exclusiva de 3.14 é
usada ainda; a decisão só evita checagem de compatibilidade com uma versão que não é a instalada.

**2026-08-22** | `jarvis` como comando de console aponta para `jarvis.io.cli:principal`, ainda que
a conversa real só chegue no M1 | O M0 já define o ponto de entrada da CLI para que M1 apenas
implemente a lógica, sem mexer em empacotamento | Deixar o entry point para M1 — rejeitada porque
adiaria uma decisão de estrutura que é barata de tomar agora | `jarvis` como comando funciona desde
o M0, mas hoje só imprime uma mensagem de fundação.

---

## M8 — Voz

**2026-08-22** | M1-M7 ainda não existem (só M0 foi construído); o marco M8 (voz) foi solicitado
diretamente, fora de ordem | Instrução explícita da missão M8 para começar por V0-V2 (fundação de
áudio, STT, TTS), que não dependem de core loop nem de ferramentas | V0-V2 são construídos
normalmente por serem autocontidos em `providers`/`io`. V3 (conversa por voz ponta-a-ponta usando
"o mesmo core loop do chat textual" e "ferramentas já existentes") depende de M1 (core loop +
LLMProvider) e M2 (tools) — que não existem. Alternativas: (a) implementar M1/M2 mínimos agora só
para destravar V3 — rejeitada por sair do escopo desta missão (M8) e duplicar trabalho que será
refeito com mais cuidado quando M1/M2 forem o marco corrente; (b) pular V3 inteiramente até M1/M2
existirem — rejeitada porque o valor de "conversar por voz" pode ser demonstrado com uma ponte
mínima direta ao LLM | Quando V3 for implementado, o escopo será reduzido: texto da fala vai direto
a um `LLMProvider` (sem tool-calling), produzindo respostas faladas coerentes; os exemplos de DoD
que dependem de ferramentas ("salve uma nota", "leia essa nota") ficam registrados como pendência
para quando M2 existir, substituídos por perguntas que não dependem de tools (ex.: "que horas são"
respondido localmente, perguntas gerais respondidas pelo LLM). Isso será revisitado explicitamente
na fatia V3.

**2026-08-22** | VAD implementado como energia do sinal (RMS) em Python/numpy puro, em vez de
`webrtcvad` ou `silero-vad` como sugerido no roteiro | `webrtcvad` (pacote de 2019, última
publicação years atrás) importa `pkg_resources` em tempo de execução; o `setuptools` moderno
(84.0, o disponível via pip hoje) removeu `pkg_resources` do pacote, então `import webrtcvad`
quebra com `ModuleNotFoundError` mesmo com `setuptools` instalado. `silero-vad` exigiria `torch`
como dependência só para cortar silêncio nas pontas de uma gravação push-to-talk — peso
desproporcional ao problema | (a) fixar `setuptools<81` só para satisfazer o `webrtcvad` —
rejeitada por reintroduzir uma dependência não mantida e travar a versão do setuptools do venv
inteiro por causa de um detalhe de VAD; (b) `silero-vad`/torch — rejeitada pelo custo de
instalação e VRAM/CPU para um corte de silêncio nas pontas, quando V3 já usa push-to-talk via
ENTER (não precisa de VAD em tempo real, só aparar silêncio das pontas do WAV capturado) | VAD
vira uma função pura (`aparar_silencio`) em `jarvis.io.audio`, testável sem dependência externa
nenhuma; se um VAD mais sofisticado for necessário no futuro (barge-in, escuta contínua — fora do
escopo desta missão), reavaliar então com benchmark.

**2026-08-22** | `capturar()`/`tocar()` usam `device=None` por padrão (deixando o PortAudio
resolver), e a checagem de dispositivo padrão consulta `sd.query_devices(kind=...)` em vez de
pegar o primeiro item de `listar_dispositivos()` | Bug reproduzido na máquina real: o primeiro
dispositivo de saída na lista bruta do PortAudio era `HDA NVidia: HDMI 1 (hw:0,7)`, um dispositivo
ALSA cru travado em 44100Hz, que rejeitou a captura/reprodução a 16000Hz
(`Invalid sample rate [PaErrorCode -9997]`); o pseudo-dispositivo `default`/`pulse` (índice 8 nesta
máquina) já roteia pelo PipeWire e faz resample automaticamente | Continuar escolhendo "o primeiro
dispositivo com canais compatíveis" da lista bruta — rejeitada por ser exatamente a causa do bug:
não há garantia de que o primeiro dispositivo aceite a taxa de amostragem desejada | `config.yaml`
com `voz.dispositivo: auto` agora significa "não fixar nenhum índice, deixar o sistema decidir",
não "primeiro da lista". `dispositivo_padrao_do_sistema()` existe só para exibição amigável do
nome do dispositivo ao usuário; a escolha real de rota de áudio é sempre feita pelo PortAudio.

**2026-08-22** | Dependências de voz (`sounddevice`, `numpy`, `faster-whisper`) isoladas no extra
opcional `voz` do `pyproject.toml`, não nas dependências base do projeto | `config.yaml.example`
já prevê `voz.habilitada: false` por padrão; quem não usa voz não deveria precisar baixar
`faster-whisper`/`ctranslate2` (dependência pesada) só para instalar o `jarvis` | Colocar tudo nas
dependências base — rejeitada por inflar a instalação padrão para quem só quer o modo texto |
Ambiente de desenvolvimento instala com `pip install -e ".[dev,voz]"`; produção decide conforme uso.
