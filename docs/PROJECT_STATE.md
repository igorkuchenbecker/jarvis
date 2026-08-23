# Estado do projeto JARVIS

**Versão:** 1.0.1 (M0-M10 concluídos — roadmap completo; +indicador de carregamento pós-1.0)
**Última atualização:** 2026-08-23

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

## Próximo passo

**Roadmap M0-M10 completo.** Todos os marcos concluídos em 2026-08-23, na mesma sessão, a pedido
direto do usuário ("vamos terminar o Jarvis"). Não há próxima fatia planejada — o projeto está
em modo de manutenção/uso a partir daqui.

Não-objetivos que agora podem ser reavaliados (eram "até depois do M10", que já passou, mas
NENHUM foi iniciado nesta sessão — decidir usar qualquer um deles é escolha do usuário, não
decisão unilateral desta sessão): multi-agent/supervisor, robótica, IoT/edge, computação
quântica, mobile, UI web pesada, fine-tuning.

Dívida técnica conhecida que sobrevive ao 1.0 (nenhuma bloqueante, todas registradas com motivo
acima e em DECISOES.md): `jarvis why` usa índice não-estável entre sessões; `autonomia`/`limites`
do config ainda não são todos lidos; `AnthropicProvider` não existe (`claude_cli` e
`openai_compat` cobertos); streaming não implementado; foco de janela por seletor não suportado;
`digitar()` só ASCII sem acentos; STT roda em CPU por escolha deliberada, não limitação.

Se uma sessão futura for retomar o projeto: ler este arquivo inteiro primeiro (fonte da verdade,
não a memória de conversas passadas), rodar `scripts/check.sh` pra confirmar que ainda está
verde, e só então decidir o que fazer — não há um "próximo passo" pré-definido esperando.
