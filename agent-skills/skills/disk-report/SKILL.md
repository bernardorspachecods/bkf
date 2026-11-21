---
name: disk-report
description: Measure what takes disk space on the user's Mac and present it as a table with a risk per item (Claude and Codex sessions, caches, Xcode, VMs, app data). Use when the user wants to free disk space or asks what is filling the disk. It is read-only and never deletes anything; do not use to clean up git branches or worktrees (use git-worktree-cleanup).
---

# Disk report

This skill shows the user where their disk space went so they can choose what to free. It never deletes, moves or empties anything, not even items the report marks as safe, and not even when the user says "limpa tudo". Deleting is a separate step the user asks for after seeing the table.

## Run it

```
bash agent-skills/skills/disk-report/scripts/disk-report.sh [min_mb]
```

The script is [scripts/disk-report.sh](scripts/disk-report.sh).

- `min_mb` (default 100) hides items smaller than that.
- It takes about two minutes on a full disk. Run it in the background and wait for it; do not start a second copy.
- It only reads. Its output is the table, a free-space line and an unclassified detail per area.

## What you give the user

Present the script's output as the user saw it the first time: the table of known items first (size, risk, note), the unclassified detail after it. Keep it short, then add:

- the total the "Nenhum" and "Baixo" rows would free, as an estimate;
- what you did not check (for example whether Codex needs its history to resume sessions) before the user decides on "Médio" rows;
- items that appear in the detail but have no risk, as "a confirmar": say what you do not know about them instead of guessing.

Then ask what they want removed. Stop there.

## When the user chooses what to delete

Only after the user names the items: delete exactly those, report the free space before and after, and say what could not be removed. A request to delete one item is not approval for another.

## Keeping the script current

The risk classification lives in the script's `add` lines, not here. If an app moved its data or the user settled a risk (for example "Android is safe now"), edit the script, not this file. Read the script before changing it.
