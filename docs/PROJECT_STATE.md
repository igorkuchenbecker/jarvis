# Estado do projeto JARVIS

**Versão:** 0.1.0 (M0, M1, M2, M3 concluídos; M8/V0 — Fundação de áudio)
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

### M2 — Tool calling
- `security/schema.py`: `validar_schema()` — validador mínimo próprio (object/properties/
  required/additionalProperties + tipos básicos), não a lib `jsonschema` (ver DECISOES.md).
- `security/jail.py`: `resolver_dentro_do_jail()` — bloqueia travessia (`..`), caminho absoluto
  fora do jail e symlink que escapa do jail, via `Path.resolve()`.
- `security/executor.py`: `Executor`/`Acao`/`ResultadoAcao` — única porta de entrada para rodar
  ferramentas: valida schema, valida jail para os `campos_caminho` da ferramenta, executa, captura
  erros, registra em auditoria (sucesso ou erro), e suporta `reverter()` para ferramentas com
  `capturar_estado`/`reverter` (usado por `fs.write`).
- `tools/base.py`: `Ferramenta`/`NivelRisco` (READ_ONLY<LOW<MEDIUM<HIGH<CRITICAL — só READ_ONLY
  e LOW usados até aqui). `tools/registro.py`: `RegistroFerramentas` (registrar/obter/todas/
  descrever_para_prompt).
- `tools/fs.py`: `fs.read`, `fs.list` (READ_ONLY), `fs.write` (LOW, com rollback real).
- `memory/armazenamento.py`: `RepositorioMemoria` sobre SQLite FTS5 (tabela virtual única
  `memorias`). `tools/memoria.py`: `memory.store` (LOW), `memory.search` (READ_ONLY).
- `tools/__init__.py`: `criar_registro_ferramentas_padrao()` monta o registro com fs+memória.
- `core/loop.py`: `processar_turno()` — laço mínimo de tool-calling (até 12 iterações): o LLM
  responde com JSON `{"tipo":"acao",...}` para agir, ou texto normal para responder; NÃO é o loop
  de goals do M4 (sem decomposição/replanning/checkpoint) — ver DECISOES.md.
- `io/cli.py`: `jarvis` (conversa padrão) agora monta o registro + executor automaticamente e usa
  `processar_turno`; mostra no terminal quais ferramentas rodaram (`→ executou fs.list(...)`).
- `core/configuracao.py`: `Configuracao` ganhou `seguranca.jail_paths` e
  `caminhos.workspace/banco_dados/auditoria_jsonl`, lidos de `config.yaml` quando presente.
- Testado na máquina real com a CLI `claude` de verdade: pedi "liste os arquivos do meu workspace
  e depois salve uma nota na memória dizendo quais arquivos encontrou". O modelo tentou primeiro
  `fs.list(".")` (fora do jail — **recusado pelo executor**), corrigiu sozinho para o caminho
  absoluto, listou `exemplo.txt`, chamou `memory.store` e respondeu corretamente. Confirmado nos
  três lugares: saída do terminal, `~/jarvis/dados/auditoria.jsonl` (mostra a recusa e os dois
  sucessos) e `~/jarvis/dados/jarvis.db` (texto realmente persistido, consultado via `sqlite3`).
- 71 testes no total (33 novos: schema, jail — incluindo travessia e symlink maliciosos —,
  executor — incluindo ferramenta desconhecida, schema inválido, travessia maliciosa, rollback —,
  memória FTS5, registro de ferramentas, `processar_turno`). Nenhum toca rede, CLI real ou custa
  dinheiro.

### M3 — Sistema + segurança plena
- `core/configuracao.py`: `Configuracao` ganhou `autonomia.nivel` e
  `limites.timeout_por_passo_segundos`; `seguranca` ganhou `allowlist_binarios`.
- `security/allowlist.py`: `validar_binario_permitido()` — recusa binário fora da allowlist E
  recusa `sudo`/`su`/`doas`/`pkexec` sempre, mesmo que apareçam na allowlist do config.
- `security/executor.py`: `Executor` ganhou `nivel_autonomia`, `allowlist_binarios` e
  `solicitar_aprovacao` (callback). Teto de risco auto-executado por nível de autonomia
  (`TETO_RISCO_POR_AUTONOMIA`); HIGH/CRITICAL sempre passam pelo callback de aprovação,
  independente do nível — sem callback, recusado por padrão (fail-closed).
- `tools/sistema.py`: `sys.info` (READ_ONLY, stdlib+`/proc`), `proc.list` (READ_ONLY),
  `proc.kill` (HIGH, sinal SIGTERM/SIGKILL/SIGINT), `terminal.exec` (MEDIUM, sem `shell=True`,
  ambiente sanitizado, timeout obrigatório, saída truncada em 4000 caracteres).
- `io/cli.py`: `_solicitar_aprovacao_interativa()` — prompt real no terminal para ações
  HIGH/CRITICAL; novos comandos `jarvis audit [--limite N]` (tabela Rich) e `jarvis why <indice>`
  (detalhe de um registro, 1 = mais recente).
- Testado na máquina real: (1) `jarvis audit`/`jarvis why 3` mostrando o histórico real do M2;
  (2) pedir para rodar `git status` via `terminal.exec` no nível de autonomia padrão (2) foi
  **bloqueado automaticamente** ("nível de autonomia atual (2) não permite ações de risco
  MEDIUM"), e o modelo explicou isso ao usuário; (3) pedir para matar um processo real
  (`sleep 300` de teste) disparou o prompt de aprovação — aprovando com "s" o processo morreu de
  verdade (confirmado com `ps`), negando com "n" o processo continuou vivo (confirmado com `ps`).
- 101 testes no total (30 novos: allowlist, ferramentas de sistema — incluindo matar um processo
  real de teste e truncamento de saída —, gate de autonomia parametrizado em 7 combinações,
  aprovação HIGH nos 3 cenários, `jarvis audit`/`jarvis why`). Nenhum toca rede ou custa dinheiro;
  os testes de `sys.info`/`proc.*`/`terminal.exec` tocam processos/disco reais isolados (mesmo
  padrão já usado para `fs.*` com `tmp_path`).

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

- CRITICAL não tem nenhuma ferramenta ainda (nada no roadmap até aqui precisa desse nível) — o
  caminho de aprovação já cobre CRITICAL igual a HIGH no código, mas está sem exercício real.
- `jarvis why` identifica o registro pelo índice de exibição (1 = mais recente), não por um ID
  estável — se novas ações forem registradas entre um `jarvis audit` e um `jarvis why N`, o índice
  pode já apontar para outro registro. Aceitável para uso interativo (index visto na hora), mas
  não é uma referência estável entre sessões.
- Isso é relevante para o M8: a fatia V3 (conversa por voz ponta-a-ponta) foi projetada para
  depender do "mesmo core loop do chat textual" e de "ferramentas já existentes" — agora ambos
  existem (M1+M2), então V3 pode religar de verdade ao `processar_turno` com ferramentas, não mais
  precisar do escopo reduzido registrado antes em DECISOES.md. Revisitar aquela decisão quando V3
  for retomado.
- `config.yaml.example`: `autonomia`, `limites` e `voz` ainda não têm código que os leia (`voz`
  é lido só pela documentação, o `io/audio.py` do M8 ainda não consulta config). `provedor.*`,
  `seguranca.jail_paths` e `caminhos.*` já são lidos.
- `AnthropicProvider`/`OpenAICompatProvider` não implementados; `criar_provider_llm()` só aceita
  `llm_padrao: claude_cli` por enquanto (qualquer outro valor levanta `ErroProvider`).
- Streaming (`stream-json`) não implementado — `ClaudeCliProvider` usa `--output-format json`
  síncrono (decisão registrada, não é dívida bloqueante, só uma melhoria futura possível).
- STT (`WhisperSTTProvider`), TTS (`PiperTTSProvider`) e o modo `jarvis voz` (M8/V1-V4) ainda não
  foram implementados.

## Próximo passo

Seguir para M4 — Loop autônomo + goals: planner com decomposição em subtarefas (dependências,
critérios de sucesso/falha), replanning, checkpoints em SQLite, retomada pós-crash,
`jarvis run "<objetivo>"`. Isso evolui `core/loop.py::processar_turno` (hoje um laço de uma
ferramenta por vez, sem estado persistido) para algo que sobrevive a um crash do processo e
persegue um objetivo multi-passo declarado, não só responde a uma mensagem por vez.
