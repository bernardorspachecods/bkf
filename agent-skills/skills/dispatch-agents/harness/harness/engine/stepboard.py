"""Render a shell-compatible board from a run directory.

    render_steps(run_dir, specs, title="Run", now=None)

``specs`` contains ``<id>|<label>|<directory>|<agent folders>|<agent output file>``
strings. ``now`` is an optional ``HH:MM`` value for deterministic comparisons.
The returned text follows the shell step-board format.
"""

import os
from datetime import datetime
from pathlib import Path


def _event_state(status_path):
    stopped = ""
    active = ""
    try:
        lines = status_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return stopped, active
    for line in lines:
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        event = fields[1]
        if event == "resume":
            stopped, active = "", ""
        elif event.startswith("STOPPED at "):
            stopped = event[len("STOPPED at "):].split(":", 1)[0]
            active = ""
        elif event.startswith("start "):
            name = event[6:]
            active = name.split(" ", 1)[0] if " " in name else ""
        elif event.startswith("done "):
            name = event[5:].split(" ", 1)[0]
            if active == name:
                active = ""
    return stopped, active


def render_steps(run_dir, specs, title="Run", now=None):
    """Return the board text for a run directory and shell-format step specs."""
    run_path = Path(run_dir)
    run_name = run_path.name
    status_path = run_path / "status.log"
    start_stamp = ""
    try:
        for index, line in enumerate(status_path.read_text(encoding="utf-8").splitlines(), 1):
            if index == 2:
                start_stamp = line.split("\t", 1)[0]
                break
    except (OSError, UnicodeError):
        pass
    start_time = start_stamp.partition("T")[2][:5] or "--:--"
    now_time = now or datetime.now().strftime("%H:%M")
    output = ["{0} {1} · início {2} → agora {3}\n\n".format(title, run_name, start_time, now_time)]
    first_pending_seen = False
    for spec in specs:
        fields = spec.split("|", 4)
        fields += [""] * (5 - len(fields))
        step_id, label, step_dir, agent_folders, output_file = fields
        stopped_id, running_id = _event_state(status_path)
        step_running = False
        if (run_path / (".done-" + step_id)).exists():
            icon = "✓"
        elif stopped_id == step_id:
            icon = "✗"
            first_pending_seen = True
        elif not first_pending_seen:
            first_pending_seen = True
            icon = "◐" if running_id == step_id else "○"
            step_running = running_id == step_id
        else:
            icon = "○"
        output.append("{0} {1}\n".format(icon, label))
        for agent in agent_folders.split():
            agent_path = run_path / step_dir / agent
            agent_output = agent_path / output_file if output_file else None
            if agent_output is not None and agent_output.is_file() and agent_output.stat().st_size > 0:
                agent_icon = "✓"
            elif (agent_path / "failed").exists():
                agent_icon = "✗"
            elif step_running:
                agent_icon = "◐"
            else:
                agent_icon = "○"
            output.append("    {0} {1}\n".format(agent_icon, agent))
    return "".join(output)
