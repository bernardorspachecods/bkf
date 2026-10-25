"""Implementation round metrics recorded by workflow runs."""
import re
import time
from pathlib import Path


_INPUT_TOKENS = re.compile(r'"input_tokens":([0-9]+)')


def record_metrics(run_path, unit, round_number, round_dir, start_epoch):
    """Append one tab-separated summary line for an implementation round."""
    run_path = Path(run_path)
    round_dir = Path(round_dir)
    events_path = round_dir / "implement.events.jsonl"
    patch_path = round_dir / "diff.patch"
    try:
        events = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        events = []
    try:
        patch_lines = patch_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        patch_lines = []

    steps = sum('"type":"item.completed"' in line for line in events)
    files = sum(line.startswith("diff --git") for line in patch_lines)
    token_matches = [match for line in events for match in _INPUT_TOKENS.finditer(line)]
    tokens = int(token_matches[-1].group(1)) if token_matches else 0
    minutes = (int(time.time()) - int(start_epoch)) // 60
    with (run_path / "metrics.tsv").open("a", encoding="utf-8", newline="") as output:
        output.write(
            "{0}\t{1}\t{2}\t{3}\t{4}\t{5}\n".format(
                unit, round_number, minutes, steps, files, tokens
            )
        )
