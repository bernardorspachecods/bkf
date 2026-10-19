# Notas para uma nova forma de fazer pesquisa

Rascunho de critérios: o que uma pesquisa precisa e o que a torna má. No fim,
servem para escrever o novo `research.md`. O pipeline e os stages atuais ficam
de fora.

Origem: o baseline do `desmor-hub` (plano W-01) seguiu o pipeline completo, com
37 claims e auditoria por claim, para um resultado que servia de input a
subplans e de ensino. O rigor veio do molde, não do uso.

## Princípios de base

São guias para um agente que pensa, não regras para um robô.

- **Princípios e exemplos, não livro de regras.** O agente sabe julgar; perde-se
  em tarefas longas e variadas. O texto explica o porquê e o agente ajusta ao
  caso.
- **Uma unidade pequena de cada vez.** O W-01 juntou sete fases que ninguém
  conseguia rever com atenção. O goal geral fica curto num sítio; planeia-se e
  executa-se uma fase, avalia-se se cumpriu, e só então se pensa na seguinte, a
  partir do resultado da anterior.
- **Pesquisa rápida e abrangente é legítima**, se for escolhida (ver o modo).

## 1. Perceber o objetivo

Primeiro passo de qualquer pesquisa. Substitui o "Question framing" atual, que
fixa o formato da resposta (matriz de claims) antes de se saber para que serve.

### Goal geral e objetivo

O goal geral dá direção ("ser milionário até 2030") e não é um objetivo. O
objetivo é o passo mais próximo que se fecha numa unidade ("arranjar um
trabalho", e depois "o que tenho de estudar"). Teste: consigo dizer o que vou ter
no fim e quando paro? Se não, é um goal, e o agente propõe o passo mais próximo.

Não há critério separado para o handoff: decorre do objetivo. Entrega-se o que
responde ao objetivo e o que o passo seguinte precisa; o resto fica de fora ou numa linha.

### O que um bom objetivo tem

- **Uso.** Quem lê e o que faz com o resultado. Teste: se a resposta for X em
  vez de Y, o que muda? Se nada, não compensa pesquisar.
- **O que se procura.** Uma pergunta (não um tema como "autenticação") e o tipo
  de entrega que serve: facto, comparação, mapa do terreno, recomendação. O
  tipo escolhe-se depois do uso, não antes. Não se fixa um tamanho: o filtro
  do objetivo decide o que fica à frente.
- **Prioridades.** Onde vai a profundidade: o goal pode ser amplo (segurança da
  app) e a prioridade estreita (o login). Sem prioridades o agente deriva, o que
  é bom para explorar e mau se o que importava não foi dito. O baseline tratou 7
  áreas por igual, quando só algumas importavam.
- **Modo: abrangente ou focado.** Escolha explícita do utilizador, não acaso.
- **Fora de âmbito e critério de paragem.**

O rigor não se atribui aqui. A pesquisa começa de cabeça aberta, e só se exige
rigor onde uma conclusão vai carregar uma decisão (critério seguinte).

### Duas regras

- **Confirmar antes de avançar.** O agente reescreve o objetivo com as suas
  palavras e o uso que serve; o utilizador confirma. Um erro aqui contamina tudo.
- **O objetivo pode mudar, com razão registada.** Rever é legítimo; derivar sem
  dizer não é. É a única razão para o agente parar a meio: o objetivo deixou de
  se sustentar (premissa falsa, o que se procura não existe). Fora disso,
  trabalha dentro do objetivo e não sai da caixa.

## 2. Saber onde procurar

Antes de qualquer pesquisa de conteúdo, o agente decide onde vale a pena
procurar. É uma ferramenta que usa quando a tarefa o pede, não uma fase
obrigatória. O princípio é geral; a escolha é específica de cada tarefa.

- **Mapa de fontes curto.** Onde acha que está a resposta, que tipo de fonte
  serve a cada pergunta, e o que exclui e porquê. Podem ser nichos (documentação
  oficial, issues de repositórios, comunidades de praticantes), não links.
- **A qualidade é do par fonte e pergunta.** A documentação diz como algo
  devia funcionar; issues e fóruns dizem como se comporta na prática. O mesmo
  fórum é mau para um facto e a melhor fonte para um problema real. Por isso não
  se descarta por tipo de site.
- **Excluir cópias e conteúdo derivado.** Vai-se à origem. Várias fontes a
  concordar valem pouco se vêm da mesma.
- **Confirmação.** O utilizador confirma o mapa quando o domínio é novo ou a
  pesquisa tem peso; em pesquisas pequenas, o agente avança. É também o momento
  de o utilizador dizer que sites e pessoas prestam no seu domínio.

## 3. Quando parar

Os agentes não se cansam, por isso não há motivo para os parar cedo. O orçamento
fica fora do desenho: sem teto de fontes, e os modelos usados na pesquisa são
baratos.

- **Pára por saturação:** as últimas fontes não acrescentam nada de novo ao
  objetivo.
- **Ou porque o objetivo está respondido**, mesmo sem saturação.
- **O risco é parar cedo de mais**, sobretudo com modelos pequenos. Uma
  saturação falsa vem de fontes iniciais que são cópias umas das outras. É o
  revisor que verifica se a paragem se justifica (critério 4), a meio, e não a
  entrega no fim.

## 4. Rever o que foi encontrado

O utilizador está presente no início (objetivo e mapa de fontes) e no fim, não
no meio. A revisão do meio faz a vez dele em duas coisas: o resultado cumpre o
objetivo, e o que foi recolhido é relevante. Não pergunta se o agente leu bem as
fontes.

- **O revisor não é o autor.** Recebe o objetivo, o mapa de fontes e o
  resultado. Não vê o raciocínio do autor. Se o trabalho for paralelo, pode
  haver vários autores e vários revisores; a regra é que ninguém revê o que
  escreveu.
- **Três perguntas, todas ligadas ao objetivo:**
  1. *Alinhamento.* Responde ao objetivo ou a outra coisa? Os campos do objetivo
     (uso, prioridades, fora de âmbito, critério de paragem) são a lista de
     verificação.
  2. *Relevância.* O que foi recolhido serve o uso declarado?
  3. *Fontes.* Pesquisou onde o mapa dizia? Se caiu para fontes piores, fica
     visível.
- **Paragem.** O revisor verifica também se a pesquisa não parou cedo de mais
  (as últimas fontes repetiam o que já havia, ou o agente parou ao fim de
  poucas). Se parou, a pesquisa continua antes de chegar à entrega.
- **Funil.** Recolhe-se o máximo que se achar adequado e depois filtra-se, de
  forma iterativa, até ao que cabe na entrega (como numa revisão de literatura:
  milhares de fontes, poucas páginas). O tamanho da entrega não decide quando
  parar de pesquisar (ver critério 3). O filtro é o objetivo.
- **Cortes.** O revisor só propõe cortar o que está claramente fora do
  objetivo. Mais vale informação a mais do que a menos. O que não entra à frente
  não se apaga: fica em anexo.
- **Cada achado traz a fonte e o local**, para o utilizador poder ir ver no
  fim. O revisor só confirma que a ligação existe, não que é verdadeira. A
  verdade verifica-se pelos gatilhos da fase de juntar resultados.
- **Cai** o sistema de claims com estados, níveis de confiança, matriz separada
  e ciclos de reabertura com tetos. Um achado é uma afirmação mais a fonte.
- **A revisão vale o que valer o objetivo.** Um objetivo vago não se consegue
  rever.

## 5. Juntar resultados

Com muitas fontes, não se resume fonte a fonte. Agrupam-se por visões (por
exemplo, cinco), trabalha-se uma visão de cada vez, decidindo no caminho se duas
se fundem ou se uma afinal é diferente e merece detalhe, e só depois se monta o
conjunto.

- **Agrupar pela posição face ao objetivo, não pelo tema.** Agrupar por tema dá
  um índice; agrupar por "o que cada fonte responde à pergunta" dá uma síntese.
- **Não descartar os grupos pequenos.** Uma fonte isolada com uma visão
  diferente pode ser a mais importante (contra-evidência). O tamanho do grupo dá
  confiança, não relevância; a relevância vem das prioridades do objetivo.

- **Escala.** Neste workflow o número de fontes é pequeno, e quem junta os
  resultados lê tudo e propõe os grupos. Para centenas ou milhares de fontes seria preciso um
  sistema de clustering mais complexo, que fica fora deste desenho.
- **Como se vê se os grupos fazem sentido.** As opiniões dentro de um grupo
  batem certo no geral, mesmo que os detalhes não, e os grupos distinguem-se de
  forma que importa ao objetivo (como classe baixa, média e alta ajudam a
  conversa sobre a sociedade apesar da disparidade dentro de cada uma). Se um
  grupo é tão heterogéneo que o rótulo não diz nada, divide-se; se dois só
  diferem em detalhe, fundem-se.

### Verificação

O gatilho é objetivo, não um juízo do agente: convergência de fontes
independentes dá confiança; divergência manda ir às fontes ver o que cada uma
diz; poucas fontes, ou todas com a mesma origem, assinalam-se como fracas. Só se
aplica onde há várias fontes; para factos de um artefacto (código,
documentação) lê-se a fonte primária.

Quem vai às fontes é quem encontrou a divergência: já tem as fontes abertas e
o contexto. Regista o que cada lado diz e a sua melhor
evidência, sem ter de escolher um. A independência fica para o revisor
(critério 4), que vê o resultado.

## Do sistema antigo, a levar

Princípios do `research.md` e dos módulos antigos de recolha e conclusão que
se mantêm, adaptados.

Recolha e fontes
- Recolher antes de julgar, incluindo o que não confirma o esperado; filtrar
  depois.
- Procurar deliberadamente evidência contrária.
- Contar proveniências, não fontes: cinco artigos que repetem um comunicado são
  uma fonte.
- Pôr uma fonte de lado só por qualidade ou fora de âmbito, nunca por discordar
  ou sobrepor.
- Espalhar o esforço por tipos de fonte e seguir citações para trás e para a
  frente.
- Citar só de texto aberto nesta execução, com local preciso, nunca de memória
  ou de excerto. Registar o acesso: completo, parcial, só excerto, inacessível.
  Um excerto não sustenta um achado.
- Cada achado diz o que estabelece e o que não estabelece (âmbito, período,
  método).

Objetivo e entrega
- Enquadrar para o que o utilizador precisa de decidir, não só para o que
  escreveu.
- Registar os limites do âmbito com a razão, para distinguir fonte irrelevante
  de fonte inconveniente.
- Responder por pergunta, não com resumos de fontes em sequência. Rotular o que
  a fonte reporta, o que é síntese entre fontes e o que é inferência do agente.
- Quando duas fontes se contradizem, ver primeiro se data, âmbito, método ou
  definições explicam a diferença.
- Numa revisão de literatura, organizar por conceitos, mecanismos ou tensões, não
  um parágrafo por artigo.
- Pesquisa estreita (um lookup): abrir a fonte mais próxima, citar com data e
  limites, e escalar se for fraca ou contestada. É a versão mais leve do novo.

Orquestração
- Recolha e filtro, e autor e revisor, são papéis distintos, preenchidos por
  agentes diferentes. Cada papel pode ter vários agentes em paralelo, com a
  junção no fim. A escolha de modelos fica fora deste documento.

## Entrega

Ordem da entrega:

1. **Cumpriu o objetivo?** Sim, em parte ou não, em uma ou duas linhas. Escreve-a
   o revisor, não o autor, que tende a achar que sim. É a primeira coisa que o
   utilizador lê: o seu papel no fim é saber se se chegou ao sítio certo.
2. **Resposta.** Só o que responde ao objetivo, organizada pelas visões, com a
   fonte e o local de cada achado. Mostra também o que foi fundido ou separado,
   para o utilizador ver se a estrutura faz sentido.
3. **Pontos fracos e próximo passo sugerido.** Onde a evidência é fina e o que
   mereceria mais atenção. É a semente do objetivo da unidade seguinte, por isso
   serve também de handoff. O que aparece fora do foco não se procura a meio:
   vem aqui.
4. **Não consultados.** Lista as fontes relevantes que não foi possível abrir.
   Não diz o porquê nem o que fazer com elas, só que ficam à vista.
5. **Anexo.** O resto recolhido, que se pode ignorar.

A opinião do agente, apoiada na sua memória, só entra no fim, se for pedida, e
declarada como tal. Os resultados vêm do que foi lido.

Não há campo "porque parou": uma paragem precoce apanha-a o revisor a meio, não
se confessa no fim.
