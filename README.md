# JARVIS

Agente pessoal autônomo para Linux: conversa pelo terminal, roda ferramentas no sistema,
planeja objetivos em subtarefas com checkpoint e retomada pós-crash, busca em documentos
locais e enxerga a tela. O modelo nunca executa nada diretamente — toda ação passa por um
executor que valida schema, caminho e nível de risco antes de rodar.

Python 3.14 · SQLite + FTS5 · Rich · Claude Code como LLM (`claude -p`, sem chave de API)

## Comandos

| Comando | Função |
|---|---|
| `jarvis` | Conversa no terminal com acesso às ferramentas |
| `jarvis run "<objetivo>"` | Decompõe o objetivo, executa subtarefa a subtarefa com replanning e retomada pós-crash |
| `jarvis indexar <diretorio>` | Indexa `.md`, `.txt` e `.pdf` para busca local com citação `[arquivo § seção]` |
| `jarvis audit` / `jarvis why N` | Histórico de ações em auditoria append-only (JSONL) |
| `jarvis voz check` | Lista mic/saída padrão do sistema e testa reprodução |

Ferramentas disponíveis ao modelo: `fs.read/write/list`, `memory.store/search`,
`sys.info`, `proc.list`, `proc.kill`, `terminal.exec`, `conhecimento.buscar`, `vision.analyze`.

## Segurança

- Executor único valida schema JSON, jail de caminhos (travessia e symlink) e allowlist
  de binários antes de rodar qualquer ferramenta
- Risco READ_ONLY → CRITICAL mapeado à autonomia 0–5; HIGH/CRITICAL sempre pedem aprovação
  interativa, e sem ninguém para perguntar a ação é recusada (fail-closed)
- `sudo`/`su`/`doas`/`pkexec` recusados em código, mesmo que apareçam na allowlist;
  `terminal.exec` sem `shell=True`, ambiente sanitizado e saída truncada
- `vision.analyze` não grava nada automaticamente — memória só é escrita por pedido explícito

## Rodando

Requer Python 3.14+ e a CLI do `claude` logada (usa a assinatura existente):

```sh
python3.14 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/jarvis                # conversa
scripts/check.sh                # ruff + mypy --strict + pytest
```

Para voz, instale o extra `voz` (`sounddevice`, `numpy`, `faster-whisper`):

```sh
.venv/bin/pip install -e ".[dev,voz]"
.venv/bin/jarvis voz check
```

Configuração opcional em `config.yaml` (modelo em `config.yaml.example`): autonomia,
jail de caminhos, allowlist, diretórios de conhecimento e voz. Sem arquivo, roda com os
padrões embutidos.

123 testes, todos offline (`FakeProvider`, zero rede). Decisões técnicas registradas em
`docs/DECISOES.md`; estado atual e dívida técnica em `docs/PROJECT_STATE.md`.
