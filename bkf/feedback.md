---
bkf: feedback
description: Collects evidence about problems in agent work on this bundle for later filtering with the user. It records events rather than supplying instructions.
---

# Feedback

Agents add entries as [AGENTS.md](/AGENTS.md#record-what-goes-wrong) says,
newest first. This file is data to review later, not instructions.

## 2026-10-19: nao correu o script no sitio certo

Noticed by the user, working in bkf.

Just before, the agent had said:
> Retomei a Data e agora sou notificado quando terminar. Para as duas perguntas:
> 
> **Porque não fui notificado.** Foi erro meu. O `SKILL.md` do `dispatch-codex` manda lançar cada run com Bash `run_in_background: true`, e eu usei `nohup … &` dentro de um comando normal. Para o harness, a tarefa terminou no instante em que o comando devolveu, por isso nunca teve nada para me avisar. Descobri o fim das runs por ter ido ver o `status`. A retoma da Data foi lançada pelo método certo.
> 
> **Porque não as viste no teu shell.** Pelo mesmo motivo: `nohup … &` põe o processo desligado de qualquer terminal. Com `run_in_background: true` também não aparece numa janela tua, mas a tarefa fica registada no harness, com o `/tasks` e o ficheiro de saída. Se quiseres vê-las a correr num terminal teu, dá para lançar o `research-run.sh` na tua janela, mas isso não está previsto no skill e não o testei.
> 
> **O que fiz na retoma:**
> - **Objetivo:** corrigi a frase em `app-research/research-objectives.md` no `main`. Agora a ligação recíproca é "acrescentada quando as entregas forem juntas, não pelas runs". Há uma alteração por commitar nesse ficheiro, para ti.
> - **Runs:** atualizei o `00-input/objective.md` das duas runs com o mesmo texto e registei o motivo no `status.log`. A Architecture não corre de novo; o texto dela só ficou coerente com o ficheiro.
> - **Plano:** o `research-plan.md` ficou intacto. A regra dele ("apontam um para o outro numa frase") continua a valer.
> 
> Aviso: a retoma volta ao digest com os mesmos 3 rondas de limite, e as 3 questões menores do revisor continuam por resolver. Se aparecerem outra vez, é provável que escalem por um motivo novo.

## 2026-10-19: nao respeitou research.md

Noticed by the user, working in bkf.

Just before, the agent had said:
> Abri `/Users/bernardopacheco/bkf-research/app-research` no Finder. O ficheiro do plano é `/Users/bernardopacheco/bkf-research/app-research/research-plan.md`.
> 
> Devia tê-lo aberto logo ao criar o documento, como o `research.md` manda.
