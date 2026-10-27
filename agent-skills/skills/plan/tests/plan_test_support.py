"""Throwaway repository and fake Codex helpers for plan workflow tests."""
import os
import subprocess
import tempfile
from pathlib import Path


class PlanRunFixture:
    def __init__(self, test_case):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "t"], check=True)
        (self.repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "init"], check=True)
        self.plan = self.root / "plan"
        self.plan.mkdir()
        self.goal = self.plan / "goal.md"
        self.goal.write_text("Goal\n", encoding="utf-8")
        self.guides = self.root / "guides"
        self.guides.mkdir()
        for name in ("plan-implementation.md", "plan-review.md"):
            (self.guides / name).write_text("guide\n", encoding="utf-8")
        self.runs = self.root / "runs"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        codex = self.bin / "codex"
        codex.write_text(_FAKE_CODEX, encoding="utf-8")
        codex.chmod(0o755)
        self.state = self.root / "state"
        self.state.mkdir()
        self.env = os.environ.copy()
        self.env.update({
            "PATH": str(self.bin) + os.pathsep + self.env.get("PATH", ""),
            "PLAN_RUNS_DIR": str(self.runs),
            "PLAN_GUIDES": str(self.guides),
            "FAKE_STATE": str(self.state),
            "FAKE_IMPLS": "{}",
        })
        self.test_case = test_case

    def add_brief(self, name, text="## Result\nImplement it.\n"):
        path = self.plan / (name + ".md")
        path.write_text(text, encoding="utf-8")
        return path

    def write_plan(self, *lines):
        path = self.plan / "plan.txt"
        path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
        return path

    def call(self, *args):
        from harness.engine.pipeline import main

        previous = os.getcwd()
        try:
            os.chdir(self.repo)
            with _environment(self.env):
                return main(str(_WORKFLOW), list(args))
        finally:
            os.chdir(previous)

    def close(self):
        self.temp.cleanup()


class _environment:
    def __init__(self, values):
        self.values = values
        self.previous = None

    def __enter__(self):
        self.previous = os.environ.copy()
        os.environ.clear()
        os.environ.update(self.values)

    def __exit__(self, exc_type, exc_value, traceback):
        os.environ.clear()
        os.environ.update(self.previous)


_WORKFLOW = Path(os.environ.get(
    "PLAN_WORKFLOW_PATH", str(Path(__file__).parents[1] / "scripts" / "plan.py")
))


_FAKE_CODEX = '''#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import sys

args = sys.argv[1:]
directory = pathlib.Path(args[args.index("-C") + 1])
output = pathlib.Path(args[args.index("-o") + 1])
prompt = sys.stdin.read()
state = pathlib.Path(os.environ["FAKE_STATE"])
if prompt.startswith("# Final review"):
    output.write_text("Final report\\n", encoding="utf-8")
elif prompt.startswith("# Review"):
    effort_file = state / "review-efforts"
    effort = next((value.partition("=")[2].strip('"') for value in args if value.startswith('model_reasoning_effort=')), "")
    with effort_file.open("a", encoding="utf-8") as efforts:
        efforts.write("model_reasoning_effort=" + effort + "\\n")
    count_file = state / "reviews"
    count = int(count_file.read_text() if count_file.exists() else "0") + 1
    count_file.write_text(str(count))
    remove = os.environ.get("FAKE_REMOVE_BRIEF_ON_REVIEW")
    if remove:
        pathlib.Path(remove).unlink(missing_ok=True)
    output.write_text("## What I checked\\n\\n- patch\\n- prompt\\n- result\\n\\n## Problems\\n\\nnone\\n\\nVERDICT: pass\\n", encoding="utf-8")
else:
    count_file = state / "implementations"
    count = int(count_file.read_text() if count_file.exists() else "0") + 1
    count_file.write_text(str(count))
    scripts = json.loads(os.environ.get("FAKE_IMPLS", "{}"))
    script = scripts.get(str(count), "echo change >> seed.txt")
    completed = subprocess.run(["bash", "-c", script], cwd=str(directory), check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)
    output.write_text("handoff\\n", encoding="utf-8")
    print('{"type":"item.completed"}')
    print('{"type":"item.completed"}')
    print('{"type":"item.completed"}')
    print('{"type":"turn.completed","usage":{"input_tokens":1234}}')
'''
