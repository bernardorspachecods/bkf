# Sources migration map: software-factory F01-F14 to `~/sources`

Result of migrating the 14 sources of `~/software-factory/fontes.md` (F01-F14) into the store `~/sources` on 2026-11-19. This file is a hand-off: the session that organizes the library rewrites `fontes.md` from it without opening the records.

Records are at `~/sources/records/<id>/<id>.md`; the snapshot is `<id>.txt` beside it (git-ignored, absent where noted). Every record has `consulted: 2026-11-19` and `via: migration:software-factory`.

**Revision of `fontes.md` that "before" describes.** `~/software-factory` is not a Git repository, so there is no commit to name. "Before" is the current `fontes.md` (last modified 17:56 on 2026-11-19): the authors and `Publicada` values quoted as "before" below, with the qualifications it gives for F03, F10 and F11 transcribed exactly, are those of its rows F01-F14. The version of the file read on 2026-11-19 while the migration ran was earlier than that and differed in places; where a statement below is true only of that version, it says "the version read on 2026-11-19".

**Consultation dates.** In the current `fontes.md`, `Consultada` is `2026-11-19` for F03-F14, which is the `consulted` date of their records (F03-F14 were consulted that day, not on a lost earlier date). Only F01 and F02 have `data por confirmar` there; for them `consulted: 2026-11-19` is the migration's own date, and their earlier consultation date is unknown. The Notes of F03-F14 now say "Consulted on 2026-11-19 for ~/software-factory (F<nn>), per fontes.md."; those of F01 and F02 say the date was lost. (They first said "lost" for all 14, which was inaccurate for F03-F14.) `before` is the value in `fontes.md`; `after` is the value in the record. "Hand" marks a value set by hand from the page because the tool extracted a wrong one or none (listed under Tool defects).

## Map

| Fnn | New id | URL in the record | Author before | Author after | Published before | Published after | Status, kind |
|---|---|---|---|---|---|---|---|
| F01 | `tan-code-slop-except-mine` | https://ai.engineer/talks/O_zcc6Xl12g-all-code-is-slop-except-mine | Lauren Tan | Lauren Tan (hand; tool said `ai`) | por confirmar | `unknown` | used, talk |
| F02 | `ai-engineer-walden-yan` | https://ai.engineer/code/2026/talks/walden-yan | Walden, Cognition | Walden Yan (hand; tool said `ai`) | por confirmar | 2026-11-12 (hand): the date of the talk, not of the page; see the F02 row below | used, talk |
| F03 | `atlassian-ensure-design-token-usage` | https://atlassian.design/components/eslint-plugin-design-system/ensure-design-token-usage (`redirected_to`: its `/usage` page) | Atlassian | Atlassian (hand; tool said `atlassian`) | por confirmar (changelog visto na v16.16.0 do `@atlaskit/eslint-plugin-design-system`) | `unknown` | used, docs |
| F04 | `shopify-polaris-references` | https://polaris.shopify.com/tools/stylelint-polaris (the page fontes.md cited; `redirected_to`: https://shopify.dev/docs/api/polaris; no alias) | Shopify | Shopify | por confirmar | `unknown` | **discarded, `dead`**, docs |
| F05 | `sardesai-custom-eslint-ratcheting-notion` | https://www.notion.com/blog/how-we-evolved-our-code-notions-ratcheting-system-using-custom-eslint-rules | Notion | Ankit Sardesai, Jake Teton-Landis | por confirmar | 2025-03-03 | used, article |
| F06 | `teton-landis-eslint-seatbelt` | https://socket.dev/npm/package/eslint-seatbelt | autor da ferramenta interna da Notion (nome por confirmar) | Jake Teton-Landis (hand, from the npm registry metadata) | por confirmar | `unknown` | used, package |
| F07 | `craig-incrementally-adding-stylelint-rules` | https://dev.to/phenomnominal/incrementally-adding-stylelint-rules-with-betterer-1b5b (alias: the `www.dev.to` URL of fontes.md) | phenomnominal | Craig ☠️💀👻 (dev.to display name; `phenomnominal` is the username) | por confirmar | 2021-03-01 | used, article |
| F08 | `berge-playwright-visual-regression-testing` | https://argos-ci.com/blog/playwright-visual-regression-testing-ci | Argos | Greg Bergé (co-founder and CEO of Argos) | por confirmar | 2026-08-18 | used, article |
| F09 | `osmani-give-ai-eyes-introducing` | https://addyosmani.com/blog/devtools-mcp/ | Addy Osmani | Addy Osmani | por confirmar | 2025-09-25 | used, article |
| F10 | `vaughan-browser-loop-testing-playwright` | https://codex.danielvaughan.com/2026/04/24/browser-in-the-loop-testing-playwright-chrome-devtools-mcp-codex-cli/ | Daniel Vaughan | Daniel Vaughan | 2026-04-24 (lida no URL, por confirmar) | 2026-04-24 (stated on the page; also `updated: 2026-11-19`) | used, article |
| F11 | `storybook-mcp-server` | https://storybook.js.org/docs/ai/mcp/overview | Storybook | Storybook | por confirmar (os docs indicavam a v10.3, com a v10.4 em beta) | `unknown` | used, docs |
| F12 | `w3c-design-tokens-stable-specification` | https://www.w3.org/community/design-tokens/2025/10/28/design-tokens-specification-reaches-first-stable-version/ | W3C Design Tokens Community Group | Kaelig Deloumeau-Prigent (hand; tool said `w3`; the byline, co-chair of the group) | 2025-10-28 | 2025-10-28 | used, article |
| F13 | `ast-grep-lint-rule` | https://ast-grep.github.io/guide/project/lint-rule (the `.html` of fontes.md dropped by the site's canonical link) | ast-grep | ast-grep | por confirmar | `unknown` | used, docs |
| F14 | `imbue-ai-ratchets` | https://github.com/imbue-ai/ratchets (the URL the current fontes.md gives; confirmed: the repository exists) | imbue-ai | imbue-ai (hand; tool said `GitHub`) | por confirmar | `unknown` | used, repo |

## What differs from fontes.md that the rewrite must carry

| Fnn | Difference |
|---|---|
| F01 | Found: the AI Engineer site's reading edition of the talk (the video is on YouTube, id `O_zcc6Xl12g`); the speaker is at SpaceXSI (Grok Bot). The page shows no date; the conference, AI Engineer CODE 2026, ran 2026-11-10 to 2026-11-12. Verification is now `página lida` (snapshot), no longer `resumo`. |
| F02 | The real title is "A New Age of Software Engineering" by Walden Yan (cofounder and CPO of Cognition), AI Engineer CODE 2026, main stage. The talk date is 2026-11-12 (the page shows "November 12, 2026, Main stage"); the record's `published` holds that date. The snapshot gives no publication date of the page itself, so none is recorded: the 2026-11-12 is the talk's, not the page's. "Software Factory" is the concept the speaker names, not the title. Same reading edition with a machine transcript; video on YouTube (day 2 livestream, 2:33:30-2:47:07). `página lida`. |
| F03 | The registered page is a script redirect to `.../ensure-design-token-usage/usage`; the record keeps the registered URL in `url` and the `/usage` URL in `redirected_to` (no alias), and its snapshot is the server-rendered `/usage` page (`manual`). The page supports the claim in fontes.md (lint rule, tokens in place of hard-coded values, autofix). |
| F04 | **Not usable as cited.** The page redirects (HTTP 301) to the generic Polaris references page, so the Stylelint Polaris page is gone. The snapshot says nothing about Stylelint, rule categories or a coverage metric, so the claim of fontes.md ("Regras por categoria e métrica de cobertura do design system") has no source in the store. The record is closed `discarded` with reason `dead`. Its `url` is the page fontes.md cited (https://polaris.shopify.com/tools/stylelint-polaris) and `redirected_to` is https://shopify.dev/docs/api/polaris; the landing page is not an alias, because a redirect destination is not the same source. The snapshot is the text of that landing page. The consumer should drop the claim or find another source. The current `fontes.md` already records the 301 (`página lida`) and that the repository is archived (`subagente`) in the `Verificação` column of F04, but still lists F04 as used for that claim. |
| F05 | The page title is "How we evolve code: Notion's “ratcheting” system using custom ESLint rules" (published 2025-03-03). The page does **not** mention a frozen mode in CI; it says only that CI blocks a new error. "Frozen" is in the eslint-seatbelt README (F06). |
| F06 | The claims come from the README of the same package on the npm registry, because socket.dev answered HTTP 403; that README is its snapshot (`manual`). That README says it re-implements Notion's internal tool, tightens per file, and freezes state in CI. Author per the package metadata: Jake Teton-Landis (also a byline author of F05). |
| F07 | The page is a dev.to post of 2021-03-01 about Betterer v4.0.0. The registered URL is `dev.to/...`; `www.dev.to/...` is its alias. |
| F08 | The page is the Argos blog; its author is the co-founder and CEO of Argos, and its later sections promote Argos. The determinism practices (one Docker environment, platform-suffixed baselines, tolerances and masks, updating baselines) are in the first sections. |
| F09 | Published 2025-09-25, at the public preview of the tool; tool names and flags have changed since. |
| F10 | Page date 2026-04-24, "Updated November 19, 2026"; the author's site promotes a book. |
| F11 | The page is labelled a preview. Neither a date nor a version is on it; the "10.3, with 10.4 in beta" of fontes.md is not in the snapshot. |
| F12 | The page is a Community Group announcement of the stable specification 2025.10, not the specification text. It does **not** say that tokens are JSON with an explicit type: that part of the claim in fontes.md needs the specification itself (https://www.designtokens.org/tr/2025.10/). |
| F13 | No date on the page. |
| F14 | The version of `fontes.md` read on 2026-11-19 gave no URL for F14; the current one gives https://github.com/imbue-ai/ratchets, and it is confirmed: the repository exists ("Ratchets: Progressive lint enforcement for human and AI developers"; Rust, built with Cargo; 12 stars, 389 commits; credits the idea to qntm). No release date on the repository page. |

## Totals

- `published` of the 14: 12 read `por confirmar` in the current `fontes.md` (F01-F09, F11, F13, F14; F03 and F11 with the qualification given in their "before" cell). After: **4 became real publication dates** (F05, F07, F08, F09, all extracted by the tool) and **1 record holds a talk date** (F02, 2026-11-12, the main-stage date of the talk, read by hand from the page: not a page publication date); **7 are `unknown`** (F01, F03, F04, F06, F11, F13, F14). F10 and F12 already had dates and kept them (F10 now confirmed by the page itself, F12 by the post).
- `author` of the 14: 1 read `por confirmar` before (F06); it became a real value (Jake Teton-Landis, by hand from the npm registry metadata). **0 are `unknown`.** The tool extracted a wrong author (the site, not the writer or owner) for 5 records (F01, F02, F03, F12, F14) and none for F06; those 6 were set by hand from the page. The authors of F05, F07 and F08 were extracted correctly and are more precise than fontes.md (people instead of the organization or username), so the rewrite should use the record values.
- Status: 13 `used`, 1 `discarded` (F04, `dead`).
- Snapshots: all 14 records have one. F03 and F06 have a `manual` snapshot (the server-rendered `/usage` page of F03; the npm registry README of F06), added after the migration with `bkf sources snapshot`.
- `bkf sources check` reports all 14 records `ok`; `bkf validate ~/sources` is CONFORMANT.

## Ids

Seven ids from the first pass were poor (`ai-ai-engineer`, `atlassian-unknown`, `socket-unknown`, `github-github-imbue-ai-ratchets`, ...). They were renamed once, before anyone cited them; the table above has the final ids. From now on an id never changes after `finish`.
