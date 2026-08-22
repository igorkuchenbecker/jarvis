# Estado do projeto JARVIS

**Versão:** 0.1.0 (M0 concluído; M8/V0 — Fundação de áudio em andamento)
**Última atualização:** 2026-08-22

## Feito

### M0 — Fundação
- Repositório git inicializado em `~/jarvis`.
- Layout `src/jarvis/` com pacotes vazios: `core`, `providers`, `tools`, `security`, `memory`,
  `io`, `observability` — prontos para receber código dos próximos marcos.
- `pyproject.toml` com dependências (`rich`, `pyyaml`) e dev (`pytest`, `ruff`, `mypy`), targets
  fixados em Python 3.14.
- `observability/logs.py`: logging estruturado em JSON (stderr + arquivo opcional).
- `observability/auditoria.py`: `RegistradorAuditoria` append-only em JSONL, com testes cobrindo
  gravação, leitura e natureza append-only.
- `config.yaml.example`: autonomia, provedores, limites, allowlists de segurança, caminhos.
- `scripts/check.sh`: roda ruff, mypy --strict e pytest em sequência.
- `docs/DECISOES.md` iniciado; `AGENTS.md` com o contexto do projeto; `CLAUDE.md` symlink.

### M8/V0 — Fundação de áudio (fora de ordem, solicitado diretamente)
- `pyproject.toml`: extra opcional `voz` (`sounddevice`, `numpy`, `faster-whisper`) — não entra
  na instalação padrão, só quando `pip install -e ".[voz]"`.
- `config.yaml.example`: seção `voz` (habilitada, stt_modelo, dispositivo, taxa_amostragem,
  idioma, tts_voz).
- `io/audio.py`: `listar_dispositivos()`, `dispositivo_entrada_padrao()`/`dispositivo_saida_padrao()`
  (varredura ingênua, usada como fallback/exibição), `dispositivo_padrao_do_sistema()` (consulta o
  default real do PortAudio/PipeWire), `gerar_beep()`, `aparar_silencio()` (VAD por energia RMS,
  substitui webrtcvad/silero-vad — ver DECISOES.md), `capturar()`/`tocar()` (sempre com
  `device=None` por padrão, deixando o PipeWire rotear e fazer resample), `salvar_wav()`/`carregar_wav()`.
- `io/cli.py`: agora com subcomandos via `argparse`; `jarvis voz check` lista mic/saída padrão e
  toca um beep.
- Testado na máquina real: `jarvis voz check` roda sem erro e reporta "beep tocado com sucesso"
  usando o dispositivo `default` (índice 8, roteado por PipeWire). Um bug real foi encontrado e
  corrigido nesta fatia (ver Bugs conhecidos/DECISOES.md).
- 17 testes (auditoria, logs, áudio, CLI) — todos com Fakes/monkeypatch, sem tocar hardware real.

## Bugs conhecidos

- Nenhum bug aberto. Um bug foi encontrado e corrigido nesta sessão: escolher "o primeiro
  dispositivo de saída da lista" levava a um device ALSA cru (`hw:0,7`, HDMI) travado em 44100Hz,
  que rejeitava a taxa de 16000Hz usada por padrão. Corrigido usando o dispositivo `default` do
  PortAudio (que já roteia pelo PipeWire/Pulse e resample automaticamente) — ver DECISOES.md.

## Limitação de verificação conhecida

O agente que construiu esta fatia (eu) não tem como *ouvir* o beep — só pode confirmar que o
comando não lançou exceção e reportou sucesso. Reprodução de áudio audível de fato deve ser
confirmada por um humano ao rodar `jarvis voz check`.

## Dívida técnica

- Nenhum provider de LLM (`ClaudeCliProvider`, `FakeProvider` etc.), nenhum core loop, nenhuma
  ferramenta (`fs.*`, `memory.*`) nem executor de ações — M1/M2/M3 não foram construídos ainda.
  Isso é relevante para o M8: a fatia V3 (conversa por voz ponta-a-ponta) foi projetada para
  depender do "mesmo core loop do chat textual" e de "ferramentas já existentes", que não existem.
  Decisão registrada em DECISOES.md: V3 terá escopo reduzido (voz → LLMProvider direto, sem
  tool-calling) até M1/M2 existirem.
- `config.yaml.example` ainda não é lido por código nenhum (nem a seção `voz` nem o resto);
  carregamento de config chega quando algum módulo precisar dele.
- `jarvis.db` (SQLite) ainda não existe.
- STT (`WhisperSTTProvider`), TTS (`PiperTTSProvider`) e o modo `jarvis voz` (V1-V4) ainda não
  foram implementados — ficam para as próximas sessões deste marco.

## Próximo passo

Continuar o marco M8 pela fatia V1 — STT: `STTProvider`/`WhisperSTTProvider` (faster-whisper,
device CUDA se livre com fallback automático para CPU, download do modelo só na primeira execução
real com aviso no console), `FakeSTTProvider` para os testes, fixtures WAV geradas por script (não
commitar binário). DoD: ditado real aparece correto no terminal.

Depois: V2 (TTS/Piper), V3 (conversa por voz ponta-a-ponta, com o escopo reduzido já registrado em
DECISOES.md), V4 (robustez/métricas). Quando M1/M2 forem retomados como marco corrente, revisitar
V3 para religar o modo voz ao core loop completo com tool-calling.
