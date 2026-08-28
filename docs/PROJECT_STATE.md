# Estado do projeto JARVIS

**Versão:** 1.4.0 (M0-M10 concluídos — roadmap completo; +indicador de carregamento, +provider
openai_compat, +jail de leitura ampliada, +integração GDAP, +busca web com Second Brain como
fonte principal, +robustez openai_compat max_tokens/retry/sem tool calling, +modo 100% local
com Ollama e web amigável offline, +autoconhecimento e automanutenção (auto.*), +detalhe da
configuração ativa no auto.info e provider padrão alternável, todos pós-1.0)
**Última atualização:** 2026-08-28

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

### M8/V1-V4 — STT, TTS, conversa por voz com ferramentas, robustez (retomado e concluído)
- `providers/base.py`: protocolos `STTProvider`/`TTSProvider` (numpy só sob `TYPE_CHECKING`,
  `from __future__ import annotations` evita import obrigatório em runtime).
- `providers/stt.py`: `WhisperSTTProvider` real (faster-whisper, CPU/int8 por padrão — ver
  DECISOES.md sobre não usar CUDA ainda). `transcrever(sinal, taxa)` valida 16000Hz, erro
  amigável para áudio vazio/sem fala detectada/falha do modelo.
- `providers/tts.py`: `PiperTTSProvider` real (pacote `piper-tts`), baixa o modelo da voz
  automaticamente em `caminhos.modelos_voz` no primeiro uso. `sintetizar(texto) ->
  (sinal, taxa)`.
- `providers/fake.py`: `FakeSTTProvider`/`FakeTTSProvider` roteirizados, mesmo padrão do
  `FakeProvider` já existente.
- `core/configuracao.py`: `ConfiguracaoVoz` (habilitada, stt_modelo, dispositivo,
  taxa_amostragem, idioma, tts_voz, duracao_captura_segundos) e `caminhos.modelos_voz` —
  fecha a dívida técnica "`io/audio.py` não consulta config" (agora `io/cli.py` consulta via
  `criar_provider_stt`/`criar_provider_tts`/`_comando_voz_falar`).
- `io/cli.py`: `jarvis voz falar` — conversa por voz push-to-talk (ENTER grava, `aparar_silencio`
  apara as pontas, STT transcreve, **`processar_turno` roda com ferramentas de verdade** — não
  mais o "LLM direto sem tools" cogitado antes de M1/M2 existirem —, resposta impressa em texto e
  falada via TTS). Atrás do gate `voz.habilitada` (antes só documentado, agora checado de
  verdade).
- Robustez (V4): erro de microfone/transcrição/reprodução em um turno não trava o loop — o
  próximo turno continua normalmente; teste E2E prova uma ferramenta real (`fs.list`) executada e
  citada na resposta falada, não só texto solto.
- 24 testes novos (STT, TTS, config de voz, CLI de voz) — todos com Fakes/monkeypatch.
- **Validado na máquina real, além dos testes com fakes**: `scripts/validar_voz_real.py` faz um
  round-trip TTS→STT de verdade (Piper sintetiza "o rato roeu a roupa do rei de roma", Whisper
  transcreve reconhecendo a frase) — e reprodução real via `tocar()` a 22050Hz (taxa nativa do
  Piper) funciona sem ajuste, confirmando que o design "device=None" do V0 já cobre taxas
  distintas. Script não faz parte da suíte de testes (baixa modelos reais / usa rede na primeira
  vez) — é validação manual, mesmo espírito do "não dá pra ouvir o beep" do V0, só que aqui dá
  pra checar objetivamente o texto transcrito em vez de precisar de um humano ouvindo.

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

### Pós-1.0 — limites do config.yaml lidos de verdade
- `limites` agora tem `max_iteracoes_por_turno` (12), `max_reparos_por_turno` (2) e
  `max_replanejamentos` (3) além do `timeout_por_passo_segundos` já existente — todos lidos de
  `config.yaml` e aplicados de fato: `processar_turno` (conversa texto e voz) e `executar_objetivo`
  (`jarvis run`) recebem esses valores em vez de defaults fixos. `config.yaml.example` sincronizado
  (removidos campos de plano nunca implementados: `max_iteracoes_por_objetivo`,
  `teto_tokens_por_objetivo`, `teto_custo_usd_por_objetivo`).

### Pós-1.0 — compressão de histórico (openai_compat)
- `historico_teto_tokens` (padrão 3000, `0` = desliga): quando a conversa em memória do
  `OpenAICompatProvider` estoura o teto aproximado de tokens, as mensagens antigas (restam as 2
  mais recentes) são trocadas por um `system` com resumo gerado pelo próprio modelo (a chamada
  de resumo usa `_solicitar_resumo`, sem recursão no `enviar` e sem tocar em histórico se o
  resumo vier vazio). Validado na máquina com qwen3:4b: histórico comprimido com sucesso.
  `historico_teto_tokens` baixo → compressão frequente, porém resumo granular demais; alto →
  risco de estourar o `num_ctx` do Ollama (4096 numa 4b padrão).

### Pós-1.0 — citação com caminho real (conhecimento.buscar)
- A citação `[arquivo § seção]` deixou de mostrar só o basename: agora mostra o caminho real
  (abreviado como `~/...` quando dentro do home) — o modelo pode ler o trecho citado inteiro com
  `fs.read`, que resolve `~` e valida contra o jail. Caminhos são normalizados com
  `expanduser().resolve()` na ingestão. Validado na máquina: citar `~/second-brain/x.md` e ler o
  arquivo citado via `fs.read` passa no executor.
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

### M4 — Loop autônomo + goals
- `core/objetivos.py`: `RepositorioObjetivos`/`Subtarefa`/`ObjetivoPersistido` — SQLite (tabela
  `objetivos`), checkpoint (`salvar_checkpoint`) a cada subtarefa concluída ou replanejamento,
  `obter_em_andamento()` para retomada pós-crash.
- `core/planejador.py`: `planejar()` (LLM decompõe um objetivo em subtarefas via protocolo JSON
  `{"tipo":"plano",...}`), `executar_objetivo()` — roda cada subtarefa com `processar_turno`,
  decide sucesso/falha pelo prefixo `SUCESSO:`/`FALHA:` da resposta final, replaneja o restante em
  caso de falha (até `max_replanejamentos`, padrão 3), persiste checkpoint a cada progresso.
- `io/cli.py`: `jarvis run "<objetivo>"` — mostra o progresso subtarefa a subtarefa no terminal.
- Testado na máquina real: `jarvis run "salve uma nota... e depois busque por essa nota..."`
  decompôs em 3 subtarefas (store, search, confirmar), executou todas com sucesso; confirmado nos
  três lugares — saída do terminal, checkpoint no SQLite (`objetivos`, estado `concluido`,
  3 subtarefas `concluida`) e a nota realmente gravada em `memorias` (FTS5).
- 15 testes novos, incluindo os dois cenários exigidos pelo DoD, ambos determinísticos com
  `FakeProvider`: **replanning** (subtarefa falha → LLM replaneja → nova subtarefa tenta de outro
  jeito → sucesso) e **retomada pós-crash** (reabre o repositório com uma nova conexão e um
  `FakeProvider` sem histórico algum, e o objetivo continua exatamente na subtarefa onde parou,
  sem replanejar nem re-executar a subtarefa já concluída — confirmado checando que o provider
  novo recebeu só 1 chamada).

### M5 — Conhecimento local (RAG leve)
- `memory/conhecimento.py`: `RepositorioConhecimento` (SQLite FTS5) — ingestão de `.md` (chunking
  por cabeçalho), `.txt` (arquivo inteiro), `.pdf` (por página, via `pypdf`); atualização por
  mtime (arquivo sem mudança não é reindexado); `Trecho.citacao()` → `[arquivo § seção]`.
- `memory/_fts5.py`: `construir_consulta_fts5()` — consulta OR entre termos, usada por
  `armazenamento.py` (M2) e `conhecimento.py` (M5). Ver "bugs conhecidos" abaixo.
- `tools/conhecimento.py`: `conhecimento.buscar` (READ_ONLY), resultado já formatado
  `[arquivo § seção]: texto`.
- `core/configuracao.py`: `conhecimento.diretorios` — lista de diretórios autorizados a indexar
  (vazia por padrão; RAG é opt-in).
- `io/cli.py`: `jarvis indexar <diretorio>` (valida contra `conhecimento.diretorios` com
  `resolver_dentro_do_jail`, reaproveitado do M2); `_seguro()` — escapa conteúdo do
  LLM/ferramentas/auditoria antes de `console.print()` (ver bug abaixo).
- `tests/golden/*.yaml` + `tests/test_golden.py`: primeira implementação real da infraestrutura
  de golden tasks descrita desde o início do projeto (objetivo → roteiro `FakeProvider` → trace de
  ações esperado, comparado por igualdade → trechos exigidos na resposta final). 2 casos:
  `citacao_conhecimento` (RAG com citação) e `resposta_direta_sem_ferramenta` (sem tool-calling).
- Testado na máquina real com um diretório de documentos fictício (`notas_projeto.md` com
  cabeçalhos): `jarvis indexar` seguido de uma pergunta em linguagem natural respondida
  corretamente COM citação `[notas_projeto.md § Como rodar localmente]` renderizada de verdade no
  terminal — dois bugs reais foram encontrados e corrigidos nesse processo (ver Bugs conhecidos).
- 121 testes no total (10 novos: chunking md/txt/pdf — PDF de teste escrito à mão, sem depender de
  lib de geração —, freshness por mtime, ingestão de diretório, 2 golden tasks, regressão do bug
  de escape de markup).

### M6 — Embeddings opcionais (avaliado, NÃO adotado)
- `scripts/benchmark_embeddings.py`: benchmark real FTS5 (produção) vs `fastembed` (ONNX,
  multilingual-MiniLM) sobre um corpus sintético de 7 trechos/7 consultas em português. Resultado:
  FTS5 hit@1 6/7, embeddings 7/7 — ganho real porém marginal, não suficiente para justificar a
  dependência nova num projeto pessoal com corpus tipicamente pequeno. Decisão e números completos
  em DECISOES.md. Nenhuma mudança de código de produção neste marco — `fastembed` não é dependência
  do projeto (`pyproject.toml` inalterado).
- Critério registrado para reavaliar: corpus real crescer o suficiente para o FTS5 errar consultas
  legítimas com frequência, ou o usuário relatar buscas que deveriam ter encontrado algo por
  sinônimo/parafraseamento e não encontraram.

### M7 — Visão
- `io/tela.py`: `capturar_tela()` via `grim` (Wayland/wlroots), binário e timeout configuráveis.
- `providers/base.py`: `VisionProvider` (Protocol: `analisar(caminho_imagem, pergunta) -> str`).
- `providers/claude_cli.py`: `ClaudeCliVisionProvider` — envia a imagem em base64 via
  `--input-format stream-json`/`--output-format stream-json --verbose` (formato de blocos de
  conteúdo da API Messages); `providers/fake.py`: `FakeVisionProvider` para testes.
- `tools/visao.py`: `vision.analyze` (READ_ONLY) — captura a tela, analisa, apaga a captura do
  disco em seguida. NÃO persiste nada na memória automaticamente (ver Bugs conhecidos).
- Testado na máquina real: "o que está na minha tela?" respondido corretamente descrevendo o
  conteúdo real da tela (duas vezes, incluindo depois da correção do `--verbose`).
- 12 testes novos (captura real com `grim` + erros com binário falso/inexistente/lento,
  `ClaudeCliVisionProvider` com um `claude` falso incluindo verificação de que a imagem em
  base64 chega no stdin, ferramenta `vision.analyze` incluindo a regressão de não-persistência).

### M9 — Computer use controlado
- `io/entrada.py`: mouse/teclado via `evdev.UInput` (dispositivo virtual no nível do kernel, não
  `ydotool`/API Lua específica desta build do Hyprland — ver DECISOES.md). `mover_mouse(dx, dy)`,
  `clicar(botao)`, `digitar(texto)` (ASCII simples, sem acentos — limitação real de XKB/evdev,
  documentada), `tecla(combinacao)` (ex.: "ctrl+c", "alt+f4", suporta modificadores + tecla).
- `io/janelas.py`: `listar_janelas()` via `hyprctl clients -j`/`activewindow -j` (JSON, só
  leitura). Foco de janela por seletor NÃO implementado — testado e confirmado não confiável
  nesta build do Hyprland (ver DECISOES.md), registrado como pendência conhecida.
- `tools/computador.py`: `computador.listar_janelas` (READ_ONLY), `computador.mover_mouse`
  (MEDIUM), `computador.clicar`/`computador.digitar`/`computador.tecla` (**CRITICAL — primeiro
  uso real desse nível de risco no projeto**, resolvendo a dívida técnica do M3). Todas atrás de
  `computador.habilitada` (`false` por padrão), além da aprovação interativa obrigatória que
  HIGH/CRITICAL já exigem.
- `core/configuracao.py`: `ConfiguracaoComputador` (só `habilitada` por enquanto).
- 29 testes novos (entrada sintética com UInput falso, listagem de janelas — inclui um teste
  REAL contra o hyprctl de verdade, mesmo espírito do teste real de `grim` do M7 —, ferramentas
  de computador, gate de configuração).
- **Validado na máquina real, com alvo descartável e seguro** (não numa aplicação real do
  usuário): `scripts/validar_computador_real.py` abre um terminal `kitty` novo rodando só
  `cat > arquivo`, confirma que ele realmente ficou em foco, digita texto via evdev, confirma
  movimento real do cursor via `hyprctl cursorpos` antes/depois, e fecha tudo com Enter+Ctrl+D —
  lê o arquivo de volta e confere que o texto batido é exatamente o esperado. Passou de verdade,
  sem sujeira deixada no sistema (arquivo e janela removidos pelo próprio script).

### M10 — Integração 1.0 (fecha o roadmap completo)
- Revisão do projeto como um todo, não uma fatia isolada: `README.md` reescrito (comandos de
  voz/computer use que faltavam, extras de instalação `voz`/`computador`, contagem de testes
  atualizada), `pyproject.toml` na versão `1.0.0`.
- `jarvis --version` (novo): lê a versão via `importlib.metadata`, uma única fonte de verdade
  (`pyproject.toml`), sem duplicar a string em dois lugares.
- **Testes de fumaça reais de ponta a ponta** (além dos testes automatizados por marco):
  - `jarvis --help`/`jarvis voz --help`: todos os subcomandos aparecem corretamente.
  - `jarvis` (conversa real com o `claude` de verdade): "qual é a capital do brasil?" →
    "Brasília." — confirma toda a cadeia (config → provider → executor → loop → CLI) funcionando
    junta, não só em isolamento.
  - `computador.listar_janelas` ativado via config temporária e exercitado através de uma
    conversa real (não só chamado direto em teste unitário): o LLM decidiu sozinho usar a
    ferramenta, o executor rodou (READ_ONLY, sem aprovação necessária), a resposta final citou
    as 3 janelas reais abertas corretamente, incluindo qual estava ativa. Prova que M9 se integra
    de verdade ao loop de conversa do M2, não só que os módulos individuais funcionam sozinhos.
- 187 testes (1 novo: `--version`).
- Roadmap M0-M10 fechado por completo nesta sessão (2026-08-23), a pedido direto do usuário.

### Pós-1.0 — Indicador de carregamento ("pensando...")
- Tarefa avulsa pedida depois do 1.0 (não é um marco novo do roadmap): mostrar um spinner
  enquanto o JARVIS processa uma resposta, já que não há streaming (decisão do M1) — o usuário
  ficava sem feedback nenhum durante chamadas que podem levar vários segundos, inclusive turnos
  com múltiplas ferramentas encadeadas.
- `io/cli.py`: `with console.status("[dim]pensando...[/dim]", spinner="dots"):` envolvendo a
  chamada bloqueante ao provider/loop em `_executar_conversa` (texto) e `_executar_conversa_voz`
  (voz). Usa `Console.status()` do Rich (já dependência do projeto) — zero dependência nova.
- 3 testes novos (mock de `console.status` para confirmar chamada, mensagem e ordem relativa
  abre→fecha→resposta-impressa; `Console.status()` não escreve nada em saída não-terminal, então
  não dá pra verificar isso por `capsys` como outras mensagens).
- **Validado numa sessão real de terminal** via `script -qc ".venv/bin/jarvis" saida.log`
  (pseudo-tty, captura os bytes/escapes ANSI reais): confirma cursor escondido, múltiplos frames
  do spinner "dots" alternando com "pensando...", e limpeza correta (`cursor-up + clear-line`)
  exatamente antes da resposta final aparecer — sem sujeira. Comando completo em DECISOES.md.
- Versão bumped para `1.0.1` (correção/melhoria de UX, não funcionalidade nova de roadmap).
- 190 testes no total.

### Provider `openai_compat` (pós-roadmap, a pedido do usuário)
- Motivação: eliminar o consumo de tokens Claude no uso diário — qualquer servidor com API
  OpenAI-compat passa a servir o loop de ações (Ollama local a custo zero/offline, ou tiers
  grátis tipo Groq/Gemini/OpenRouter via `api_key_env`).
- `core/configuracao.py`: `ConfiguracaoOpenAiCompat` (base_url, modelo, api_key_env,
  timeout_segundos), lida da seção `provedor.openai_compat`.
- `providers/openai_compat.py`: `OpenAICompatProvider` (protocolo `LLMProvider`) — POST em
  `{base_url}/chat/completions` via `urllib` stdlib (zero dependência nova), histórico da
  conversa mantido client-side (APIs OpenAI-compat são stateless; `reiniciar()` limpa a lista),
  mensagem cujo envio falhou sai do histórico pra retry recomeçar limpo. Erros de rede/HTTP/JSON
  viram `ErroProvider` amigável; resposta sem `choices`/sem conteúdo também.
- `providers/__init__.py::criar_provider_llm()`: aceita `llm_padrao: openai_compat`; chave de
  API vem de variável de ambiente (nome configurado em `api_key_env`) — config.yaml nunca guarda
  segredo; variável ausente = `ErroProvider` fail-closed.
- 24 testes novos (`tests/test_providers_openai_compat.py` + seção nova em
  `test_configuracao.py`): transporte falso injetado gravando chamadas (URL, corpo, headers),
  histórico/reinício/system prompt/Authorization, falha sem sujar histórico, payloads maliciosos
  de `_extrair_conteudo`, e a camada de rede real (`_postar_json`) exercitada com urllib
  monkeypatchado (HTTPError/URLError/timeout/não-JSON). Zero rede nos testes.
- Suíte completa: 211 testes verdes (`scripts/check.sh`).

### Base de conhecimento — dois livros indexados (pós-roadmap, uso do M5 existente)
- Não é código novo: o usuário colocou dois PDFs em `~/second-brain/01-knowledge/` (*Código
  Limpo*, Robert C. Martin, PT-BR, 398 páginas; *Fundamentos Matemáticos para a Ciência da
  Computação*, Judith Gersting, PT-BR, 749 páginas) e pediu para o conteúdo virar conhecimento
  usável tanto no second brain quanto pelo JARVIS.
- `config.yaml` (não versionado) já tinha `conhecimento.diretorios: [~/second-brain]` — nenhuma
  mudança de configuração foi necessária, só rodar `jarvis indexar ~/second-brain` de novo para
  o M5 (ver seção M5 acima) reindexar os dois PDFs recém-colocados junto com o resto da base.
- Resultado real: 866 trechos indexados no total. Validado na máquina real com
  `RepositorioConhecimento.buscar()` direto: consultas em português retornam tanto as 16 notas
  sintetizadas novas em `second-brain/01-knowledge/{engenharia-software,matematica-discreta}/`
  quanto trechos crus dos próprios PDFs por número de página real (ex.: consulta por "Teorema de
  Bayes" retorna a página 239 do PDF do Gersting), confirmando que o pipeline `.pdf` por página
  do M5 processou os dois livros de ponta a ponta, não só os `.md`.
- Sem mudança de versão — é dado novo na base de conhecimento indexada pelo M5, não uma
  funcionalidade nova do agente.

### Jail de leitura ampliada (pós-roadmap, a pedido do usuário)
- Pedido: jarvis devia poder ler qualquer arquivo em `/home/igor`, não só
  `~/jarvis/workspace`/`~/second-brain`, sem ampliar o que ele pode escrever.
- `security/executor.py::Executor` ganha `jail_paths_leitura: tuple[Path, ...] = ()`
  (compatível com chamadas antigas). Em `_executar_validado`, a validação de
  `campos_caminho` usa `jail_paths + jail_paths_leitura` só quando
  `ferramenta.risco == NivelRisco.READ_ONLY` — ou seja, só `fs.read`/`fs.list`
  (as únicas ferramentas READ_ONLY com `campos_caminho` no projeto hoje).
  `fs.write` (LOW) nunca vê a raiz extra, continua confinado a `jail_paths`.
- `core/configuracao.py`: nova `ConfiguracaoSeguranca.jail_paths_leitura`,
  lida de `seguranca.jail_paths_leitura` no `config.yaml` (lista de
  caminhos, vazia por padrão — comportamento antigo preservado até
  configurar). `config.yaml.example` documentado; `config.yaml` real
  (não versionado) do usuário configurado com `jail_paths_leitura: [/home/igor]`.
- 5 testes novos (3 em `test_executor.py` provando leitura permitida e
  escrita recusada na raiz extra — o teste "malicioso" da convenção do
  projeto; 2 em `test_configuracao.py` provando o parsing do YAML).
- Validado na máquina real contra o `config.yaml` de produção (não só
  fakes): `fs.read` em `/home/igor/.bashrc` teve sucesso; `fs.write` em
  `/home/igor/arquivo-novo.txt` foi recusado com "fora dos diretórios
  autorizados", sem criar o arquivo.
- Versão `1.1.1` (capacidade nova, mudança pequena e compatível).
- 217 testes no total, todos verdes (`scripts/check.sh`).

### Integração com GDAP (pós-roadmap, a pedido do usuário)
- Motivação: usuário pediu para integrar o JARVIS com o GDAP (projeto irmão em `~/gdap`, uma
  plataforma de automação/análise de dados construída separadamente), de forma que o JARVIS
  pudesse USAR o GDAP através das ferramentas.
- `core/configuracao.py`: `ConfiguracaoGdap` (habilitada, base_url, api_key_env,
  timeout_segundos, pipelines_permitidos), lida da seção `gdap`.
- `io/gdap.py`: `ClienteGdap` — transporte HTTP via `urllib` stdlib (zero dependência nova,
  mesmo estilo de `providers/openai_compat.py`), erros de rede/HTTP/JSON convertidos em
  `ErroGdap` amigável, extraindo a mensagem do envelope de erro uniforme do GDAP
  (`{"error": {"code","message",...}}`) quando disponível.
- `tools/gdap.py`: 5 ferramentas — `gdap.status`/`listar_datasets`/`consultar`/`perguntar`
  (READ_ONLY: o GDAP já bloqueia escrita/DDL no próprio guard de SQL, então uma consulta
  arbitrária daqui não altera dado nenhum) e `gdap.executar_pipeline` (MEDIUM, só nomes na
  allowlist `gdap.pipelines_permitidos` — mesma filosofia de `terminal.exec`/
  `allowlist_binarios`, verificada dentro da própria ferramenta pois o Executor não tem
  allowlist genérica além de binário de terminal).
- `tools/__init__.py`: gate `gdap.habilitada: false` por padrão (mesmo padrão de
  `computador.habilitada`); variável de ambiente ausente = `ErroProvider` fail-closed, igual ao
  `openai_compat`.
- **Bug real encontrado no GDAP** validando isto na máquina (não nos testes com fakes):
  `gdap system key create <nome> --role X` reusava um usuário existente pelo e-mail sem
  sincronizar o papel armazenado — reemitir uma chave com papel maior para o mesmo nome era um
  no-op silencioso (a chave "dizia" ter o papel novo, mas o principal ficava preso ao antigo).
  `gdap.executar_pipeline` falhava com "missing permission(s): dataset:write" mesmo com
  `--role engineer`. Corrigido no próprio GDAP (`cli/main.py::key_create` e
  `api/routers/system.py::create_api_key`), com teste de regressão provando os dois lados
  (sanity-check manual: removendo a correção, o teste volta a falhar com o erro real).
- 30 testes novos (`tests/test_io_gdap.py`, `tests/test_tools_gdap.py`): transporte falso
  injetado (mesmo espírito de `test_providers_openai_compat.py`), rede real exercitada com
  `urllib` monkeypatchado, e o teste "malicioso" da convenção do projeto (pipeline fora da
  allowlist recusado sem sequer chamar o GDAP).
- **Validado na máquina real, ponta a ponta**: GDAP rodando como serviço systemd `--user`
  (`~/.config/systemd/user/gdap.service`, porta 8811 — a 8000 padrão já estava ocupada por outro
  processo nesta máquina), chave real emitida com papel `engineer`, guardada em `GDAP_API_KEY`
  (variável universal do fish, mesmo padrão de `GROQ_API_KEY`). Duas conversas reais via
  `processar_turno` com o provider Groq configurado do usuário: uma decidiu sozinha chamar
  `gdap.status` + `gdap.listar_datasets` para "verifique se o GDAP está no ar e liste os
  datasets"; outra chamou `gdap.perguntar` para "por que a receita caiu?", repassando a resposta
  do analista de IA do GDAP (com evidência e confiança) na resposta do JARVIS.
  `gdap.executar_pipeline` também validado publicando uma nova versão de dataset e gerando
  relatórios reais.
- Versão `1.2.0` (capacidade nova — integração com um sistema externo inteiro).
- 247 testes no total, todos verdes (`scripts/check.sh`).

## Bugs conhecidos

- Nenhum bug aberto. No M7: faltava a flag `--verbose` (exigida pela CLI junto com
  `--output-format=stream-json` em modo `-p`) no `ClaudeCliVisionProvider` — corrigido; e a
  primeira versão de `vision.analyze` persistia automaticamente um resumo de cada captura de tela
  na memória sem pedido do usuário (chegou a gravar dados pessoais reais numa execução manual,
  removidos manualmente) — corrigido removendo a persistência automática por completo (ver
  DECISOES.md, é uma correção de privacidade, não só um bug técnico).
- No M5: três bugs reais foram encontrados e corrigidos validando o M5 na máquina
  real (nenhum apareceu nos testes automatizados até então — ver DECISOES.md para os três):
  (1) coluna `secao` do FTS5 estava `UNINDEXED`, então palavras que só apareciam no título de uma
  seção markdown eram invisíveis à busca; (2) consultas FTS5 usavam AND implícito entre termos,
  então perguntas naturais de 4+ palavras raramente batiam num único trecho pequeno — trocado
  para OR (aplicado também retroativamente a `memory.search`, mesmo defeito desde o M2); (3) o
  resultado de ferramentas virava `repr()` de lista Python na mensagem pro LLM, e o terminal
  (Rich) engolia citações `[arquivo § seção]` por interpretá-las como marcação de estilo — ambos
  corrigidos (`core/loop.py::_formatar_valor_para_llm`, `io/cli.py::_seguro`).
- Um bug foi encontrado e corrigido no M8/V0: escolher "o primeiro dispositivo
  de saída da lista" levava a um device ALSA cru (`hw:0,7`, HDMI) travado em 44100Hz, que rejeitava
  a taxa de 16000Hz usada por padrão. Corrigido usando o dispositivo `default` do PortAudio (que já
  roteia pelo PipeWire/Pulse e resample automaticamente) — ver DECISOES.md.

## Limitação de verificação conhecida

O agente que construiu esta fatia (eu) não tem como *ouvir* o beep — só pode confirmar que o
comando não lançou exceção e reportou sucesso. Reprodução de áudio audível de fato deve ser
confirmada por um humano ao rodar `jarvis voz check`.

## Dívida técnica

- CRITICAL agora TEM ferramentas reais (M9: `computador.clicar`/`digitar`/`tecla`) e exercício
  real via `scripts/validar_computador_real.py` — dívida resolvida.
- Foco de janela por seletor (classe/endereço/título) não é suportado — só listagem. A API Lua
  desta build do Hyprland não respondeu de forma confiável para isso (ver DECISOES.md, M9). Não
  bloqueante: o agente pode listar e agir fisicamente sem trocar foco automaticamente.
- `digitar()` só suporta ASCII simples, sem acentos — limitação real de evdev/XKB (ver
  DECISOES.md, M9), não uma omissão descuidada.
- `jarvis why` identifica o registro pelo índice de exibição (1 = mais recente), não por um ID
  estável — se novas ações forem registradas entre um `jarvis audit` e um `jarvis why N`, o índice
  pode já apontar para outro registro. Aceitável para uso interativo (index visto na hora), mas
  não é uma referência estável entre sessões.
- `config.yaml.example`: `autonomia` e `limites` ainda não têm código que os leia. `voz` agora É
  lido de verdade (resolvido no M8/V1-V4). `provedor.*`, `seguranca.jail_paths`, `caminhos.*` e
  `voz.*` já são lidos.
- `AnthropicProvider` não implementado; `criar_provider_llm()` aceita `claude_cli` e
  `openai_compat` (qualquer outro valor levanta `ErroProvider`).
- Streaming (`stream-json`) não implementado — `ClaudeCliProvider` usa `--output-format json`
  síncrono (decisão registrada, não é dívida bloqueante, só uma melhoria futura possível).
- `voz.dispositivo` só suporta `"auto"` de verdade — mapear um valor específico para um índice de
  dispositivo exigiria correspondência difusa de nome, não implementada (M8/V4, não bloqueante).
- STT usa CPU (não GPU) por padrão mesmo com RTX 2060 disponível — decisão deliberada (ver
  DECISOES.md), não dívida involuntária; reavaliar só se latência real exigir.

## Dívida técnica (M4)

- Um único objetivo "em_andamento" por vez é suportado (ver decisão em DECISOES.md) — não há fila
  de objetivos concorrentes nem comparação de descrição ao retomar.
- Subtarefas não têm dependências explícitas entre si (a decomposição do LLM já as ordena
  sequencialmente, mas não há um grafo de dependências declarado nem paralelismo).
- `jarvis run` não tem um jeito de listar/cancelar um objetivo em andamento (só continua ou
  esgota `max_replanejamentos`).

## Pós-1.0 — Busca web (Second Brain como fonte principal)

`io/web.py` (transporte `urllib` stdlib + `html.parser`, zero dependência nova) consulta o
DuckDuckGo HTML sem chave de API e devolve títulos/URLs/trechos orgânicos (propagandas —
alvos `duckduckgo.com/y.js` ou links sem `uddg` — descartadas). `tools/web.py` expõe duas
ferramentas READ_ONLY atrás do gate `web.habilitada` (`true` por padrão): `web.buscar` (web
explícita) e `pesquisar` — a ferramenta principal de conhecimento, que consulta PRIMEIRO o
Second Brain local (FTS5) e só cai na web quando não há resultado local, enforçado em código
(não em prompt). O prompt do sistema ganhou a regra explícita de preferir o conhecimento local
antes da web. `config.yaml`/`config.yaml.example` ganharam `web.timeout_segundos`/
`web.limite_padrao`.

Validado na máquina real ponta a ponta: conversa real com o provider Groq configurado do usuário
rogou `pesquisar` sozinho para responder "o que o meu Second Brain sabe sobre código limpo?" e
recebeu trechos citados `[arquivo § seção]` do índice real; numa segunda conversa a mesma
ferramenta fez o fallback para a web (resultado orgânico de batente) — o passo seguinte foi
barrado só pelo rate limit do provedor (HTTP 429), não por bug. 15 testes novos
(`tests/test_io_web.py`, `tests/test_tools_web.py`), incl. o "malicioso" de recusa de schema e
a prova de que `pesquisar` NÃO toca a rede quando o Second Brain responde. Versão `1.3.0`.

Um comportamento observado no E2E (não é bug do web, é limitação pré-existente do M5): a citação
`[arquivo § seção]` mostra só o nome do arquivo, então o modelo tentou abrir um caminho
relativo errado com `fs.read`. Se reconstruir o caminho completo do arquivo citado for
necessário, é mudança no formato da citação do `RepositorioConhecimento` — registrar como
melhoria futura, não dívida desta fatia.

## Pós-1.0 — Robustez openai_compat (bug-1.3.1 e 1.3.2)

Bug 1.3.1 reportado pelo usuário: pergunta simples na conversa → `erro: resposta chegou sem
conteúdo textual`. Causa raiz: o provider não enviava `max_tokens`; o default do Groq (baixo)
em modelos reasoning (`openai/gpt-oss-120b` emite um campo `reasoning`) estourava o teto às
vezes e `content` voltava `null` (HTTP 200 sem conteúdo). Correção: `max_tokens` configurável
(`provedor.openai_compat.max_tokens`, default 8192, `0` desliga) + retry automático de 2
 tentativas para resposta sem conteúdo + erro final com dica sobre `max_tokens`. Bug latente
 corrigido de quebra: falha de extração de conteúdo passou a remover a mensagem do usuário do
 histórico (antes só falhas HTTP faziam isso). Validado na máquina real: conversa real respondeu
 com conteúdo e o modelo "se autocorrigiu" após uma ferramenta ser bloqueada pelo jail.

 Complemento: `piso_max_tokens_raciocinio` (padrão 16384, `0` = sem piso) aplica um teto mínimo
 efetivo em famílias que emitem `reasoning` antes do `content` (qwen3, gpt-oss, deepseek-r1...),
 de modo que um `max_tokens` baixo não corte a resposta no meio de uma ação (`content` segue
 sendo o valor maior entre os dois). O piso não impede `max_tokens` explícito maior.

Bug 1.3.2 (sequência, mesma noite): a conversa real passou a responder HTTP 400 `tool_use_failed`
("Tool choice is none, but model called a tool") — o `gpt-oss-120b` do Groq emite tool calling
nativa não-determinística mesmo sem `tools` declarado na API. Correção: o provider envia
`tools: []` + `tool_choice: "none"` por padrão (flag `desabilitar_ferramentas_nativas`, `false`
restaura o comportamento antigo), forçando o protocolo de ações em texto puro. Validado na
máquina: conversa real respondeu com resumo real do Second Brain (`pesquisar` chamado sozinho).

4 + 2 testes novos; suíte 268 passed. Versões `1.3.1` e `1.3.2`.

## Pós-1.0 — Modo 100% local (Ollama/qwen3) + web amigável offline (a pedido do usuário)

Decisão do usuário: JARVIS NÃO deve consumir a assinatura Claude Pro (o `claude_cli` via
`claude -p` gastava a cota OAuth da conta dele a cada turno) nem APIs externas com limitador.
Provider ativo trocado no `config.yaml` (não versionado) de `claude_cli` →
`openai_compat` apontando para um **Ollama local** (`http://localhost:11434/v1`, modelo
`qwen3:4b`) — instalação: `sudo pacman -S ollama-cuda` (repo cachyos-extra, ~988MB), o usuário
`ollama` do systemd-sysusers não era criado automaticamente (gerado com
`sudo systemd-sysusers /usr/lib/sysusers.d/ollama.conf` + `chown ollama:ollama /var/lib/ollama`),
serviço `systemctl enable --now ollama`, modelo `ollama pull qwen3:4b` (~2,5GB, GPU RTX 2060).

O reasoning agora roda **na máquina, sem internet fixa**: o Second Brain (FTS5) é indexação
local e o LLM local decide e responde offline. `tools/web.py` ganhou tratamento amigável de
`ErroBuscaWeb`: sem conexão (ou DuckDuckGo inacessível), `pesquisar` e `web.buscar` devolvem a
mensagem "web indisponível (\<motivo>) — sem conexão não há busca web; use apenas o conhecimento
local (Second Brain)" em vez de falharem — o agente segue respondendo com o que o conhecimento
local tiver. `config.yaml.example` ainda tem `llm_padrao: claude_cli` como padrão embutido do
código (preservado); quem não tiver `config.yaml` continua caindo no Pro até configurar.

Validado na máquina, ponta a ponta: conversa real pergunta "o que o meu Second Brain sabe sobre
código limpo?" → `qwen3:4b` local chamou `conhecimento.buscar` sozinho e respondeu com os 17
capítulos do Clean Code indexados — zero uso de rede/Pro no raciocínio. Suíte 270 passed
(+2 testes: rede fora vira resultado amigável, sem falhar). Versão `1.3.3`.

**Atentar**: o processo `jarvis` aberto antes da troca de config continua usando o provider
antigo até ser reiniciado (só o config.yaml é lido na inicialização). Visão (M7) depende do
`ClaudeCliVisionProvider` — não é coberta pelo Ollama local (qwen3:4b é só texto); `vision.analyze`
fica indisponível com `llm_padrao: openai_compat` (provê compatível exigiria um modelo VL).

## Pós-1.0 — Autoconhecimento e automanutenção (auto.*, a pedido do usuário)

O usuário pediu que o JARVIS soubesse identificar as últimas mudanças do próprio software, dissesse
com qual provider está rodando (claude_cli vs Ollama) e conseguisse se atualizar / se modificar.
Novo módulo `tools/autor.py` com 5 ferramentas (registradas sempre, sem gate de config):

- `auto.info` (READ_ONLY) — versão do pacote (`importlib.metadata`), provider ativo com detalhe
  (`claude_cli` → binário; `openai_compat` → base_url/modelo/api_key_env/api_key_definida), endereço
  do config.yaml e estado do git (branch, head, data/mensagem do último commit, arquivos não
  commitados).
- `auto.mudancas` (READ_ONLY) — `git log` (hash/data/mensagem), com `limite` 1–50.
- `auto.atualizar` (HIGH) — sequência fixa: trava se houver alterações não commitadas →
  `git fetch origin` (sem internet → resposta amigável) → `git rev-list HEAD..origin/<branch>` →
  `git pull --ff-only` quando atrasado → `pip install --no-build-isolation -e .` →
  `scripts/check.sh`. Nunca usa `shell=True`; ambiente minimizado (PATH/HOME/LANG +
  SSH_AUTH_SOCK quando existir).
- `auto.editar` (HIGH) — grava/sobrescreve arquivo DENTRO de `~/jarvis` com rollback
  (`capturar_estado`/`reverter`, mesmos do fs.write). Caminhos relativos resolvem a partir da raiz
  do repositório; recusa qualquer coisa fora dela e qualquer coisa dentro de `.git` (confinamento
  próprio — `~/jarvis` NÃO entrou no `jail_paths` do config para não liberar `fs.write` LOW em
  autonomia 2; ver DECISOES).
- `auto.commit` (HIGH) — `git add -A` + `git commit -m <mensagem>` (msg vazia recusada).

Motivação de segurança: toda mutação é HIGH → aprovação humana interativa SEMPRE (fail-closed sem
callback); READ_ONLY livres. Não há push automático (usuario decide quando publicar no GitHub).

Validado com 19 testes novos (`tests/test_tools_autor.py`): parsing de git log, limite, confinamento
de caminho (fora do repo e dentro de `.git` recusados), rollback de edição (restaura e remove),
bloqueio com mudanças locais, fetch sem internet, pull quando atrasado, commit, e o Executor
recusando HIGH sem aprovação / rodando com aprovação / recusando schema inválido. Suíte 289 passed
(ruff + mypy --strict + pytest). Versão `1.4.0`.

Correção no mesmo dia: o qwen3:4b driftou para o formato nativo de tool-call
(`{"tool": ..., "args": ...}`) numa conversa real, e o `_extrair_acao` (que só aceitava
`{"tipo":"acao",...}`) tratou o JSON como resposta final sem executar nada. `_extrair_acao` agora
normaliza os formatos comuns (`tool`/`args`, `tool`/`arguments`, `{type:function,function:{...}}`,
`function_call`) além do canônico, e o prompt do sistema ganhou reforço das chaves exatas. Além
disso, `processar_turno` ganhou **retry de formato** (`max_reparos`, padrão 2): resposta que parece
chamada de ferramenta malformada (JSON truncado, chaves erradas) recebe uma mensagem corretiva e o
turno continua em vez de virar resposta final. Suíte 297 passed.

**Benchmark de aderência** (`scripts/benchmark_aderencia.py`): roda conversas reais contra o
provider ativo (Ollama local) para 6 perguntas golden e mede quantas vezes o modelo seguiu o
protocolo (formato da 1ª resposta e se executou a ferramenta esperada automaticamente). Resultado
na máquina com qwen3:4b: **12/12 (100%) canônico** — reforço de prompt + parse tolerante
eliminaram o drift observado antes; o script vira teste de regressão manual p/ futuras trocas de
modelo (substituição por `qwen3:8b`/`llama3.1:8b` deve começar rodando o benchmark). Suíte 297
passed.

**Atentar**: quem rodar `auto.atualizar` deve reiniciar a sessão do `jarvis` depois (o provider e o
pacote novos só são lidos/carregados na inicialização). Visão (M7) segue dependente do
`ClaudeCliVisionProvider` — não coberta pelo Ollama local.

## Pós-1.0 — Agendador (systemd user timers, a pedido do usuário)

`io/agendador.py` + subcomando `jarvis agendar` (add|listar|remover|testar). Cada tarefa vira um
par `.service`+`.timer` em `~/.config/systemd/user/` sob o prefixo `jarvis_tarefa_<slug>`, ativado
com `systemctl --user enable --now`; o `.service` é `Type=oneshot` e roda `jarvis run "<objetivo>"`
(ExecStart que se resolve sozinho para o binário `jarvis` ou `sys.executable -m jarvis.io.cli`),
reusando o loop do M4 (plano/subtarefas/auto-resume) com retomada pós-crash. Agenda por
`--diarias HH:MM`, `--a-cada N` (minutos) ou `--quando <OnCalendar>`; `--sobrescrever` substitui
o mesmo nome; `testar` dispara na hora (`systemctl --user start`). Sem gate de config — a
expressão de tempo vai direto para o OnCalendar da unit. `systemctl` é injetável
(`SistemaSystemctl: Callable[[list[str]], str]`) para os testes rodarem sem tocar o da máquina.

Regra de segurança herdada: o timer executa em ambiente sem TTY (entrada é `/dev/null`), então
aprovações HIGH/CRITICAL nunca são possíveis — fail-closed por natureza; só objetivos READ_ONLY
têm garantia de conclusão automática. Validado de ponta a ponta na máquina: `agendar add` criou
as units + timer ativo, `listar` mostrou, `testar` subiu o serviço e o objetivo (qwen3:4b local)
concluiu em ~33s, `remover` desativou e apagou tudo (`systemctl --user list-timers` limpo).

Ajuste encontrado na validação: timers rodam fora do ambiente do fish, então a variável universal
`GDAP_API_KEY` não chega ao processo. O registro das ferramentas (`tools/__init__.py`) agora
degrada em vez de quebrar o startup: processo sem TTY + env faltando → imprime aviso no stderr e
omite as ferramentas `gdap.*`; interativamente o erro explícito continua (feedback imediato).
Testes: 12 novos em `tests/test_agendar.py` (units, OnCalendar, slug, sobrescrever, listar,
remover, disparar, diárias/intervalos inválidos) + 1 em `tests/test_io_gdap.py` (degradação sem
TTY). Suíte 318 passed.

## Próximo passo

**Roadmap M0-M10 completo.** Todos os marcos concluídos em 2026-08-23, na mesma sessão, a pedido
direto do usuário ("vamos terminar o Jarvis"). Não há próxima fatia planejada — o projeto está
em modo de manutenção/uso a partir daqui.

Não-objetivos que agora podem ser reavaliados (eram "até depois do M10", que já passou, mas
NENHUM foi iniciado nesta sessão — decidir usar qualquer um deles é escolha do usuário, não
decisão unilateral desta sessão): multi-agent/supervisor, robótica, IoT/edge, computação
quântica, mobile, UI web pesada, fine-tuning.

Dívida técnica conhecida que sobrevive ao 1.0 (nenhuma bloqueante, todas registradas com motivo
acima e em DECISOES.md): `jarvis why` usa índice não-estável entre sessões; `AnthropicProvider`
não existe (`claude_cli` e `openai_compat` cobertos); streaming não implementado; foco de janela
por seletor não suportado; `digitar()` só ASCII sem acentos; STT roda em CPU por escolha
deliberada, não limitação.

Se uma sessão futura for retomar o projeto: ler este arquivo inteiro primeiro (fonte da verdade,
não a memória de conversas passadas), rodar `scripts/check.sh` pra confirmar que ainda está
verde, e só então decidir o que fazer — não há um "próximo passo" pré-definido esperando.
