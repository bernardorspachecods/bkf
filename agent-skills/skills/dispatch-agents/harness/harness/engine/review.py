"""Run and validate one review of a round."""

import os
import shutil
from typing import NamedTuple, Optional

from ..verdict import checked_ok, read_verdict
from .agentstep import run_agent_step


class ReviewResult(NamedTuple):
    verdict: Optional[str]
    reason: str


def run_review(
    run,
    label,
    directory,
    round_dir,
    build_prompt,
    model,
    effort,
    tier,
    min_checked,
    previous_problems=None,
):
    """Run up to three reviewer attempts and persist a usable review."""
    round_path = os.fspath(round_dir)
    message_path = os.path.join(round_path, "review.last-message.md")
    prompt_path = os.path.join(round_path, "review-prompt.md")
    output_prefix = os.path.join(round_path, "review")

    for attempt in range(1, 4):
        try:
            os.remove(message_path)
        except FileNotFoundError:
            pass

        with open(prompt_path, "w", encoding="utf-8", newline="") as prompt:
            prompt.write(build_prompt(attempt))

        step = run_agent_step(
            run,
            label,
            directory,
            prompt_path,
            output_prefix,
            model,
            effort,
            "read-only",
            tier,
            "{0}: review exit=<exit> (see {1}/review.stderr.log)".format(
                label, round_path
            ),
        )
        if not step.ok:
            return ReviewResult(None, step.reason)

        verdict = read_verdict(message_path)
        usable = (
            os.path.isfile(message_path)
            and os.path.getsize(message_path) > 0
            and checked_ok(message_path, min_checked)
            and verdict is not None
        )
        if usable:
            problems_path = os.path.join(round_path, "problems.md")
            shutil.copyfile(message_path, problems_path)
            verdict_path = os.path.join(round_path, "verdict")
            with open(verdict_path, "w", encoding="utf-8", newline="") as output:
                output.write(verdict + "\n")
            run.note(
                "{0}: round {1}: verdict {2}".format(
                    label, os.path.basename(round_path), verdict
                )
            )
            return ReviewResult(verdict, "")

        run.note("{0}: review attempt {1} was not usable".format(label, attempt))

    return ReviewResult(
        None,
        "{0}: the reviewer left no usable review after {1} attempts (see {2})".format(
            label, attempt, message_path
        ),
    )
