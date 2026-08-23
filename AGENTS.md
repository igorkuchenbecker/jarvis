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
(próximo) · M10 Integração 1.0.

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
