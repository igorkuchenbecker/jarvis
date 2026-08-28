# JARVIS — contexto para sessões de agente

Este arquivo é a fonte da verdade sobre o projeto para qualquer sessão futura. Leia também
`docs/PROJECT_STATE.md` (estado atual, feito, dívida técnica, próximo passo) e
`docs/DECISOES.md` (histórico de decisões técnicas com motivo e alternativas) antes de
qualquer trabalho.

## O que é

Agente pessoal autônomo multimodal para Linux. Não é um chatbot: é uma camada agêntica sobre
o sistema operacional — percebe, planeja, age com ferramentas, observa, avalia e replaneja.
Evolui por marcos verticais (M0..M10) sempre funcionais; ver roadmap completo no histórico do
master prompt original (resumo abaixo).

## Ambiente-alvo (não presumir outro)

CachyOS (Arch), Wayland/Hyprland, shell fish, systemd, ripgrep presente. Ryzen 5 2600, RTX 2060
6GB, 15GiB RAM. Python 3.14 (venv obrigatório, `.venv/` na raiz do repo). Sem chave de API paga
por padrão: provider padrão é a CLI do Claude via subprocess (`claude -p`); `AnthropicProvider`
só entra se `ANTHROPIC_API_KEY` existir no `.env`.

## Estrutura

Monorepo em `~/jarvis`, layout `src/jarvis/`:

- `core/` — loop do agente, estado, goals
- `providers/` — interfaces para LLM/STT/TTS/vision/embeddings (ClaudeCliProvider é o padrão)
- `tools/` — registro declarativo de ferramentas (nome, schema, risco, execute, rollback)
- `security/` — executor: valida schema, risco, allowlist e jail de caminhos antes de rodar
  qualquer ação. O modelo nunca executa nada diretamente.
- `memory/` — working (sessão) + persistente em SQLite (episódios, fatos, auditoria) com FTS5
- `io/` — CLI Rich, canal de voz (`io/audio.py`: dispositivos, captura, reprodução, corte de
  silêncio) e personalidade (sem acesso a security)
- `observability/` — logging estruturado, auditoria JSONL append-only, métricas, tracing

`tests/` (FakeProvider, zero rede) e `tests/golden/*.yaml` (objetivo → ações esperadas →
asserts de estado final). `docs/` para DECISOES.md e PROJECT_STATE.md. `scripts/check.sh` roda
ruff + mypy --strict + pytest.

## Regras fixas (valem para todo o projeto, todas as fases)

1. Máximo esforço de raciocínio antes de codar; reavaliar arquitetura a cada marco.
2. Sem perguntas avulsas de continuidade — decidir, registrar em `docs/DECISOES.md`, seguir.
   Só perguntar se fisicamente bloqueante ou ação CRITICAL irreversível.
3. Fatias pequenas e verticais: cada fatia termina rodando, testada e commitada (um commit por
   fatia, mensagem imperativa curta, sem trailer de atribuição de IA).
4. Nunca deixar código quebrado — se a fatia não fechou, consertar antes de seguir.
5. Ao fim de cada marco: atualizar este arquivo + `docs/PROJECT_STATE.md` e dar resumo de até
   10 linhas.
6. Identificadores em português, zero comentário decorativo.
7. C/Rust proibidos até benchmark provar gargalo real (decisão registrada). SQLite é o banco
   único até M6. Postgres/pgvector só entram se um benchmark do M6 justificar.
8. Toda ferramenta declara: nome, descrição, JSON Schema dos args, nível de risco, validação
   extra, `execute()`, `rollback()` opcional.
9. Riscos: READ_ONLY < LOW < MEDIUM < HIGH < CRITICAL. HIGH/CRITICAL exigem aprovação humana
   interativa sempre, independentemente do nível de autonomia configurado.
10. `pytest` + `ruff` + `mypy --strict`, zero rede nos testes (usar `FakeProvider`). Cada
    ferramenta tem teste unitário + teste malicioso (traversal, binário fora da allowlist,
    schema inválido) provando recusa pelo executor.

## Protocolo de sessão

1. Ler `AGENTS.md` e `docs/PROJECT_STATE.md` antes de qualquer coisa.
2. Trabalhar somente o marco atual; terminá-lo ou deixar o repo verde no último commit.
3. Ao fim: atualizar `PROJECT_STATE.md`, rodar `scripts/check.sh`, commitar.
4. Contexto apertado: despejar estado em `PROJECT_STATE.md` e continuar em nova sessão — o
   arquivo é a fonte da verdade, não a memória da conversa.

## Roadmap (resumo)

M0 Fundação (concluído) · M1 Core conversacional (concluído fora de ordem) · M2 Tool calling
(concluído) · M3 Sistema + segurança plena (concluído) · M4 Loop autônomo + goals (concluído) ·
M5 RAG leve local (concluído) · M6 Embeddings (avaliado, não adotado — ver abaixo) · M7 Visão
(concluído) · M8 Voz (concluído, fora de ordem — ver abaixo) · M9 Computer use controlado
(concluído — ver abaixo) · M10 Integração 1.0 (concluído — ver abaixo).

**Roadmap completo (M0-M10) fechado em 2026-08-23.** Projeto em modo de manutenção/uso a partir
daqui — não há próxima fatia planejada. Ver `docs/PROJECT_STATE.md` seção "Próximo passo" para o
que considerar se uma sessão futura for retomar o trabalho.

Não-objetivos até depois do M10: multi-agent/supervisor, robótica, IoT/edge, computação
quântica, mobile, UI web pesada, fine-tuning.

## M8 — Voz (fatias V0-V4, concluído)

Solicitado diretamente antes de M1-M7 existirem. V0 (fundação de áudio) foi construído fora de
ordem primeiro. V1 (STT, `WhisperSTTProvider`/faster-whisper), V2 (TTS, `PiperTTSProvider`/Piper)
e V3 (conversa por voz push-to-talk, `jarvis voz falar`) foram retomados e concluídos depois que
M1 (core loop) e M2 (tools/executor) já existiam — por isso V3 usa o `processar_turno` COMPLETO,
com ferramentas de verdade, não a ponte reduzida "texto direto a um LLMProvider" cogitada quando
M8 começou (decisão revisitada e substituída, ver `docs/DECISOES.md`). V4 (escopo definido só ao
fechar o marco, nunca detalhado no roteiro original) cobriu robustez: erro de
microfone/transcrição/reprodução num turno não trava o loop de voz, e um teste E2E prova uma
ferramenta real executada e citada na resposta falada.

Fora de escopo (permanece fora do roadmap inteiro, não só desta missão): wake word, escuta
contínua, barge-in, hotkey global do Hyprland, streaming de tokens falados, diarização,
multi-idioma além do pt-BR. STT roda em CPU (não GPU) por padrão — decisão deliberada, não
dívida, ver `docs/DECISOES.md`.

Estado detalhado de cada fatia (V0/V1/V2/V3/V4): `docs/PROJECT_STATE.md`.

## M9 — Computer use controlado (concluído)

Mouse/teclado sintéticos via `evdev.UInput` (dispositivo virtual no nível do kernel — não
`ydotool` nem a API Lua específica desta build do Hyprland, ambas descartadas por motivos
registrados em `docs/DECISOES.md`). `io/entrada.py` (mover_mouse/clicar/digitar/tecla),
`io/janelas.py` (listar_janelas, só leitura via hyprctl), `tools/computador.py`
(`computador.listar_janelas` READ_ONLY, `computador.mover_mouse` MEDIUM,
`computador.clicar`/`digitar`/`tecla` **CRITICAL** — primeiro uso real desse nível de risco no
projeto). Tudo atrás de `computador.habilitada` (`false` por padrão) além da aprovação
interativa que HIGH/CRITICAL já exigem sempre.

Foco de janela por seletor (não só listagem) ficou de fora do M9 — a investigação inicial da API
Lua desta build foi inconclusiva — e foi RESOLVIDO depois (ver "Pós-1.0 — Foco de janela por
seletor (Hyprland)"). `digitar()` só suporta ASCII sem acentos (limitação real de evdev/XKB, não
descuido). Ambos registrados como pendência conhecida em `docs/PROJECT_STATE.md`, não bloqueantes.

## Pós-1.0 — Foco de janela por seletor (Hyprland)

`io/janelas.py::focar_janela(seletor)` + ferramenta `computador.focar_janela` (MEDIUM, atrás da
mesma `computador.habilitada` do M9). Nesta build o dispatch é roteado por uma camada Lua, então
o caminho é: (1) enumera janelas via `hl.get_windows()` (`hyprctl eval` com o "truque do error" —
a build não expõe valor de retorno do eval; o chunk termina em `error(s)` e a lista sai no corpo;
rc=7), endereços == `hyprctl clients -j`; (2) resolve o seletor no índice e dispara
`hyprctl dispatch 'hl.dsp.focus({window=hl.get_windows()[N]})'` — a primitiva que muda o foco.
Fallback clássico (`dispatch focuswindow`) só para build sem API Lua (`SemApiLua`). Seletores:
`address:0x...`, `class:` exata (`class:(x)` aceito), `title:` substring, nome livre. Radiografia
de todos os caminhos descartados (IIFE, eval sandbox, `{window="0x..."}`) em `docs/DECISOES.md`.

## M10 — Integração 1.0 (concluído)

Não introduziu ferramenta nova — foi revisão e validação do projeto inteiro integrado (versão
`1.0.0`, `jarvis --version`, `README.md` atualizado). Validação real de ponta a ponta: conversa
real com o `claude` respondendo corretamente, e `computador.listar_janelas` exercitado através de
uma conversa real (o LLM decidiu sozinho chamar a ferramenta, não foi só teste unitário isolado)
— prova que M9 se integra de verdade ao loop de conversa do M2.

## M1 — Core conversacional (concluído fora de ordem)

Também solicitado diretamente, no meio da missão M8 ("quero testar o jarvis em si"). `jarvis` sem
subcomando agora é uma conversa real de texto com o `ClaudeCliProvider` (via `claude -p`, sem
tools próprias, com `--system-prompt` mínimo e `--resume` para manter a sessão barata — decisões
e números de custo reais em `docs/DECISOES.md`).

## M2 — Tool calling (concluído)

Protocolo de ação próprio (o LLM responde com JSON `{"tipo":"acao",...}` para agir), executor
único em `security/executor.py` que valida schema (`security/schema.py`, validador mínimo
próprio) e jail de caminho (`security/jail.py`) em código antes de rodar qualquer coisa, registro
declarativo de ferramentas (`tools/registro.py`), `fs.read/write/list` e `memory.store/search`
(SQLite FTS5). `core/loop.py::processar_turno` encadeia até 12 chamadas de ferramenta por turno —
é um loop mínimo, não o loop de goals completo do M4. `jarvis` (conversa padrão) já usa isso
automaticamente. Validado na máquina real: pedido para listar arquivos e salvar nota funcionou
ponta a ponta, incluindo o executor recusando uma tentativa de caminho fora do jail e o modelo se
autocorrigindo sozinho.

## M3 — Sistema + segurança plena (concluído)

`sys.info`/`proc.list` (READ_ONLY, stdlib+`/proc`), `proc.kill` (HIGH), `terminal.exec` (MEDIUM,
sem `shell=True`, allowlist de binário, `sudo`/`su`/`doas`/`pkexec` sempre proibidos mesmo que
apareçam na allowlist). Autonomia 0-5 agora é aplicada de verdade no `Executor`
(`TETO_RISCO_POR_AUTONOMIA`): READ_ONLY/LOW/MEDIUM liberados conforme o nível, HIGH/CRITICAL
SEMPRE passam por aprovação humana interativa (`io/cli.py::_solicitar_aprovacao_interativa`),
recusados por padrão se não houver ninguém para perguntar (fail-closed). `jarvis audit`/
`jarvis why <n>` inspecionam a auditoria. Validado na máquina real: `terminal.exec` (MEDIUM, só liberado a partir do nível 3) bloqueado no
nível de autonomia padrão (2), e `proc.kill` real aprovado/negado interativamente matando ou
preservando um processo de teste de verdade.

## M4 — Loop autônomo + goals (concluído)

`core/planejador.py::executar_objetivo` — decompõe um objetivo em subtarefas (LLM responde JSON
`{"tipo":"plano",...}`), roda cada uma com `processar_turno` do M2, decide sucesso/falha pelo
prefixo `SUCESSO:`/`FALHA:` da resposta, replaneja o restante se falhar (até 3 vezes por padrão).
Checkpoint em SQLite (`core/objetivos.py::RepositorioObjetivos`) a cada subtarefa concluída —
`jarvis run` retoma automaticamente um objetivo `em_andamento` encontrado no banco, sem replanejar
nem re-executar o que já passou (retomada pós-crash). `jarvis run "<objetivo>"` no CLI. Validado
com testes determinísticos (`FakeProvider`) cobrindo replanning e retomada pós-crash, e na máquina
real com um objetivo de 3 subtarefas usando `memory.store`/`memory.search`.

## M5 — Conhecimento local / RAG leve (concluído)

`memory/conhecimento.py::RepositorioConhecimento` — ingestão de `.md` (chunking por cabeçalho),
`.txt` (arquivo inteiro), `.pdf` (por página, `pypdf`), FTS5, freshness por mtime, citação
`[arquivo § seção]`. `conhecimento.buscar` (tool) + `jarvis indexar <diretorio>` (só diretórios
listados em `conhecimento.diretorios`, validado com o mesmo `resolver_dentro_do_jail` do M2).
Primeira implementação real de golden tasks (`tests/golden/*.yaml` + `tests/test_golden.py`),
prevista desde o master prompt original mas nunca antes exercida.

**Três bugs reais** encontrados validando isto na máquina (nenhum apareceu nos testes automatizados
até então — detalhes e correções em `docs/DECISOES.md`): título de seção fora do índice FTS5,
consultas FTS5 com AND implícito matando buscas em linguagem natural (corrigido com OR, também
retroaplicado a `memory.search` do M2), e citações `[arquivo § seção]` sendo engolidas pelo Rich
por interpretar colchetes como marcação de estilo (`io/cli.py::_seguro()` agora escapa todo
conteúdo de LLM/ferramentas/auditoria antes de imprimir). Regra prática herdada disto: todo
`console.print()` novo que interpola conteúdo não escrito por nós precisa passar por `_seguro()`.

## M6 — Embeddings opcionais (avaliado, NÃO adotado)

`scripts/benchmark_embeddings.py` comparou FTS5 (produção) com `fastembed` (ONNX, modelo
multilíngue pequeno) num corpus sintético desenhado para expor a lacuna léxico-vs-semântico
(metade das consultas usa sinônimo/parafraseamento sem nenhuma palavra em comum com o trecho
certo). Resultado real: FTS5 hit@1 6/7, embeddings 7/7 — ganho real mas marginal, insuficiente
para justificar a dependência nova (`fastembed`+`onnxruntime`+download de modelo) num projeto
pessoal com corpus tipicamente pequeno. `fastembed` NÃO é dependência do projeto. Critério de
reavaliação e números completos em `docs/DECISOES.md`.

## M7 — Visão (concluído)

`io/tela.py::capturar_tela()` (via `grim`) + `VisionProvider`/`ClaudeCliVisionProvider` (imagem em
base64 via `claude -p --input-format stream-json --output-format stream-json --verbose --tools=`)
+ ferramenta `vision.analyze` (READ_ONLY). Validado na máquina real: "o que está na minha tela?"
respondido corretamente. **Importante, correção de privacidade**: `vision.analyze` NÃO persiste
nada na memória automaticamente — a primeira versão gravava um resumo de cada captura sem pedido
do usuário e chegou a persistir dados pessoais reais numa execução manual (removidos assim que
percebido). A API de `criar_ferramentas_visao()` nem aceita mais um repositório de memória, por
decisão explícita registrada em `docs/DECISOES.md`. Se o usuário quiser lembrar de algo visto na
tela, o LLM usa `memory.store` normalmente, por pedido explícito — nunca automático.

## Pós-1.0 — Integração com GDAP (não é um marco novo do roadmap)

GDAP (Global Data Automation Platform, projeto irmão em `~/gdap`) é uma plataforma de dados
separada com seu próprio servidor HTTP, banco, RBAC e sandbox de SQL. O JARVIS ganhou 5
ferramentas (`gdap.status`, `gdap.listar_datasets`, `gdap.consultar`, `gdap.perguntar`,
`gdap.executar_pipeline`) que falam com ela só pela API HTTP — nunca importa o pacote gdap nem
toca no banco dele, exatamente como qualquer outro cliente da API (a própria CLI/web UI do
GDAP). `io/gdap.py` (transporte `urllib` stdlib, mesmo estilo de `providers/openai_compat.py`,
zero dependência nova) + `tools/gdap.py` (schemas/riscos), atrás do gate
`gdap.habilitada: false` por padrão (mesmo padrão de `computador.habilitada`).

Quatro ferramentas são READ_ONLY: o próprio GDAP já bloqueia INSERT/UPDATE/DELETE/DDL por
padrão no seu guard de SQL, então mesmo `gdap.consultar` com SQL arbitrário não altera dado
nenhum — na pior hipótese o GDAP recusa e devolve erro. `gdap.executar_pipeline` é MEDIUM e só
aceita nomes na allowlist `gdap.pipelines_permitidos` do config.yaml — mesma filosofia de
`terminal.exec`/`allowlist_binarios`, verificada dentro da própria ferramenta porque o Executor
não tem um mecanismo genérico de allowlist além de binário de terminal.

**Bug real encontrado e corrigido no GDAP durante a validação na máquina** (não nos testes com
fakes — mesma lição de sempre deste projeto): `gdap system key create <nome> --role X` reusava
um usuário existente pelo e-mail sem sincronizar o papel armazenado, então reemitir uma chave
com um papel maior para o mesmo nome era um no-op silencioso — a chave dizia ter o papel novo,
mas o principal continuava restrito ao papel antigo. Só apareceu rodando
`gdap.executar_pipeline` de verdade contra um servidor real (o pipeline falhava com "missing
permission(s): dataset:write" mesmo com `--role engineer`). Corrigido no próprio GDAP (dois
pontos: `cli/main.py::key_create` e `api/routers/system.py::create_api_key`), com teste de
regressão provando os dois lados (falha sem a correção, passa com ela).

**Validado na máquina real, ponta a ponta**, não só com fakes: servidor GDAP rodando como
serviço systemd `--user` (`~/.config/systemd/user/gdap.service`, porta 8811 — a 8000 padrão já
estava ocupada por outro processo nesta máquina), chave de API real emitida com papel
`engineer` (papel `analyst` não basta — pipelines que ingerem/publicam dataset exigem
`dataset:write`, só a partir de `engineer`), guardada como variável universal do fish
(`GDAP_API_KEY`, mesmo padrão de `GROQ_API_KEY`). Uma conversa real via `processar_turno` com o
provider Groq configurado do usuário decidiu sozinha chamar `gdap.status` +
`gdap.listar_datasets` para responder "verifique se o GDAP está no ar e liste os datasets" — e
outra decidiu chamar `gdap.perguntar` para responder "por que a receita caiu?", repassando a
resposta do analista de IA do GDAP (com evidência e confiança) na resposta falada/escrita do
JARVIS. `gdap.executar_pipeline` também validado de ponta a ponta contra um pipeline real,
publicando uma nova versão de dataset e gerando relatórios de verdade.

30 testes novos (`tests/test_io_gdap.py`, `tests/test_tools_gdap.py`) — transporte HTTP falso
injetado (mesmo espírito de `test_providers_openai_compat.py`), camada de rede real exercitada
com `urllib` monkeypatchado, e o teste "malicioso" da convenção do projeto provando que um
pipeline fora da allowlist é recusado sem sequer chamar o GDAP. Versão `1.2.0`.

## Pós-1.0 — Indicador de carregamento (não é um marco novo do roadmap)

`with console.status("[dim]pensando...[/dim]", spinner="dots"):` (Rich, já dependência) envolve
a chamada bloqueante ao provider/loop em `_executar_conversa`/`_executar_conversa_voz`, já que o
projeto não faz streaming (decisão do M1). Validado numa sessão real de terminal via `script`
(pseudo-tty) — ver `docs/DECISOES.md` pelo comando exato e o que o log confirmou. Versão `1.0.1`.

## Pós-1.0 — Modo 100% local e autoconhecimento (não é um marco novo do roadmap)

Por decisão do usuário (28/08), o provider ativo do JARVIS é um **Ollama local** (config.yaml não
versionado: `llm_padrao: openai_compat`, `base_url: http://localhost:11434/v1`, modelo
`qwen3:4b`). O default embutido do código continua `claude_cli` (Claude Code via `claude -p`,
que consome a assinatura Pro do usuário — por isso o config.yaml local manda no LLM). A web
(DuckDuckGo) segue disponível quando há conexão; sem rede, `pesquisar`/`web.buscar` devolvem
mensagem amigável em vez de falhar.

`tools/autor.py` cobre autoconhecimento e automanutenção (registrado sempre): `auto.info`
(READ_ONLY: versão, provider ativo com detalhe, estado do git), `auto.mudancas` (READ_ONLY:
git log), e `auto.atualizar`/`auto.editar`/`auto.commit` (**HIGH** — aprovação humana sempre).
Por design, `~/jarvis` NÃO está no `jail_paths` (senão `fs.write` LOW liberaria edição do próprio
código em autonomia 2); `auto.editar` confina caminhos à raiz do repo internamente (caminhos
relativos resolvem da raiz; recusa qualquer coisa fora dela e dentro de `.git`) com rollback.
Sem push automático — publicar no GitHub é decisão do usuário. 19 testes em
`tests/test_tools_autor.py`; suíte 289 passed. Versão `1.4.0`.

## Pós-1.0 — Agendador (não é um marco novo do roadmap)

`jarvis agendar` (add|listar|remover|testar) agenda tarefas periódicas via **systemd user
timers**: cada tarefa vira um par `.service` (oneshot, `ExecStart` = `jarvis run "<objetivo>"`,
auto-resolvido para o binário `jarvis` ou `python -m jarvis.io.cli`) + `.timer` em
`~/.config/systemd/user/`, prefixo `jarvis_tarefa_<slug>`. Agenda por `--diarias HH:MM`,
`--a-cada N` minutos ou `--quando <OnCalendar>`; `--sobrescrever` substitui o mesmo nome.
Regra de segurança: o timer roda sem TTY → toda aprovação HIGH/CRITICAL falha fechada; só
objetivos READ_ONLY concluem automaticamente. `systemctl` é injetável nos testes
(`SistemaSystemctl: Callable[[list[str]], str]`). Detalhe herdado da validação real: processos
sem TTY e sem `GDAP_API_KEY` degradam (stderr + sem ferramentas `gdap.*`) em vez de quebar o
startup. 12 testes em `tests/test_agendar.py`; suíte 318 passed. Versão `1.4.0`.

## Pós-1.0 — Foco de janela por seletor (Hyprland)

`io/janelas.py::focar_janela(seletor)` + ferramenta `computador.focar_janela` (MEDIUM, atrás da
mesma `computador.habilitada` do M9), resolvendo a pendência do M9. Nesta build o dispatch é
roteado por uma camada Lua, então o caminho é: (1) enumera janelas via `hl.get_windows()`
(`hyprctl eval` com o "truque do error" — a build não expõe valor de retorno do eval; o chunk
termina em `error(s)` e a lista sai no corpo da mensagem; rc=7), endereços == `hyprctl clients -j`;
(2) resolve o seletor no índice em Python e dispara
`hyprctl dispatch 'hl.dsp.focus({window=hl.get_windows()[N]})'` — a primitiva que muda o foco de
verdade. Fallback clássico (`dispatch focuswindow`) só para build sem API Lua (`SemApiLua`).
Seletores: `address:0x...` (com ou sem `0x`), `class:` exata (`class:(x)` tem parênteses
removidos), `title:` substring, nome livre. Radiografia de todos os caminhos descartados (IIFE,
eval sandbox, `{window="0x..."}`) em `docs/DECISOES.md`. 14 testes em `tests/test_io_janelas.py`;
suíte 333 passed. Versão `1.4.0`.
