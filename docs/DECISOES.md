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

**2026-08-23** | Lição externa (projeto Moon Browser, fork do Firefox): publicar um clone git RASO
(`--depth N`, histórico de terceiros + commits próprios) num repositório GitHub novo falhou 2x
seguidas com `remote: fatal: did not receive expected object <hash>` / `index-pack failed`,
sempre o mesmo hash — confirmado com `git cat-file -t <hash>` que o objeto genuinamente não existe
no repo local (problema estrutural na cadeia de deltas do clone raso, não instabilidade de rede) |
Relevante para qualquer ferramenta futura do jarvis que precise publicar/sincronizar um repositório
git com histórico raso num remote novo (nenhuma ferramenta faz isso hoje) | Insistir tentando de
novo do mesmo jeito — rejeitada, o erro é determinístico, não aleatório | Correção que funcionou:
`git checkout --orphan <branch>`, commitar o estado atual da árvore como commit único (sem
histórico), `git push origin <branch>:main --force`. Efeito colateral: o remote perde o histórico
granular (aceitável/desejável quando o objetivo é só publicar o estado atual). Nota adicional:
depois de um push assim (commit único gigante, ex. ~474 mil arquivos), os metadados derivados do
GitHub (`size`, `/languages` da API) podem ficar zerados por muito mais tempo que o normal,
independente de pushes seguintes (force ou não) — não confiar nesses campos como sinal de sucesso;
usar a Contents API ou `git ls-remote` pra confirmar o conteúdo real. Detalhes completos:
`second-brain/05-learnings/git-shallow-clone-push-to-new-remote-fails.md` e
`github-stale-language-stats-large-push.md`.

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

**2026-08-23** | M8/V1 (STT): `WhisperSTTProvider` usa `faster-whisper` com `device="cpu"` e
`compute_type="int8"` como padrão, não `device="auto"`/CUDA, mesmo com RTX 2060 disponível |
Rodar CTranslate2 em GPU exige cuDNN/cuBLAS compatíveis instalados no sistema, o que nunca foi
validado nesta máquina; falhar silenciosamente ou com um erro obscuro na primeira execução por
causa de uma biblioteca de sistema ausente é pior do que começar simples e funcionando | (a)
`device="auto"` — rejeitada por poder falhar de formas difíceis de diagnosticar se o stack CUDA
do sistema não bater com o que CTranslate2 espera, sem benefício medido (nenhum benchmark
mostrou que CPU é lento demais para uso interativo push-to-talk) | Validado na máquina real:
modelo "small" em CPU carrega em ~10s e transcreve uma frase de ~2s de áudio em ~3s — aceitável
para conversa por voz não teleimediata. Reavaliar GPU só se um caso de uso real exigir latência
menor, com benchmark antes de trocar o default.

**2026-08-23** | M8/V2 (TTS): Piper via pacote `piper-tts` (não o binário standalone/CLI
tradicional do projeto Piper) | `piper-tts` é instalável via pip, roda em processo (sem precisar
gerenciar um subprocess feito à mão como o `ClaudeCliProvider` faz para o `claude`), inclui
`onnxruntime` e uma API Python (`PiperVoice.load()`/`.synthesize()`) que devolve
`np.ndarray` diretamente — encaixa no mesmo formato de dado (float32 mono) usado por todo
`io.audio` e pelo STT, sem conversão extra | Baixar e invocar o binário `piper` standalone via
subprocess — rejeitada por exigir gerenciar um binário externo separado (download, permissão de
execução, parsing de stdout) quando a biblioteca Python já resolve isso nativamente | Modelo de
voz (`pt_BR-faber-medium`, .onnx + .onnx.json) baixado automaticamente no primeiro uso, salvo em
`caminhos.modelos_voz` (`~/jarvis/dados/modelos_voz` por padrão) — uso subsequente não precisa de
rede. Validado na máquina real com um round-trip TTS→STT (`scripts/validar_voz_real.py`): Piper
sintetiza "o rato roeu a roupa do rei de roma", Whisper transcreve de volta reconhecendo a frase
(com pequenas imprecisões esperadas de um modelo "small" numa voz sintética, não um erro do
pipeline) — e reprodução real via `tocar()` a 22050Hz (taxa nativa do Piper, diferente dos
16000Hz usados no resto do pipeline) funciona sem ajuste extra, confirmando que o design
"device=None, deixa o PipeWire resample" do M8/V0 já cobre taxas de amostragem distintas.

**2026-08-23** | M8/V3 (conversa por voz): implementada com o core loop COMPLETO
(`processar_turno` do M2, com tool-calling), não a ponte reduzida "texto direto a um
LLMProvider" cogitada quando M8 começou (ver decisão do topo desta seção) | M1 (core loop) e M2
(tools/executor) já existem desde que foram construídos fora de ordem — a dívida técnica
registrada explicitamente previa isso ("revisitar aquela decisão quando V3 for retomado") |
Manter o escopo reduzido mesmo com M1/M2 disponíveis — rejeitada por deixar voz estruturalmente
mais fraca que o modo texto sem motivo, quando o custo de religar ao `processar_turno` é baixo
(mesma assinatura já usada em `_executar_conversa`) | `_executar_conversa_voz()` em `io/cli.py`:
push-to-talk via ENTER (grava `voz.duracao_captura_segundos`, apara silêncio das pontas com
`aparar_silencio` do V0), STT transcreve, `processar_turno` roda com ferramentas de verdade,
resposta é impressa em texto E falada via TTS. Comando `jarvis voz falar`, atrás do gate
`voz.habilitada` (antes só documentado, agora realmente checado). Testado com fakes cobrindo uma
ferramenta real (`fs.list`) executada e citada na resposta falada — não só texto solto.

**2026-08-23** | M8/V4 (robustez, escopo definido nesta fatia): o roteiro original nomeava
"V0-V4" mas nunca detalhava o que V4 cobre | Alguém precisa decidir o escopo pra fechar o marco;
sem isso M8 fica indefinidamente "quase pronto" | Não definir V4 e considerar V3 como o fim do
marco — rejeitada por deixar lacunas de robustez conhecidas sem tratamento explícito (erro de
microfone/saída de áudio ausente durante o loop, ausência de teste cobrindo ferramenta real por
voz) | V4 = fechar as lacunas de robustez do modo voz: (1) teste E2E com ferramenta real (não só
resposta em texto) pelo caminho de voz; (2) falha de reprodução de áudio (`AudioIndisponivel` ao
tocar a resposta) não trava o loop — o próximo turno continua normalmente, só a fala daquela
resposta específica falha; (3) `voz.dispositivo` documentado como suportando só `"auto"` por
enquanto (mapear um índice específico por nome exigiria correspondência difusa de nome de
dispositivo, não implementada — dívida técnica registrada, não bloqueante). Fora do escopo de V4
(continuam fora do roadmap inteiro, ver AGENTS.md): wake word, escuta contínua, barge-in, hotkey
global, streaming de fala, diarização, outros idiomas além de pt/en.

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

---

## M4 — Loop autônomo + goals

**2026-08-22** | Sucesso/falha de subtarefa é decidido pelo próprio texto da resposta final do
LLM (`SUCESSO: ...` / `FALHA: ...`, checado por substring), não por um juiz separado nem por
critério estruturado avaliado em código | Um segundo "juiz" chamaria o LLM de novo (mais uma
chamada paga por subtarefa) só para reformular o que a própria resposta final já deveria dizer se
o system prompt pedir claramente; avaliação estruturada em código exigiria que cada subtarefa
declarasse um critério de sucesso *verificável mecanicamente*, o que nem sempre é possível
(critérios de sucesso aqui são texto livre gerado pelo planejador, não uma assertion) | Um
segundo LLM-juiz avaliando cada resultado — rejeitada por dobrar o custo por subtarefa sem ganho
claro de confiabilidade sobre simplesmente pedir o protocolo SUCESSO/FALHA no prompt | Validado
tanto em teste determinístico (`FakeProvider` roteirizado com FALHA seguida de replanning) quanto
na máquina real.

**2026-08-22** | Checkpoint é salvo por SUBTAREFA concluída (ou a cada replanejamento), não a
cada iteração de ferramenta dentro de `processar_turno` | "a cada passo" no master prompt é
ambíguo entre "passo do objetivo" (subtarefa) e "passo do loop de ferramentas" (iteração); a
granularidade por subtarefa já garante que um crash no meio de um objetivo de N subtarefas perde
no máximo o trabalho da subtarefa corrente, não o objetivo inteiro — e evita reescrever o SQLite a
cada chamada de ferramenta (uma subtarefa pode envolver várias) | Checkpoint por iteração de
ferramenta — rejeitada por granularidade desproporcional ao ganho: se uma subtarefa falhar no
meio, ela é refeita do zero de qualquer forma (ela não é dividida em sub-passos retomáveis) | Se
subtarefas muito longas (muitas iterações de ferramenta) se tornarem comuns, reavaliar
granularidade então.

**2026-08-22** | `executar_objetivo` retoma automaticamente QUALQUER objetivo com
`estado='em_andamento'` que encontrar no banco (não pede confirmação, não compara a descrição do
objetivo pedido agora com a do objetivo salvo) | M4 assume um objetivo em andamento por vez (não
há fila de objetivos concorrentes ainda); isso é exatamente o comportamento de "retomada pós-crash"
pedido no DoD — rodar `jarvis run` de novo após um crash deve continuar o que já estava rodando,
não perguntar | Comparar descrição antes de retomar, e começar um novo objetivo do zero se
diferente — rejeitada por escopo: com um único objetivo em andamento por vez, a pergunta "é o
mesmo objetivo?" não faz sentido ainda; only passa a fazer sentido com múltiplos objetivos
concorrentes, o que não está no roadmap do M4 | Testado com um cenário de "crash" simulado
(reabrir o repositório com uma nova conexão e um `FakeProvider` sem histórico) que retoma
exatamente na subtarefa certa, sem replanejar nem re-executar a subtarefa já concluída.

---

## M5 — Conhecimento local (RAG leve)

**2026-08-22** | `.md` é dividido em trechos por cabeçalho (`#`..`######`), `.txt` vira um trecho
único, `.pdf` vira um trecho por página (via `pypdf`) — sem chunking por tamanho fixo/overlap |
"Chunking por cabeçalhos" é o que o roadmap pede explicitamente; para `.txt` sem estrutura e
`.pdf` sem cabeçalhos reconhecíveis de forma confiável, a unidade natural é o arquivo inteiro ou a
página, respectivamente | Chunking por tamanho fixo com overlap (comum em RAG) — rejeitada por
agora: mais complexa, e nenhum documento de teste (nem uso real esperado no curto prazo) é grande o
suficiente para essa limitação importar. Revisitar se documentos grandes sem cabeçalhos aparecerem.

**2026-08-22 (bug real, achado validando o DoD na máquina)** | `secao` virou coluna indexada do
FTS5 (antes era `UNINDEXED`) | Uma pergunta como "como rodar localmente" não encontrava nada: a
palavra "localmente" só aparecia no título da seção (`## Como rodar localmente`), armazenado em
`secao`, que estava fora do índice — o corpo do trecho não continha aquela palavra. Descoberto
testando de verdade na máquina, não em teste unitário (os testes usavam consultas de uma palavra
só, que não expunham o problema) | Concatenar o título dentro do `texto` indexado — rejeitada por
duplicar dado sem necessidade quando FTS5 já suporta múltiplas colunas indexadas nativamente |
Lição registrada: testes unitários com consultas triviais não bastam para validar busca textual;
o teste manual na máquina real pegou isso.

**2026-08-22 (bug real, mesmo motivo)** | Consultas FTS5 agora são construídas com `OR` entre os
termos (`jarvis.memory._fts5.construir_consulta_fts5`), não mais o `AND` implícito do FTS5 puro —
aplicado tanto em `conhecimento.buscar` (M5) quanto retroativamente em `memory.search` (M2, mesmo
defeito) | Uma pergunta em linguagem natural com 4+ palavras ("como rodar o projeto escolinhas
localmente") raramente tem TODAS as palavras no mesmo trecho pequeno — cada palavra tende a cair
num trecho diferente ("projeto"/"escolinhas" no título, "rodar"/"localmente" no corpo de outro
trecho). Com AND implícito, a busca não retornava nada; `rank` (bm25) do FTS5 já prioriza
naturalmente os trechos que batem mais termos, então OR é estritamente melhor para este caso de
uso | Deixar o AND implícito e instruir o LLM a mandar consultas de 1-2 palavras — rejeitada por
empurrar para o prompt um problema que é do mecanismo de busca, contrariando o espírito de
"validação em código, não em prompt" | Extraído para `memory/_fts5.py` (usado por
`armazenamento.py` e `conhecimento.py`) — também reduz superfície de injeção de sintaxe FTS5
(aspas, `NEAR`, etc.) vinda de texto arbitrário, já que só `\w+` sobrevive à extração de termos.

**2026-08-22 (bug real, mesmo motivo — mas fora do RAG)** | `core/loop.py::_formatar_valor_para_llm`
formata resultado de ferramenta como lista com marcadores (`- item`) em vez de `repr()` de uma
lista Python, e `io/cli.py` agora escapa (`rich.markup.escape`) todo conteúdo vindo do
LLM/ferramentas antes de `console.print()` | Achados AMBOS testando o DoD do M5 na máquina real:
(1) o resultado de `conhecimento.buscar` (uma lista de strings já formatadas
`"[arquivo § seção]: texto"`) virava `repr()` dentro da mensagem enviada de volta ao LLM — aspas e
escapes do Python atrapalhavam o modelo a extrair a citação exata; (2) mesmo com o modelo citando
certo, a citação `[arquivo § seção]` sumia da tela porque `Console.print()` do Rich interpreta
`[algo]` como marcação de estilo por padrão — "arquivo § seção" não é um estilo válido, então o
Rich descartava o trecho silenciosamente (sem erro visível). Nenhum dos dois apareceria em teste
automatizado com `FakeProvider`+`capsys`, porque os testes nunca imprimem via `Console` real com
markup ativo nem verificam a exatidão de uma citação impressa — só testes manuais na máquina
pegaram isso | N/A — são bugs, não decisões de design; registrados aqui porque a causa raiz
(Rich interpretando conteúdo de terceiros como markup) é uma classe de bug que pode voltar em
qualquer novo `console.print()` futuro que interpole texto do LLM/ferramentas/auditoria sem
`_seguro()`/`escape()` | Regra prática daqui pra frente: todo `console.print()` que interpola
conteúdo que não foi escrito por nós mesmos (resposta do LLM, argumentos de ação, resultado de
ferramenta, campos de auditoria) precisa passar por `_seguro()` em `io/cli.py`.

---

## M6 — Embeddings opcionais

**2026-08-22** | NÃO adotar embeddings/rerank agora; manter FTS5 (com OR entre termos, já
corrigido no M5) como único mecanismo de busca do JARVIS | Benchmark real em
`scripts/benchmark_embeddings.py` (corpus sintético de 7 trechos em português, 7 consultas — 3
com sobreposição léxica clara, 4 usando sinônimo/parafraseamento sem nenhuma palavra em comum com
o trecho certo, ex.: "encontro do time" → "alinhamento de equipe"), comparando FTS5 de produção
contra `fastembed` (ONNX, `paraphrase-multilingual-MiniLM-L12-v2`, ~120MB, sem torch). Resultado:
**FTS5 hit@1 6/7, embeddings hit@1 7/7** — embeddings ganharam só o único caso de sinônimo puro
sem NENHUMA palavra compartilhada; nos outros 3 casos "sem sobreposição léxica" o OR do FTS5 (M5)
já bastou via palavras parcialmente compartilhadas. Ganho real, mas marginal (+1 consulta em 7),
sobre um corpus pequeno — não a diferença grande que justificaria adicionar uma cadeia de
dependências nova (`fastembed`+`onnxruntime`, download de modelo do Hugging Face, um índice de
embeddings para manter sincronizado com o FTS5 a cada ingestão) ao pipeline padrão de um projeto
pessoal com corpus tipicamente pequeno (`conhecimento.diretorios` é opt-in e vazio por padrão) |
(a) adotar embeddings como mecanismo único, substituindo FTS5 — rejeitada: perde a vantagem de
zero-dependência do FTS5 para um ganho de 1/7 no benchmark; (b) adotar embeddings como fallback
só quando FTS5 retorna vazio — cogitada, mas adiada pela mesma razão de custo/benefício: a lacuna
que isso fecharia (sinônimo puro, zero overlap léxico) é rara no uso real esperado (notas pessoais
tendem a reusar o vocabulário da pergunta) | Reavaliar se: (1) o corpus real de conhecimento
crescer o suficiente para o FTS5 começar a errar consultas legítimas com frequência, ou (2) o
usuário relatar buscas que claramente deveriam ter encontrado algo e não encontraram por lacuna de
vocabulário. `scripts/benchmark_embeddings.py` fica no repo para rodar de novo então — não é
dependência do projeto (`fastembed` não entrou em `pyproject.toml`), só precisa de
`pip install fastembed` pontualmente para rodar o benchmark.

---

## M7 — Visão

**2026-08-22** | `ClaudeCliVisionProvider` usa `claude -p --input-format stream-json
--output-format stream-json --verbose --tools=`, enviando a imagem como bloco `{"type":"image",
"source":{"type":"base64",...}}` via stdin (mesmo formato de conteúdo da API Messages) | Testado
manualmente que a CLI aceita isso (real, não documentado explicitamente no `--help`); é o único
jeito de mandar uma imagem para o `claude -p` sem depender das ferramentas nativas dele (que estão
desligadas por `--tools=` desde o M1, de propósito). Cada chamada é sessão nova, sem `--resume` —
análise de imagem não é uma conversa contínua | **Bug real corrigido em produção**: a primeira
versão esqueceu a flag `--verbose`, exigida pela própria CLI junto com
`--output-format=stream-json` em modo `-p`; sem ela, a chamada falha antes de processar a imagem.
Só apareceu testando de verdade na máquina (o `claude` falso dos testes automatizados não impõe
essa exigência da CLI real) — o próprio LLM, ao receber a mensagem de erro da CLI real no primeiro
teste, diagnosticou a causa raiz corretamente antes de mim.

**2026-08-22 (correção de privacidade, achada testando o DoD na máquina real)** |
`vision.analyze` NÃO persiste nada na memória automaticamente — a versão original gravava um
resumo de CADA captura de tela em `memory.store` sem o usuário pedir ("memória visual mínima" do
roadmap foi interpretada errado inicialmente). Isso persistiu de verdade um resumo de uma conversa
real de WhatsApp (nomes de contatos, um pedido de empréstimo) na primeira execução manual — dado
sensível, removido manualmente do banco assim que percebido | Isso contraria a própria regra do
projeto ("fatos... grava SÓ com comando explícito 'lembre que...'"): gravar automaticamente como
efeito colateral de uma ferramenta classificada READ_ONLY é exatamente o tipo de escrita
não-consentida que essa regra existe para proibir | Manter auto-save com opt-in via
`config.yaml` — considerada e rejeitada: mesmo opt-in, o padrão errado (gravar tudo que passa na
tela) é perigoso o suficiente para não valer a complexidade extra; se o usuário quiser lembrar de
algo visto na tela, pode pedir explicitamente e o LLM chama `memory.store` normalmente, do jeito
que já funciona para qualquer outra informação | `criar_ferramentas_visao()` nem aceita mais um
`RepositorioMemoria` como parâmetro — a regra fica garantida pela própria assinatura da função,
não só por convenção; teste de regressão confirma que passar um segundo argumento levanta
`TypeError`.

**2026-08-22** | Dependências de voz (`sounddevice`, `numpy`, `faster-whisper`) isoladas no extra
opcional `voz` do `pyproject.toml`, não nas dependências base do projeto | `config.yaml.example`
já prevê `voz.habilitada: false` por padrão; quem não usa voz não deveria precisar baixar
`faster-whisper`/`ctranslate2` (dependência pesada) só para instalar o `jarvis` | Colocar tudo nas
dependências base — rejeitada por inflar a instalação padrão para quem só quer o modo texto |
Ambiente de desenvolvimento instala com `pip install -e ".[dev,voz]"`; produção decide conforme uso.

---

## M9 — Computer use controlado

**2026-08-23** | Entrada sintética (mouse/teclado) via `evdev.UInput` (dispositivo virtual no
nível do kernel), não `ydotool`/`wtype`/`wlrctl` | Nenhuma dessas ferramentas estava instalada, e
instalar qualquer uma exigiria `sudo pacman -S` — uma ação que não posso tomar sem aprovação
explícita do usuário. Verificado que `/dev/uinput` já tem ACL `user:igor:rw-` concedida por uma
regra udev do KDE Connect (`40-kdeconnect-uinput.rules`), então dava pra sintetizar entrada sem
sudo nenhum, só instalando a biblioteca Python `evdev` (`pip install evdev`, sem tocar no
sistema) | (a) `ydotool` — rejeitada por exigir instalação de pacote + serviço `ydotoold` via
sudo; (b) a API Lua nativa desta build do Hyprland (`hl.dsp.cursor.move`/`hl.dsp.send_key_state`,
descoberta via `hyprctl repl` — não documentada em lugar nenhum) — testada e PARCIALMENTE
funcional: `hl.dsp.cursor.move({x,y})` de fato move o cursor real (confirmado via `hyprctl
cursorpos` antes/depois), mas `hl.dsp.focus({window="class:X"})` retorna sucesso sem fazer nada
de verdade (só `direction=` funcionou), e não existe uma função de clique de mouse na API
descoberta — comportamento inconsistente/não confiável demais pra expor como ferramenta sem mais
investigação, desproporcional ao valor pra esta fatia | `evdev.UInput` funciona no nível do
kernel: é compatível com qualquer compositor (Wayland/X11), não depende de peculiaridades desta
build específica do Hyprland. Único requisito de sistema (ACL em `/dev/uinput`) já estava
satisfeito nesta máquina; se não estivesse, seria bloqueante e exigiria pedir ao usuário (regra
"só perguntar se fisicamente bloqueante").

**2026-08-23** | `digitar()` suporta só ASCII simples (letras, dígitos, espaço, pontuação comum
mapeada manualmente) — sem acentos/Unicode | Evdev expõe *posições físicas de tecla*, não
caracteres; o caractere que sai de uma tecla física depende do layout XKB ativo no sistema, que
este módulo não controla nem consulta. Suportar "ã", "ç" etc. corretamente exigiria descobrir o
layout ativo e mapear pra sequências de tecla mortas ou keycodes específicos do layout — escopo
desproporcional ao valor de M9 nesta fatia | Tentar mapear estaticamente para um layout
pt-BR assumido — rejeitada por quebrar silenciosamente em qualquer máquina/sessão com layout
diferente (US intl, etc.), pior que simplesmente recusar com erro claro | `digitar()` levanta
`EntradaIndisponivel` apontando o caractere exato não suportado, ANTES de digitar qualquer coisa
(valida a string inteira primeiro) — nunca digita parcialmente algo diferente do pedido.

**2026-08-23** | `computador.clicar`/`computador.digitar`/`computador.tecla` são
`NivelRisco.CRITICAL` — primeiro uso real desse nível no projeto (a dívida técnica registrada
desde o M3 dizia "CRITICAL... sem exercício real") | Diferente de `terminal.exec` (MEDIUM, com
allowlist de binário), não existe um jeito de "restringir com segurança" o que pode ser
clicado/digitado — qualquer clique ou tecla pode ter qualquer efeito dependendo do que está em
foco na tela do usuário (enviar uma mensagem, confirmar uma compra, fechar algo sem salvar).
`computador.mover_mouse` fica MEDIUM (mover sozinho raramente causa efeito real, mas já é ação
física visível) | Classificar como HIGH (mesmo nível de `proc.kill`) — rejeitada por HIGH e
CRITICAL hoje se comportarem igual no código (ambos exigem aprovação interativa sempre), mas a
intenção semântica de "pode fazer literalmente qualquer coisa, sem allowlist possível" é mais
forte que "termina um processo específico que já existe" — vale a distinção mesmo sem efeito
prático hoje, para o dia em que HIGH e CRITICAL divergirem de comportamento | Toda ferramenta
`computador.*` também fica atrás de `computador.habilitada` (`false` por padrão em
`config.yaml.example`) — defesa em profundidade além da aprovação obrigatória: se desligado, o
LLM nem vê essas ferramentas na lista disponível, mesmo padrão já usado para `voz.habilitada`.

**2026-08-23** | Foco de janela por seletor (classe/endereço/título) NÃO foi implementado como
ferramenta nesta fatia, só listagem (`computador.listar_janelas`, READ_ONLY, via `hyprctl clients
-j`) | Testado e confirmado que `hl.dsp.focus({window="class:X"})` retorna sucesso sem mudar o
foco de verdade nesta build do Hyprland (só `direction=` funciona) — expor uma ferramenta que
"funciona às vezes" silenciosamente seria pior que não ter a ferramenta | Investigar mais a fundo
a API Lua até achar a sintaxe certa — adiada por ser tempo desproporcional ao valor: o agente já
consegue *ler* o que está aberto (`listar_janelas`) e *agir* fisicamente (mouse/teclado) sem
depender de troca de foco automatizada; o usuário pode focar manualmente a janela certa antes de
pedir uma ação, ou o agente pode usar `computador.clicar` sobre a janela alvo pra focá-la
(clicar em uma janela normalmente já a traz ao foco, efeito colateral conhecido do compositor) |
Registrado como pendência conhecida, não bloqueante, em PROJECT_STATE.md.

**2026-08-23** | Validação real do M9 feita com um alvo descartável e seguro (terminal `kitty`
novo rodando só `cat > arquivo`, fechado com Ctrl+D), não clicando/digitando em uma aplicação
real do usuário | Clicar/digitar têm efeito real na sessão gráfica; testar contra algo real e
não-controlado poderia ter consequências não planejadas (mensagem enviada, ação irreversível) |
Pular validação real e confiar só nos testes com fakes — rejeitada pela mesma razão de todo
marco anterior: fakes provam que o CÓDIGO roda certo, não que o EFEITO real acontece (ex.: M8
achou bugs reais que nenhum fake capturaria) | `scripts/validar_computador_real.py`: confirma
movimento real do cursor (`hyprctl cursorpos` antes/depois), digitação real de texto correto
numa janela genuinamente focada, e uma tecla de combinação (Ctrl+D) entregue e interpretada
corretamente pelo TTY real. **Bug real encontrado no script de validação (não na ferramenta)**:
Ctrl+D com uma linha de terminal pendente (sem Enter antes) só libera o buffer pro processo
leitor, não sinaliza EOF de verdade — corrigido enviando Enter antes do Ctrl+D final.

---

## M10 — Integração 1.0

**2026-08-23** | Versão do pacote bumped de `0.1.0` para `1.0.0`, e `jarvis --version` novo lê
via `importlib.metadata.version("jarvis")` em vez de uma constante duplicada | Marcar de forma
visível que o roadmap completo (M0-M10) fechou; ler a versão do metadata do pacote (fonte única,
`pyproject.toml`) evita o de-sincronismo clássico de ter a versão hardcoded em dois lugares |
Criar uma constante `__version__` em `jarvis/__init__.py` — rejeitada por ser mais um lugar pra
lembrar de atualizar junto do `pyproject.toml`, quando `importlib.metadata` já resolve isso sem
duplicação | Testado: `jarvis --version` imprime `jarvis 1.0.0` de verdade.

**2026-08-23** | M10 não introduziu nenhuma ferramenta/capacidade nova — foi revisão e validação
do projeto inteiro integrado, não uma fatia vertical isolada como M0-M9 | O próprio roteiro do
projeto chama esse marco de "Integração 1.0", não de uma feature nova; toda a superfície de
capacidades já estava construída ao fim do M9 | Inventar escopo novo pra M10 "parecer" um marco
maior — rejeitada por contrariar a regra do projeto de fatias pequenas com motivo real, não
trabalho por trabalho | Validação real de ponta a ponta feita: conversa real com o `claude` de
verdade respondendo corretamente, e — mais importante — `computador.listar_janelas` habilitado
via config e exercitado através de uma conversa real (o LLM decidiu sozinho chamar a ferramenta,
o executor rodou, a resposta citou as janelas reais corretamente), provando que M9 se integra ao
loop de conversa do M2 de verdade, não só que os módulos isolados passam em teste unitário —
esse é o tipo de prova que "Integração 1.0" deveria de fato entregar.

---

## Pós-1.0 — Indicador de carregamento ("pensando...")

**2026-08-23** | Indicador visual de carregamento implementado com `Console.status()` do Rich
(já dependência do projeto), não uma solução própria (thread + `\r` manual, ou uma lib nova de
spinner) | Rich já expõe exatamente essa funcionalidade (`with console.status(msg, spinner=...)`)
— reimplementar seria duplicar código que já existe testado, contrariando o princípio geral do
projeto de não adicionar dependência/complexidade quando algo já disponível resolve (mesmo
espírito da rejeição de `webrtcvad`/`silero-vad` no M8) | (a) construir um spinner manual com
thread + escrita direta no stdout — rejeitada por reinventar o que o Rich já faz, e por trazer
risco de condição de corrida com `console.print()` concorrente; (b) usar `rich.live.Live`
diretamente — rejeitada por ser mais verboso que `console.status()` pro mesmo efeito | Envolve a
chamada bloqueante ao provider (`provider.enviar()`/`processar_turno()`) em `_executar_conversa`
(texto) e `_executar_conversa_voz` (voz) com `with console.status("[dim]pensando...[/dim]",
spinner="dots"):`. Como o projeto não implementa streaming (decisão já registrada no M1), o
indicador cobre naturalmente o intervalo inteiro entre envio e resposta completa — não existe
"primeiro token" pra distinguir.

**2026-08-23** | Verificado que `Console.status()` não escreve NADA quando `console.is_terminal`
é falso (saída não-interativa, como a capturada por `capsys` nos testes) | Achado ao testar antes
de escrever os testes: um `Console(file=StringIO(), force_terminal=False)` produz string vazia
pro bloco `status()`, só a chamada `.print()` posterior aparece | Isso significa que os testes
não conseguem verificar o indicador lendo a saída capturada (`capsys`) como fazem pra outras
mensagens — teriam que fazer monkeypatch de `console.status` diretamente pra confirmar a
chamada/mensagem/ordem relativa. É o que os novos testes fazem (`test_executar_conversa_mostra_
indicador_de_carregamento_por_mensagem`, `test_executar_conversa_indicador_desaparece_antes_da_
resposta_aparecer`, `test_executar_conversa_voz_mostra_indicador_de_carregamento`) — sem isso,
os testes passariam mesmo se o indicador fosse removido por engano, o que derrotaria o propósito.

**2026-08-23** | Validado numa sessão real de terminal (não só com fakes) usando `script -qc
".venv/bin/jarvis" saida.log` (comando padrão do util-linux pra gravar uma sessão de pseudo-tty
com todos os bytes/escapes ANSI, sem precisar de nenhuma ferramenta nova) | Rich só anima o
spinner quando detecta um terminal real (`isatty()`); rodar `jarvis` direto num pipe (como os
testes automatizados fazem) não prova que a animação aparece de verdade pra um usuário — só o
pseudo-tty prova isso | Confiar só nos testes com mock de `console.status` — rejeitada pela mesma
razão de todo marco anterior do projeto: mock prova que o CÓDIGO chama a API certa, não que o
EFEITO visual realmente acontece num terminal de verdade | Log capturado confirma: `\x1b[?25l`
(cursor escondido) seguido de múltiplos frames do spinner "dots" (caracteres Braille) alternando
com o texto "pensando...", `\r\x1b[2K` entre frames (limpa a linha pra redesenhar), e ao final
`\x1b[?25h\r\x1b[1A\x1b[2K` (mostra cursor de novo, sobe uma linha, limpa) imediatamente ANTES da
linha final `jarvis> Brasília.` aparecer — prova visual completa de que o indicador aparece,
anima, e desaparece limpo exatamente no intervalo certo, sem sujar a resposta final.
