# Entrega: onde gastar modelo forte e reasoning alto (implementar vs rever)

## 1. A resposta

**Resumo.** Nenhuma das duas perguntas tem uma resposta universal. Q1 (modelo) tem uma resposta condicional apoiada por um estudo controlado. Q2 (reasoning effort) **não tem evidência** que a decida. Nenhum estudo compara a mesma verba gasta a implementar com a mesma verba gasta a rever.

### Q1: modelo mais forte a implementar ou a rever?

**Resposta condicional: depende de quão forte é o implementador.**

O único estudo controlado direto (Xiang et al., Claude Opus 4.7 vs Codex GPT-5.5, 116 problemas LiveCodeBench médios/difíceis, effort alto em tudo, uma passagem, sem executar testes):

| Configuração | Acerto | Custo extra vs implementador sozinho | Latência extra |
|---|---:|---:|---:|
| Codex sozinho | 71,6% | — | — |
| Codex + revisão Codex | 84,5% | $0,12/tarefa | 29 s |
| Codex + revisão Claude | 89,7% | $0,25/tarefa | 74 s |
| Claude sozinho | 91,4% | — | — |
| Claude + revisão Claude | 91,4% | $0,16/tarefa | ~50 s |
| Claude + revisão Codex | 82,8% | $0,16/tarefa | 32 s |

- Implementador **fraco** + revisor **forte**: ganho grande (+18 pontos). Foi aqui que o revisor forte compensou.
- Implementador **forte**: a revisão não ajudou (Claude a rever-se: 0) e um revisor mais fraco **piorou** (−8,6 pontos).
- **Limite grave:** os braços não reaproveitam o custo extra do revisor para implementar melhor. Por isso não responde à pergunta com orçamento igual. Fica por medir quanto renderiam esses $0,13 extra num implementador mais forte ou mais longo.

Evidência de apoio, mais fraca:
- Greptile (estudo do próprio vendor, 1000 PRs, só recall de bugs graves): o revisor de outro modelo apanhou mais que a auto-revisão nas duas direções (62,0% vs 50,5%; 60,0% vs 53,7%). Não é independente, não dá precisão nem custo.
- CriticGPT (OpenAI): críticos de LLM apanham bugs que humanos deixam passar, mas também alucinam bugs. A auto-correção sem informação externa é pouco clara.
- Zhou et al. (fora de código): o verificador discrimina pior à medida que o gerador melhora.

**Recomendação (condicional).** Se o implementador for relativamente fraco, a revisão independente com um modelo mais forte é um uso plausível e de bom retorno. Se o implementador já for forte, não há evidência de que a revisão pague o custo. Não generalizes de problemas de competição para trabalho em repositório sem testar localmente.

### Q2: reasoning effort mais alto a implementar ou a rever?

**Sem evidência para decidir.** O estudo Claude/Codex usa effort alto em todos os papéis, por isso não testa effort alto num papel e baixo no outro.

O que existe, em fluxos separados que não são comparáveis entre si:
- **Rever, só revisor.** O IronBee (vendor, 50 PRs, 21 modelos) mostra retorno misto. Em 18 modelos com vários níveis de effort, 8 melhoraram F2 de forma significativa, 9 ficaram na mesma e 1 piorou. O recall subiu em 13 modelos e a precisão desceu em 11. O effort mais alto custou até 3,5× e demorou 3,5–18× mais. O Macroscope vê ganhos de score no GPT-6.1 Terra (76,1 → 82,3) a $0,18 → $0,57 por revisão.
- **Implementar, só gerador.** Gemini 2.5 (mais thinking tokens → mais acerto em LiveCodeBench, a mais custo) e estudos de compute em inferência (SWE-Reasoner, S*) apontam no mesmo sentido. São intervenções de sistema, não só subir o effort da API.
- **Aviso de orquestração.** Numa nota da Anthropic, o Sonnet 5.5 pontuou menos em Max do que em Xhigh em dois casos, porque o Max chamou mais um subagente de revisão. Isso causou timeout ou edições fora de âmbito. É um caso estreito, não prova que rever seja mau.

**Recomendação.** Nenhuma baseada em evidência. Qualquer regra "effort alto na revisão" ou "na implementação" é palpite até medires no teu fluxo.

### Transversal: o que limita o valor de uma revisão

- Um *finding* não é um bug apanhado. Falsos positivos têm custo: no CodeRabbit, 56,3% das sugestões foram rejeitadas e 36,4% aceites. Nenhuma métrica agregada é um falso-positivo limpo.
- Contexto e independência pesam tanto como o rótulo do modelo: a Anthropic recomenda um revisor "fresco", que não viu a conversa de implementação, a rever contra uma especificação escrita. Regras de repositório com âmbito definido subiram a recuperação de problemas de 58,3% para 98% (OpenAI), mas são resultados do próprio fornecedor.
- Várias revisões agregadas subiram o F1 até 43,67% (SWRBench, só o abstract), a mais custo de inferência.

**Divergências a ler com cuidado.** Claude a rever Codex ajuda e Codex a rever Claude prejudica (estudo controlado), enquanto o Greptile vê vantagem cruzada nas duas direções. Diferem em tarefa, métrica e independência da fonte. Não os faças média.

## 2. Pontos fracos e próximo passo

1. **Falta a comparação central a orçamento igual** (implementar mais forte/longo vs rever mais forte/longo, nas mesmas tarefas de repositório).
2. **Q2 está praticamente sem resposta direta.**
3. **O estudo direto é de uma passagem, sem testes.** Fluxos reais têm ferramentas, contexto, várias voltas e CI. O SWE-Review mostra que um ciclo gerar-rever-corrigir melhora a resolução, mas com modelos abertos e sem orçamento igual.
4. **Custos são locais a cada configuração**, e preços atuais ficaram fora de âmbito.
5. **Métricas não são intercambiáveis** (pass rate, recall, F2, aceitação, ação do autor). Há juízes LLM e amostras pequenas, e os relatos de praticantes são anedóticos.

**Próximo passo sugerido (objetivo da próxima unidade):** montar uma experiência local barata no teu próprio fluxo: mesmas tarefas, orçamento fixo, cruzando modelo e effort entre implementador e revisor, com contagem de bugs reais, falsos positivos e custo. É a única forma de fechar Q2 e de verificar Q1 em repositório.

## 3. Não consultado

- Post de engenharia "Claude Code Review" (Anthropic): não abriu.
- `navels/neal-swebench`: abertura expirou.
- Issues/changelog do Qodo e do CodeRabbit: não localizados ou não acessíveis (changelog do CodeRabbit não consultado à parte).
- Outros repositórios de frameworks que apareceram nas pesquisas: não abertos.
- Paper J-STAGE de custo vs deteção em orquestração (2026) e preprint CR-Bench-v2 (2026): apareceram na pesquisa, não foram abertos.
- Discussões do Reddit sobre emparelhamento de modelos; PDF do whitepaper do Qodo; paper completo do estudo CodeRabbit (só abstract).
- Preços de lista atuais, por âmbito.

## 4. Anexo

Material recolhido que pode ser ignorado (detalhe no digest): infraestrutura de benchmarks (ReviewBench, OpenHands, Factory: modelos mais caros nem sempre ganham, ex. GPT-5.2 60,5% a $1,25 vs Claude Opus 4.6 59,8% a $3,11 por PR), outros benchmarks de revisão (SWE-PRBench, 15–31% dos problemas humanos apanhados), SWE-Review (revisão agêntica 27,5% → 56,9% de resolução num modelo aberto), relatos de praticantes (hipóteses, não evidência) e o preprint do Iyengar sobre alocação de compute (resultado ligado a configuração; falsos positivos do verificador sobem com a capacidade do gerador).

**Nota de processo.** O digest escalou na revisão por 3 omissões só do anexo. Acrescentei-as à mão (Iyengar e Factory; o ponto do SWE-Review já lá estava), sem nova revisão. Estas conclusões vêm do que as fontes disseram. Não acrescentei opinião minha.
