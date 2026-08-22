# Estado do projeto JARVIS

**Versão:** 0.1.0 (M0 concluído; M1 concluído fora de ordem; M8/V0 — Fundação de áudio)
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

### M1 — Core conversacional (fora de ordem, a pedido do usuário)
- `core/configuracao.py`: `carregar_configuracao()` lê `~/jarvis/config.yaml` (opcional) com
  padrões embutidos; hoje só entende `provedor.llm_padrao` e `provedor.claude_cli.*`.
- `providers/base.py`: `LLMProvider` (Protocol: `enviar(mensagem) -> str`, `reiniciar()`) e
  `ErroProvider`.
- `providers/claude_cli.py`: `ClaudeCliProvider` real — chama `claude -p --output-format json
  --tools= --system-prompt "<persona jarvis>"`, usando `--session-id` na primeira mensagem e
  `--resume` nas seguintes (histórico fica do lado da CLI do claude, barato via cache). Erros
  amigáveis para binário ausente, timeout, exit code != 0, saída não-JSON e `is_error`.
- `providers/fake.py`: `FakeProvider` roteirizado, só para testes.
- `io/cli.py`: `jarvis` (sem subcomando) agora inicia um loop de conversa real no terminal
  (`você>` / `jarvis>`), com `sair`/`exit`/`quit` para encerrar e `reiniciar` para zerar a sessão.
- Testado na máquina real com a CLI `claude` de verdade: pergunta "qual é a capital do brasil?"
  respondida corretamente ("Brasília."), `reiniciar` confirmado. Custo por chamada caiu de
  ~US$0,035-0,05 (sem restringir nada) para ~US$0,012 na primeira mensagem e ~US$0,001 nas
  seguintes da mesma sessão (`--system-prompt` enxuto + `--resume`) — ver DECISOES.md.
- 38 testes no total (21 novos: configuração, `FakeProvider`, `ClaudeCliProvider` com um binário
  `claude` falso gerado nos testes, loop de conversa do CLI) — nenhum toca rede, CLI real ou custa
  dinheiro.

## Bugs conhecidos

- Nenhum bug aberto. Um bug foi encontrado e corrigido no M8/V0: escolher "o primeiro dispositivo
  de saída da lista" levava a um device ALSA cru (`hw:0,7`, HDMI) travado em 44100Hz, que rejeitava
  a taxa de 16000Hz usada por padrão. Corrigido usando o dispositivo `default` do PortAudio (que já
  roteia pelo PipeWire/Pulse e resample automaticamente) — ver DECISOES.md.

## Limitação de verificação conhecida

O agente que construiu esta fatia (eu) não tem como *ouvir* o beep — só pode confirmar que o
comando não lançou exceção e reportou sucesso. Reprodução de áudio audível de fato deve ser
confirmada por um humano ao rodar `jarvis voz check`.

## Dívida técnica

- Ainda não existe core loop de agente (percepção→plano→ação→observação, M4), nem ferramentas
  (`fs.*`, `memory.*`) nem executor de ações (M2/M3) — a conversa do M1 é só ida-e-volta de texto
  com o LLM, sem tool-calling. Isso é relevante para o M8: a fatia V3 (conversa por voz
  ponta-a-ponta) foi projetada para depender do "mesmo core loop do chat textual" e de "ferramentas
  já existentes"; agora existe uma conversa textual real para religar, mas ainda sem ferramentas —
  decisão em DECISOES.md permanece: V3 usa `LLMProvider` direto, sem tool-calling, até M2 existir.
- `config.yaml.example` só é lido parcialmente: `provedor.llm_padrao`/`provedor.claude_cli.*` já
  são usados por `carregar_configuracao()`; `autonomia`, `limites`, `seguranca`, `caminhos` e `voz`
  ainda não têm código que os leia.
- `jarvis.db` (SQLite) ainda não existe.
- `AnthropicProvider`/`OpenAICompatProvider` não implementados; `criar_provider_llm()` só aceita
  `llm_padrao: claude_cli` por enquanto (qualquer outro valor levanta `ErroProvider`).
- Streaming (`stream-json`) não implementado — `ClaudeCliProvider` usa `--output-format json`
  síncrono (decisão registrada, não é dívida bloqueante, só uma melhoria futura possível).
- STT (`WhisperSTTProvider`), TTS (`PiperTTSProvider`) e o modo `jarvis voz` (M8/V1-V4) ainda não
  foram implementados.

## Próximo passo

A definir com o usuário: retomar M8 pela fatia V1 (STT/faster-whisper) como planejado antes da
pausa para M1, ou seguir para M2 (tool calling) agora que a conversa real está funcionando e faz
mais sentido religar ferramentas a ela. Nenhuma decisão tomada ainda — esperar sinal do usuário na
próxima sessão em vez de escolher sozinho, já que as duas direções têm o mesmo peso no roadmap
original e a escolha é mais sobre prioridade de produto do que sobre arquitetura.
