# Bernardo Knowledge Format (BKF)

BKF organizes a repository's knowledge so agents can find the current guidance and act correctly. Without clear ownership and discovery, the same facts get copied, drift from the code, and become hard for new agents to locate. BKF gives each fact, rule, and procedure one owner, uses maps to find documents, and provides tooling to check the format. It keeps repo-specific organization grounded in each repository's readers and work rather than prescribing a fixed set of documents.

## What's in it

- **Format** ([`bkf/`](bkf/MAP.md)): defines a valid document, map, and bundle. The `bkf` command validates bundles, keeps map inventories current, orients an agent at session start, and searches documents. Optional hooks add talk and work modes, session-start orientation and personal rules, stop-time validation, and idea and feedback logging.
- **Library** ([`agent-skills/library/`](agent-skills/library/MAP.md)): rule modules and workflow types, each written once and selected per task.
- **Entry skills** ([`agent-skills/skills/`](agent-skills/MAP.md)): thin triggers, one per situation, each listing the library modules that apply.
- **Repo library**: a `repo-library/` folder in your own repository holds its local procedures and modules. They add to the shared library and never restate it.
- **Workflows** ([workflow foundation](bkf/format/agent-workflow-foundation.md)): for complex tasks, declared stages with handoffs, independent review, and user checkpoints, scaffolded by `bkf sync`.

[Why it is built in layers](bkf/manual/what-is-bkf.md#the-layers). [How it compares with a single AGENTS.md, editor rules, and skill collections, and when not to use it](bkf/manual/why-bkf.md). This repository is itself the worked example of BKF.

## A 10-minute path

1. Follow [INSTALL.md](INSTALL.md) to install the `bkf` command and link the skills.
2. From the repository root, run `bkf validate .` and `bkf orient`.
3. Open [`bkf/MAP.md`](bkf/MAP.md) and follow it to one document.
4. Point your agent at [`bkf/manual/build-repo-organization.md`](bkf/manual/build-repo-organization.md) to organize a repository of your own.

## Entry points

[Repository map](MAP.md) · [Agent instructions](AGENTS.md) · [BKF map](bkf/MAP.md) · [Agent skills map](agent-skills/MAP.md) · [What BKF is](bkf/manual/what-is-bkf.md)

## License

[MIT License](LICENSE)
