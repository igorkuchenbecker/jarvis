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

---

## M8 — Voz

**2026-08-22** | M1-M7 ainda não existem (só M0 foi construído); o marco M8 (voz) foi solicitado
diretamente, fora de ordem | Instrução explícita da missão M8 para começar por V0-V2 (fundação de
áudio, STT, TTS), que não dependem de core loop nem de ferramentas | V0-V2 são construídos
normalmente por serem autocontidos em `providers`/`io`. V3 (conversa por voz ponta-a-ponta usando
"o mesmo core loop do chat textual" e "ferramentas já existentes") depende de M1 (core loop +
LLMProvider) e M2 (tools) — que não existem. Alternativas: (a) implementar M1/M2 mínimos agora só
para destravar V3 — rejeitada por sair do escopo desta missão (M8) e duplicar trabalho que será
refeito com mais cuidado quando M1/M2 forem o marco corrente; (b) pular V3 inteiramente até M1/M2
existirem — rejeitada porque o valor de "conversar por voz" pode ser demonstrado com uma ponte
mínima direta ao LLM | Quando V3 for implementado, o escopo será reduzido: texto da fala vai direto
a um `LLMProvider` (sem tool-calling), produzindo respostas faladas coerentes; os exemplos de DoD
que dependem de ferramentas ("salve uma nota", "leia essa nota") ficam registrados como pendência
para quando M2 existir, substituídos por perguntas que não dependem de tools (ex.: "que horas são"
respondido localmente, perguntas gerais respondidas pelo LLM). Isso será revisitado explicitamente
na fatia V3.

**2026-08-22** | VAD implementado como energia do sinal (RMS) em Python/numpy puro, em vez de
`webrtcvad` ou `silero-vad` como sugerido no roteiro | `webrtcvad` (pacote de 2019, última
publicação years atrás) importa `pkg_resources` em tempo de execução; o `setuptools` moderno
(84.0, o disponível via pip hoje) removeu `pkg_resources` do pacote, então `import webrtcvad`
quebra com `ModuleNotFoundError` mesmo com `setuptools` instalado. `silero-vad` exigiria `torch`
como dependência só para cortar silêncio nas pontas de uma gravação push-to-talk — peso
desproporcional ao problema | (a) fixar `setuptools<81` só para satisfazer o `webrtcvad` —
rejeitada por reintroduzir uma dependência não mantida e travar a versão do setuptools do venv
inteiro por causa de um detalhe de VAD; (b) `silero-vad`/torch — rejeitada pelo custo de
instalação e VRAM/CPU para um corte de silêncio nas pontas, quando V3 já usa push-to-talk via
ENTER (não precisa de VAD em tempo real, só aparar silêncio das pontas do WAV capturado) | VAD
vira uma função pura (`aparar_silencio`) em `jarvis.io.audio`, testável sem dependência externa
nenhuma; se um VAD mais sofisticado for necessário no futuro (barge-in, escuta contínua — fora do
escopo desta missão), reavaliar então com benchmark.

**2026-08-22** | `capturar()`/`tocar()` usam `device=None` por padrão (deixando o PortAudio
resolver), e a checagem de dispositivo padrão consulta `sd.query_devices(kind=...)` em vez de
pegar o primeiro item de `listar_dispositivos()` | Bug reproduzido na máquina real: o primeiro
dispositivo de saída na lista bruta do PortAudio era `HDA NVidia: HDMI 1 (hw:0,7)`, um dispositivo
ALSA cru travado em 44100Hz, que rejeitou a captura/reprodução a 16000Hz
(`Invalid sample rate [PaErrorCode -9997]`); o pseudo-dispositivo `default`/`pulse` (índice 8 nesta
máquina) já roteia pelo PipeWire e faz resample automaticamente | Continuar escolhendo "o primeiro
dispositivo com canais compatíveis" da lista bruta — rejeitada por ser exatamente a causa do bug:
não há garantia de que o primeiro dispositivo aceite a taxa de amostragem desejada | `config.yaml`
com `voz.dispositivo: auto` agora significa "não fixar nenhum índice, deixar o sistema decidir",
não "primeiro da lista". `dispositivo_padrao_do_sistema()` existe só para exibição amigável do
nome do dispositivo ao usuário; a escolha real de rota de áudio é sempre feita pelo PortAudio.

---

## M1 — Core conversacional

**2026-08-22** | M1 foi construído fora de ordem, a pedido direto do usuário no meio da missão
M8 ("quero testar o jarvis em si, não só a parte de microfone") | Sem M1 não existe "jarvis" para
testar de verdade — só fundação (M0) e E/S de áudio isolada (M8/V0) | Terminar M8 primeiro e só
depois voltar a M1 — rejeitada porque o usuário pediu explicitamente para testar o agente
conversando, e isso não é possível sem M1 | M1 implementado como fatia autocontida (providers,
configuração, loop de conversa no CLI), sem tocar no que falta de M2-M7. Voltar ao roadmap M8
V1-V4 depois desta fatia, a menos que o usuário redirecione de novo.

**2026-08-22** | `ClaudeCliProvider` chama `claude -p --output-format json --tools= --system-prompt
"<persona mínima>"`, com `--session-id`/`--resume` para manter a conversa | Testado na máquina
real: sem restringir nada, cada chamada custou ~US$0,035-0,05 e recarregava ~8-11 mil tokens de
contexto padrão do Claude Code (CLAUDE.md, definição de ferramentas etc.), mesmo para "qual é a
capital do Brasil?". Com `--system-prompt` próprio (substituindo o padrão) o custo caiu para
~US$0,012 na primeira chamada; com `--resume` na mesma sessão, a segunda chamada custou ~US$0,001
(cache do lado do Anthropic). `--tools=` desliga as ferramentas nativas do Claude Code — sem isso,
o provider poderia executar ações no sistema por conta própria, violando o invariante "o modelo
nunca executa nada" (quem decide/executa é o executor do JARVIS, a partir do M2) | (a) usar o
system prompt padrão do Claude Code — rejeitada pelo custo e por trazer identidade/instruções que
não são as do JARVIS; (b) `--bare` para cortar ainda mais overhead — rejeitada porque exige
`ANTHROPIC_API_KEY` (nunca lê OAuth/keychain), contrariando a decisão de usar a assinatura
existente sem chave paga | Todo uso do `ClaudeCliProvider` em produção paga por token via a
assinatura do usuário; manter `--system-prompt` enxuto e `--resume` sempre que possível é o que
mantém isso barato. Testes usam um binário `claude` falso, nunca o real.

**2026-08-22** | Interface `LLMProvider` é `enviar(mensagem: str) -> str` (stateful, uma mensagem
por vez) em vez de `enviar(historico: list[Mensagem]) -> str` (stateless, histórico completo a
cada chamada) | O `ClaudeCliProvider` já ganha continuidade de graça via `--resume` da própria CLI
(sessão do lado do Claude Code); reenviar o histórico inteiro a cada turno jogaria fora esse cache
e faria o custo crescer com o tamanho da conversa. Cada provider passa a ser responsável por
guardar seu próprio estado de sessão | Interface stateless com histórico completo — rejeitada por
ser mais cara no caso real (`ClaudeCliProvider`) sem ganho de simplicidade correspondente (o loop
do CLI já não precisa gerenciar uma lista de mensagens, só chamar `enviar()` e imprimir) | Quando
`AnthropicProvider`/`OpenAICompatProvider` chegarem, cada um decide internamente como manter seu
próprio histórico (provavelmente guardando a lista de mensagens dentro da instância). `reiniciar()`
existe na interface para descartar a sessão/histórico corrente sem recriar o provider.

**2026-08-22** | M1 usa `--output-format json` (não-streaming), apesar do master prompt sugerir
`stream-json` | Streaming exigiria parsear eventos parciais e não é necessário para o DoD do M1
("conversa real funcionando no terminal") — uma resposta completa impressa de uma vez já cumpre
isso, com pipeline bem mais simples de implementar e testar | Implementar streaming já no M1 —
rejeitada por adicionar complexidade (parsing incremental, testes de streaming) sem que o DoD
exija | Streaming fica como melhoria futura, não registrada como pendência obrigatória de nenhum
marco específico; revisitar apenas se a latência de resposta completa incomodar no uso real.

**2026-08-22** | `carregar_configuracao()` tem padrões embutidos no código (dataclasses com
`default`) e só sobrescreve com o que estiver em `~/jarvis/config.yaml`, que continua opcional |
`config.yaml` nunca é versionado (está no `.gitignore` desde o M0); o `jarvis` precisa funcionar
"out of the box" sem o usuário copiar `config.yaml.example` manualmente primeiro | Exigir que
`config.yaml` exista (erro se ausente) — rejeitada por atrito desnecessário para uso local pessoal;
ler `config.yaml.example` como config real em runtime — rejeitada por misturar "arquivo de
documentação/template" com "arquivo de configuração efetiva" | Só as chaves de `provedor.llm_padrao`
e `provedor.claude_cli.*` são lidas por enquanto — as demais seções de `config.yaml.example`
(autonomia, limites, segurança, voz) ainda não têm código que as leia; ler quando o marco
correspondente (M2/M3/M8-V1+) precisar delas.

---

## M2 — Tool calling

**2026-08-22** | Validação de schema de argumentos é um validador próprio, mínimo, em
`security/schema.py` (object/properties/required/additionalProperties + tipos
string/integer/number/boolean/array/object), em vez da biblioteca `jsonschema` | As 5 ferramentas
do M2 (`fs.read/write/list`, `memory.store/search`) têm schemas simples e planos — sem `$ref`,
`oneOf`, `anyOf` ou schemas aninhados complexos. `jsonschema` traria uma cadeia de dependências
(hoje inclui `referencing`, `rpds-py`/`attrs` dependendo da versão) desproporcional ao que é
realmente validado | Adotar `jsonschema` desde já, prevendo schemas mais ricos no futuro —
rejeitada por "simplicidade vence sofisticação aparente" (regra do projeto): YAGNI até uma
ferramenta futura realmente precisar de uma feature de JSON Schema que o validador próprio não
cobre; nesse momento, reavaliar | Se/quando uma ferramenta precisar de schema aninhado ou
validação condicional, essa é a hora de trocar para `jsonschema` — não antes.

**2026-08-22** | Jail de caminho (`security/jail.py`) usa `Path.resolve()` (segue symlinks,
normaliza `..`) e compara com `Path.parents`/igualdade contra as raízes autorizadas — testado com
um teste malicioso de symlink apontando para fora do jail (bloqueado) e travessia `../..`
(bloqueada) | É o invariante mais importante do M2 ("O modelo nunca executa nada... validação é
código no executor, nunca prompt") logo precisa ser a coisa mais testada do marco. Confirmado na
máquina real: ao pedir "liste os arquivos do meu workspace", o modelo tentou primeiro
`fs.list(".")` (resolvendo para `~/jarvis`, fora do jail) — o executor recusou automaticamente e o
modelo corrigiu sozinho para o caminho absoluto correto na tentativa seguinte, sem que nenhuma
instrução de prompt tivesse pedido isso — prova de que a validação em código funciona
independentemente do que o modelo "decida" fazer | N/A (não há alternativa razoável a
`resolve()` + comparação de caminho para este problema).

**2026-08-22** | O tool-calling do M2 usa um protocolo textual próprio: o LLM responde com um JSON
`{"tipo": "acao", "ferramenta": "...", "argumentos": {...}}` quando quer agir, verificado por
`core/loop.py::processar_turno` (até 12 iterações por turno, mesmo teto de
`limites.max_iteracoes_por_objetivo` do config.yaml.example) — não o tool-calling nativo da API
Anthropic (`tool_use`/`tool_result` blocks) | O `ClaudeCliProvider` fala com a CLI `claude`, que já
tem sua própria noção de "ferramentas" (que desligamos com `--tools=` desde o M1, exatamente para
que o JARVIS seja quem decide o que roda). Usar `tool_use` nativo exigiria trocar de arquitetura
de provider (SDK direto, não mais `claude -p`) e contrariaria a decisão já tomada no M1 de usar a
CLI com a assinatura existente | Aguardar o `AnthropicProvider` (SDK) para ter tool-calling nativo
— rejeitada porque adiaria o M2 inteiro para depois de um marco que nem está no roadmap ainda |
Quando o `AnthropicProvider` existir, ele pode oferecer tool-calling nativo por baixo do mesmo
`LLMProvider`/`processar_turno`, ou `processar_turno` pode ganhar um modo nativo — decidir então,
não agora.

**2026-08-22** | `core/loop.py::processar_turno` implementa só o laço "chamar ferramenta → ver
resultado → chamar de novo ou responder", sem decomposição em subtarefas, replanning ou
checkpoint em SQLite (isso é M4) | O DoD do M2 ("liste os arquivos e salve uma nota ponta a
ponta") já exige encadear 2 ações antes de uma resposta final, o que não dá pra fazer com uma
chamada única ao LLM — mas não exige nada do que M4 promete (retomada pós-crash, critérios de
sucesso/falha por subtarefa, replanning) | Implementar o M4 completo agora, já que "o loop" está
sendo tocado — rejeitada por escopo: o roadmap separa isso de propósito, e a versão mínima já
resolve o problema do M2 sem antecipar trabalho que merece ser feito com cuidado próprio | Quando
M4 chegar, `processar_turno` provavelmente vira uma peça interna de um loop maior com goals,
persistência de estado e replanning — não descartar, evoluir.

**2026-08-22** | `memory.store`/`memory.search` gravam em uma única tabela virtual FTS5
(`memorias(texto, criado_em UNINDEXED)`), sem distinguir "fatos" de "episódios" ainda, apesar da
seção MEMÓRIA do master prompt descrever as duas categorias separadamente | M2 pede só
"memory.search/store" como ferramentas — a distinção fatos-vs-episódios e a regra "fatos só
gravados com comando explícito 'lembre que...'" são comportamento do LLM/core (o que decide
quando chamar `memory.store`), não uma restrição que o executor deva codificar; modelar isso
agora seria adivinhar uma necessidade que ainda não apareceu | Criar tabelas separadas
`fatos`/`episodios` desde já — rejeitada por YAGNI: sem um caso de uso concreto ainda para
diferenciá-las na busca, uma tabela única já cumpre "busca textual com FTS5" | Se/quando a
distinção importar (ex.: o RAG do M5 precisar separar memória de documentos ingeridos), revisitar
o schema da tabela.

---

## M3 — Sistema + segurança plena

**2026-08-22** | Mapa fixo de teto de risco por nível de autonomia
(`TETO_RISCO_POR_AUTONOMIA = {0: nenhum, 1: READ_ONLY, 2: LOW, 3: MEDIUM, 4: MEDIUM, 5: MEDIUM}`),
e HIGH/CRITICAL SEMPRE passam por um callback de aprovação humana interativa, nunca liberados só
por autonomia alta | Regra fixa do próprio AGENTS.md ("HIGH/CRITICAL exigem aprovação humana
interativa sempre, independentemente do nível de autonomia"). Autonomia 4/5 ("tarefas longas
autônomas"/"alta autonomia sob política estrita") descrevem duração/escopo da tarefa, não uma
licença para pular aprovação em ações de risco alto — por isso o teto de auto-execução não sobe
além de MEDIUM em nenhum nível | Deixar nível 5 auto-executar HIGH sem aprovação — rejeitada por
contrariar regra explícita do projeto, não é uma decisão de engenharia aberta | Testado com 7
combinações (nível × risco) mais os 3 cenários de aprovação (sem callback, callback nega,
callback aprova) — os dois últimos validados também na máquina real com `proc.kill` de verdade
(processo morto quando aprovado, mantido vivo quando negado).

**2026-08-22** | Sem callback de aprovação configurado, ação HIGH/CRITICAL é RECUSADA por padrão
(fail-closed), não liberada | Não há UI para perguntar em todo contexto que usa o `Executor`
(ex.: um golden test do M4, ou um script) — na ausência de alguém para perguntar, a escolha segura
é nunca executar, nunca a de assumir "sim" | Executar por padrão quando não há callback —
rejeitada por violar o princípio de segurança mais básico do projeto (fail-safe) | `io/cli.py`
fornece `_solicitar_aprovacao_interativa` (prompt real no terminal) como o único callback real
hoje; qualquer novo canal de E/S (voz, uma futura UI) precisa fornecer o seu.

**2026-08-22** | `terminal.exec` nunca usa `shell=True`; argumentos vão como lista para
`subprocess.run`, ambiente reduzido a `PATH`/`HOME`/`LANG` (não repassa o ambiente do processo do
JARVIS) e `sudo`/`su`/`doas`/`pkexec` são recusados no código do executor mesmo que apareçam na
allowlist do config.yaml por engano | `shell=True` seria injeção de comando por design (a essência
do que "sem sudo" e "allowlist" tentam evitar); repassar o ambiente inteiro do JARVIS a um binário
arbitrário da allowlist arriscaria vazar segredos (ex.: se um dia houver uma API key em variável de
ambiente) | Repassar `os.environ` inteiro para conveniência — rejeitada por superfície de vazamento
desnecessária; permitir configurar `shell=True` como opção — rejeitada, nunca deveria existir |
Testado com metacaracteres de shell (`$(whoami)`, `; ls`) confirmando que chegam literais ao
`echo`, não interpretados.

**2026-08-22** | `sys.info`/`proc.list` usam só stdlib + `/proc` (Linux), sem adicionar `psutil` |
O projeto é Linux-first (CachyOS) por decisão de ambiente já registrada no M0; `/proc/meminfo`,
`/proc/uptime`, `/proc/<pid>/comm` e `os.statvfs`/`os.getloadavg` cobrem tudo que essas duas
ferramentas precisam sem nenhuma dependência nova | Adicionar `psutil` para código mais portável
entre SOs — rejeitada por YAGNI: o projeto não tem meta de rodar em outro SO, e stdlib+`/proc` já
resolve | Se um dia houver meta de portabilidade (não há hoje), essa é a hora de reavaliar.

**2026-08-22** | Dependências de voz (`sounddevice`, `numpy`, `faster-whisper`) isoladas no extra
opcional `voz` do `pyproject.toml`, não nas dependências base do projeto | `config.yaml.example`
já prevê `voz.habilitada: false` por padrão; quem não usa voz não deveria precisar baixar
`faster-whisper`/`ctranslate2` (dependência pesada) só para instalar o `jarvis` | Colocar tudo nas
dependências base — rejeitada por inflar a instalação padrão para quem só quer o modo texto |
Ambiente de desenvolvimento instala com `pip install -e ".[dev,voz]"`; produção decide conforme uso.
