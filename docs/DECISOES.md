# Registro de decisões técnicas

Formato: data | decisão | motivo | alternativas consideradas | consequências

---

**2026-08-22** | Estrutura em `src/jarvis/` (src layout) em vez de pastas soltas na raiz | O
master prompt nomeia um módulo `io`, que colidiria com o módulo `io` da stdlib do Python se
ficasse solto no topo do sys.path; empacotar tudo sob `jarvis.io` elimina o conflito sem mudar
o nome pedido | (a) manter `io/` na raiz e confiar que nunca haveria colisão de import — rejeitada
por fragilidade; (b) renomear o módulo para `interface/` — rejeitada por contrariar o master
prompt sem necessidade | Todo import interno passa a ser `from jarvis.core import ...` etc.;
`pyproject.toml` usa `tool.setuptools.packages.find` com `where = ["src"]`.

**2026-08-22** | `target-version`/`python_version` do ruff e mypy fixados em 3.14 | A máquina-alvo
tem Python 3.14.6 instalado e o ambiente é criado com `python3.14 -m venv`; testado manualmente que
ruff 0.16.4 e mypy 2.3.1 aceitam `py314`/`"3.14"` sem erro | Usar 3.13 como teto "seguro" —
rejeitada por não refletir o ambiente real da máquina-alvo | Nenhuma sintaxe exclusiva de 3.14 é
usada ainda; a decisão só evita checagem de compatibilidade com uma versão que não é a instalada.

**2026-08-22** | `jarvis` como comando de console aponta para `jarvis.io.cli:principal`, ainda que
a conversa real só chegue no M1 | O M0 já define o ponto de entrada da CLI para que M1 apenas
implemente a lógica, sem mexer em empacotamento | Deixar o entry point para M1 — rejeitada porque
adiaria uma decisão de estrutura que é barata de tomar agora | `jarvis` como comando funciona desde
o M0, mas hoje só imprime uma mensagem de fundação.
