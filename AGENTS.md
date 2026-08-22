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
- `io/` — CLI Rich e personalidade/voz (sem acesso a security)
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

M0 Fundação (concluído) · M1 Core conversacional · M2 Tool calling · M3 Sistema + segurança
plena · M4 Loop autônomo + goals · M5 RAG leve local · M6 Embeddings (só se benchmark provar
ganho) · M7 Visão · M8 Voz · M9 Computer use controlado · M10 Integração 1.0.

Não-objetivos até depois do M10: multi-agent/supervisor, robótica, IoT/edge, computação
quântica, mobile, UI web pesada, fine-tuning.
