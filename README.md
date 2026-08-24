# JARVIS

Agente pessoal autônomo para Linux: conversa por texto ou voz, roda ferramentas no sistema
(inclusive mouse/teclado/janelas), planeja objetivos em subtarefas com checkpoint e retomada
pós-crash, busca em documentos locais e enxerga a tela. O modelo nunca executa nada diretamente
— toda ação passa por um executor que valida schema, caminho e nível de risco antes de rodar.

Python 3.14 · SQLite + FTS5 · Rich · Claude Code como LLM (`claude -p`, sem chave de API)

## Comandos

| Comando | Função |
|---|---|
| `jarvis` | Conversa no terminal com acesso às ferramentas |
| `jarvis run "<objetivo>"` | Decompõe o objetivo, executa subtarefa a subtarefa com replanning e retomada pós-crash |
| `jarvis indexar <diretorio>` | Indexa `.md`, `.txt` e `.pdf` para busca local com citação `[arquivo § seção]` |
| `jarvis audit` / `jarvis why N` | Histórico de ações em auditoria append-only (JSONL) |
| `jarvis voz check` | Lista mic/saída padrão do sistema e testa reprodução |
| `jarvis voz falar` | Conversa por voz push-to-talk (ENTER grava), com as mesmas ferramentas do modo texto |

Ferramentas disponíveis ao modelo: `fs.read/write/list`, `memory.store/search`,
`sys.info`, `proc.list`, `proc.kill`, `terminal.exec`, `conhecimento.buscar`, `vision.analyze`,
e — com `computador.habilitada: true` — `computador.listar_janelas/mover_mouse/clicar/digitar/tecla`.
Com `gdap.habilitada: true`, ganha `gdap.status/listar_datasets/consultar/perguntar` (consulta o
catálogo e o analista de IA do [GDAP](https://github.com/igorkuchenbecker/gdap), projeto irmão de automação de dados) e
`gdap.executar_pipeline` (roda um pipeline de dados já cadastrado, allowlist por nome).

## Segurança

- Executor único valida schema JSON, jail de caminhos (travessia e symlink) e allowlist
  de binários antes de rodar qualquer ferramenta
- Risco READ_ONLY → CRITICAL mapeado à autonomia 0–5; HIGH/CRITICAL sempre pedem aprovação
  interativa, e sem ninguém para perguntar a ação é recusada (fail-closed)
- `sudo`/`su`/`doas`/`pkexec` recusados em código, mesmo que apareçam na allowlist;
  `terminal.exec` sem `shell=True`, ambiente sanitizado e saída truncada
- `vision.analyze` não grava nada automaticamente — memória só é escrita por pedido explícito
- Ferramentas de computer use (`computador.clicar/digitar/tecla`) são CRITICAL e ficam
  desligadas por padrão (`computador.habilitada: false`) — nenhum allowlist consegue restringir
  com segurança o que pode ser clicado/digitado, então a defesa é a aprovação interativa sempre
  exigida para esse nível de risco, mais o gate explícito de configuração

## Rodando

Requer Python 3.14+ e a CLI do `claude` logada (usa a assinatura existente):

```sh
python3.14 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/jarvis                # conversa
scripts/check.sh                # ruff + mypy --strict + pytest
```

Para voz, instale o extra `voz` (`sounddevice`, `numpy`, `faster-whisper`, `piper-tts` — STT/TTS
rodam localmente, modelos baixados automaticamente no primeiro uso):

```sh
.venv/bin/pip install -e ".[dev,voz]"
.venv/bin/jarvis voz check
.venv/bin/jarvis voz falar     # requer voz.habilitada: true em config.yaml
```

Para computer use (mouse/teclado/janelas), instale o extra `computador` (`evdev`) e ligue
`computador.habilitada: true` em `config.yaml`. Requer acesso de escrita a `/dev/uinput`
(verifique com `getfacl /dev/uinput` — em algumas distros já vem liberado por regras udev de
outros programas, como KDE Connect; caso contrário, é necessário configurar isso manualmente):

```sh
.venv/bin/pip install -e ".[dev,voz,computador]"
```

Para usar o [GDAP](https://github.com/igorkuchenbecker/gdap) (catálogo de dados, consultas, analista de IA, pipelines), rode o
servidor dele (`gdap system serve`, ou o serviço systemd `--user` — ver `~/gdap/README.md`),
gere uma chave (`gdap system key create jarvis --role engineer` — `analyst` não basta para
pipelines que escrevem dados) e ligue em `config.yaml`:

```yaml
gdap:
  habilitada: true
  base_url: http://127.0.0.1:8000
  api_key_env: GDAP_API_KEY   # exporte a chave nessa variável, nunca no config.yaml
  pipelines_permitidos: [nome_do_pipeline]
```

Zero dependência nova — o cliente usa `urllib` da stdlib, mesmo estilo do provider `openai_compat`.

Configuração opcional em `config.yaml` (modelo em `config.yaml.example`): autonomia,
jail de caminhos, allowlist, diretórios de conhecimento, voz e computador. Sem arquivo, roda com
os padrões embutidos (tudo que é arriscado — voz, computer use — vem desligado por padrão).

247 testes, todos offline (`FakeProvider`/mocks, zero rede — os `scripts/validar_*_real.py` são
validação manual à parte, fora da suíte, que de fato baixam modelos/tocam hardware). Decisões
técnicas registradas em `docs/DECISOES.md`; estado atual e dívida técnica em
`docs/PROJECT_STATE.md`.
