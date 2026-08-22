# Estado do projeto JARVIS

**Versão:** 0.1.0 (M0 — Fundação)
**Última atualização:** 2026-08-22

## Feito

- Repositório git inicializado em `~/jarvis`.
- Layout `src/jarvis/` com pacotes vazios: `core`, `providers`, `tools`, `security`, `memory`,
  `io`, `observability` — prontos para receber código dos próximos marcos.
- `pyproject.toml` com dependências (`rich`, `pyyaml`) e dev (`pytest`, `ruff`, `mypy`), targets
  fixados em Python 3.14.
- `observability/logs.py`: logging estruturado em JSON (stderr + arquivo opcional).
- `observability/auditoria.py`: `RegistradorAuditoria` append-only em JSONL, com testes cobrindo
  gravação, leitura e natureza append-only.
- `io/cli.py`: stub do comando `jarvis` (ainda sem conversa real).
- `config.yaml.example`: autonomia, provedores, limites, allowlists de segurança, caminhos.
- `scripts/check.sh`: roda ruff, mypy --strict e pytest em sequência.
- `docs/DECISOES.md` iniciado com as primeiras 3 decisões de arquitetura.
- `AGENTS.md` com o contexto do projeto para sessões futuras; `CLAUDE.md` symlink para ele.

## Bugs conhecidos

Nenhum.

## Dívida técnica

- Nenhum provider (`ClaudeCliProvider`, `FakeProvider` etc.) implementado ainda — chega no M1.
- Nenhuma ferramenta (`fs.*`, `memory.*`) nem executor de ações — chega no M2/M3.
- `config.yaml.example` ainda não é lido por código nenhum; carregamento de config chega quando
  algum módulo precisar dele (provavelmente M1, junto do provider).
- `jarvis.db` (SQLite) ainda não existe — chega quando memória/checkpoints forem implementados.

## Próximo passo

Iniciar M1 — Core conversacional: CLI Rich com sessão/histórico, `ClaudeCliProvider` real
(chamando `claude -p --output-format stream-json` via subprocess, com erro amigável se o binário
`claude` não existir no PATH), `FakeProvider` determinístico para os testes, streaming se a CLI
suportar. DoD do M1: conversa real funcionando no terminal e `scripts/check.sh` verde.
