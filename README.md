# Bernardo Knowledge Format (BKF)

BKF organizes a repository's knowledge so agents can find the current guidance and act correctly. Without clear ownership and discovery, the same facts get copied, drift from the code, and become hard for new agents to locate. BKF gives each fact, rule, and procedure one owner, uses maps to find documents, and provides tooling to check the format. It keeps repo-specific organization grounded in each repository's readers and work rather than prescribing a fixed set of documents.

## Repository contents

- [`bkf/`](bkf/MAP.md) defines the document, map, and bundle format and provides tooling to validate bundles and maintain inventories.
- [`agent-skills/`](agent-skills/MAP.md) contains request-matching skills and the shared rule library those skills select.

This repository is itself the worked example of BKF.

## A 10-minute path

1. Follow [INSTALL.md](INSTALL.md) to install the `bkf` command and link the skills.
2. From the repository root, run `bkf validate .` and `bkf orient`.
3. Open [`bkf/MAP.md`](bkf/MAP.md) and follow it to one document.
4. Point your agent at [`bkf/manual/build-repo-organization.md`](bkf/manual/build-repo-organization.md) to organize a repository of your own.

## Entry points

[Repository map](MAP.md) · [Agent instructions](AGENTS.md) · [BKF map](bkf/MAP.md) · [Agent skills map](agent-skills/MAP.md) · [What BKF is](bkf/manual/what-is-bkf.md)

## License

[MIT License](LICENSE)
