# JARVIS

Assistente pessoal para Linux: conversa por texto ou voz, executa ferramentas no
sistema (mouse/teclado/janelas), decompõe objetivos em subtarefas com checkpoint
e retomada pós-crash, busca em documentos locais e pode analisar o que está na
tela. O modelo nunca executa nada diretamente — toda ação passa por um executor
que valida schema, caminho e nível de risco antes de rodar.

Python 3.14 · SQLite + FTS5 · Rich

## Finalidade

Automatizar tarefas no próprio computador via linguagem natural, com segurança
e auditoria: pedir comandos, agendar objetivos longos que se retomam sozinhos
se quebrar, consultar conhecimento local com citação, e operar a máquina (voz,
mouse, teclado e janelas) sempre sob aprovação humana quando o risco exige.

## Como funciona

```text
Você ──> jarvis ──> modelo de IA ──> executor valida schema/risco/caminho ──> ferramenta
                <────────────────────── resultado + auditoria ──────────────────
```

- **Executor único**: valida JSON Schema, jail de caminhos (travessia e symlink) e
  allowlist de binários antes de qualquer ferramenta rodar; `sudo`/`su`/`doas`/`pkexec`
  são recusados em código
- **Risco READ_ONLY → CRITICAL** mapeado à autonomia 0–5; HIGH/CRITICAL sempre pedem
  aprovação interativa (fail-closed se não houver ninguém para perguntar)
- **Comandos**:

| Comando | Função |
|---|---|
| `jarvis` | Conversa no terminal com acesso às ferramentas |
| `jarvis run "<objetivo>"` | Decompõe o objetivo, executa subtarefa a subtarefa com replanning e retomada pós-crash |
| `jarvis indexar <diretorio>` | Indexa `.md`, `.txt` e `.pdf` para busca local com citação `[arquivo § seção]` |
| `jarvis audit` / `jarvis why N` | Histórico de ações em auditoria append-only (JSONL) |
| `jarvis voz check` | Lista mic/saída padrão do sistema e testa reprodução |
| `jarvis voz falar` | Conversa por voz push-to-talk (ENTER grava), com as mesmas ferramentas do modo texto |

Ferramentas disponíveis: `fs.read/write/list`, `memory.store/search`, `sys.info`,
`proc.list`, `proc.kill`, `terminal.exec`, `conhecimento.buscar`, `vision.analyze`
e — com `computador.habilitada: true` — `computador.listar_janelas/mover_mouse/
clicar/digitar/tecla`. Com `gdap.habilitada: true`, consulta o catálogo de dados e
o analista de IA do [GDAP](https://github.com/igorkuchenbecker/gdap) e executa
pipelines cadastrados (allowlist por nome).

- **Voz** (STT/TTS locais), **computer use** (mouse/teclado/janelas) e **GDAP** vêm
  desligados por padrão; ligam por configuração
- **247 testes offline** (fakes/mocks, zero rede); decisões técnicas registradas em
  `docs/DECISOES.md`; estado atual e dívida técnica em `docs/PROJECT_STATE.md`

## Como rodar

Requer Python 3.14+:

```sh
python3.14 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/jarvis                # conversa
scripts/check.sh                # ruff + mypy --strict + pytest
```

Voz (extra `voz` — sounddevice, numpy, faster-whisper, piper-tts; STT/TTS rodam
localmente, modelos baixados automaticamente no primeiro uso):

```sh
.venv/bin/pip install -e ".[dev,voz]"
.venv/bin/jarvis voz check
.venv/bin/jarvis voz falar     # requer voz.habilitada: true em config.yaml
```

Computer use (extra `computador` — evdev) e o gate em `config.yaml`:

```sh
.venv/bin/pip install -e ".[dev,voz,computador]"
```

```yaml
computador:
  habilitada: true   # requer escrita em /dev/uinput (verifique com getfacl)
```

GDAP (projeto irmão de automação de dados): rode o servidor dele, gere uma chave
com papel `engineer` e ligue em `config.yaml` — sem dependência nova (cliente
`urllib` da stdlib).

```yaml
gdap:
  habilitada: true
  base_url: http://127.0.0.1:8000
  api_key_env: GDAP_API_KEY   # exporte a chave na variável, nunca no config.yaml
  pipelines_permitidos: [nome_do_pipeline]
```

Configuração opcional em `config.yaml` (modelo em `config.yaml.example`): autonomia,
jail de caminhos, allowlist, diretórios de conhecimento, voz e computador. Sem
arquivo, roda com os padrões embutidos (tudo que é arriscado vem desligado).