import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.engine.diffbase import snapshot_commit
from harness.engine import group
from harness.engine.group import prepare_worktrees, remove_worktrees, run_group
from harness.engine.run import RunDir, RunError, Settings


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        self.run = RunDir.create(self.root / "runs", "sample", self.repo,
                                 Settings("model", "effort", "effort"), "none")
        self.env = os.environ.copy()
        self.bin = self.root / "bin"
        self.bin.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo)] + list(args), check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=self.env if hasattr(self, "env") else None).stdout.strip()

    def fake_df(self, before, after):
        script = self.bin / "df"
        count = self.root / "df-count"
        script.write_text(
            "#!/bin/sh\n"
            "n=0; [ -f \"$DF_COUNT\" ] && n=$(cat \"$DF_COUNT\"); n=$((n+1)); echo $n >\"$DF_COUNT\"\n"
            "if [ $n -eq 1 ]; then value=$DF_BEFORE; else value=$DF_AFTER; fi\n"
            "printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\\n/dev/fake 999999 0 %s 0%% /fake\\n' \"$value\"\n",
            encoding="utf-8")
        script.chmod(0o755)
        try:
            count.unlink()
        except FileNotFoundError:
            pass
        self.env.update({"PATH": str(self.bin) + os.pathsep + self.env.get("PATH", ""),
                         "DF_COUNT": str(count), "DF_BEFORE": str(before), "DF_AFTER": str(after)})

    def test_snapshot_commit_uses_working_tree_and_expected_identity(self):
        (self.repo / "new.txt").write_text("new\n", encoding="utf-8")
        (self.repo / "ignored.txt").write_text("ignored\n", encoding="utf-8")
        commit = snapshot_commit(self.repo)
        self.assertEqual(self.git("show", "-s", "--format=%an <%ae>|%cn <%ce>|%s", commit),
                         "plan-run <plan-run@localhost>|plan-run <plan-run@localhost>|plan-run snapshot")
        names = self.git("ls-tree", "-r", "--name-only", commit).splitlines()
        self.assertIn("new.txt", names)
        self.assertNotIn("ignored.txt", names)

    def test_snapshot_failure_falls_back_to_head(self):
        self.fake_df(300000, 200000)
        with patch.object(group, "snapshot_commit", side_effect=RunError("snapshot failed")):
            self.assertEqual(prepare_worktrees(self.run, self.repo, 1, ["a"], environ=self.env), "")
        self.assertTrue((self.run.path / "worktrees/a/tracked.txt").is_file())

    def test_worktree_creation_failure_returns_reason_and_keeps_log(self):
        def failed_add(repo, args, output=None):
            if args[:2] == ["worktree", "add"]:
                output.write("worktree add failed\n")
                return subprocess.CompletedProcess(args, 1, "", "")
            return original_git(repo, args, output)

        original_git = group._git
        with patch.object(group, "_git", side_effect=failed_add):
            reason = prepare_worktrees(self.run, self.repo, 1, ["a"], environ=self.env)
        log = self.run.path / "a.worktree.log"
        self.assertEqual(reason, "could not create the worktree for a (see {0})".format(log))
        self.assertEqual(log.read_text(), "worktree add failed\n")
        self.assertFalse((self.run.path / ".group-ready-S1").exists())

    def test_group_worktrees_share_snapshot_and_resume_does_not_remake_them(self):
        (self.repo / "untracked.txt").write_text("snapshot\n", encoding="utf-8")
        (self.repo / "ignored.txt").write_text("ignored\n", encoding="utf-8")
        self.fake_df(300000, 200000)
        ready = prepare_worktrees(self.run, self.repo, 1, ["a", "b"], environ=self.env)
        self.assertEqual(ready, "")
        self.assertIn("S1: disk: the first worktree took 97 MB; 1 more need about 122 MB, 195 MB free",
                      (self.run.path / "status.log").read_text())
        for unit in ("a", "b"):
            worktree = self.run.path / "worktrees" / unit
            self.assertEqual((worktree / "untracked.txt").read_text(), "snapshot\n")
            self.assertFalse((worktree / "ignored.txt").exists())
        before = self.git("worktree", "list", "--porcelain")
        (self.run.path / "worktrees" / "a" / "untracked.txt").write_text("later\n")
        prepare_worktrees(self.run, self.repo, 1, ["a", "b"], environ=self.env)
        self.assertEqual(before, self.git("worktree", "list", "--porcelain"))
        self.assertEqual((self.run.path / "worktrees" / "a" / "untracked.txt").read_text(), "later\n")

    def declare(self, section):
        (self.repo / ".plan-run.json").write_text(json.dumps({"worktree": section}), encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-qm", "declare")

    def test_every_group_worktree_is_set_up_as_the_repository_declares(self):
        self.declare({"copy": ["local.env"], "prepare": ["echo built > built.txt"]})
        (self.repo / "local.env").write_text("S=1\n", encoding="utf-8")
        self.fake_df(300000, 200000)
        self.assertEqual(prepare_worktrees(self.run, self.repo, 1, ["a", "b"], environ=self.env), "")
        for unit in ("a", "b"):
            worktree = self.run.path / "worktrees" / unit
            self.assertEqual((worktree / "built.txt").read_text(), "built\n")
            self.assertEqual((worktree / "local.env").read_text(), "S=1\n")
            self.assertTrue((self.run.path / ("prepare-" + unit) / "gate.md").is_file())
            self.assertTrue((self.run.path / (".prepared-" + unit)).exists())
        log = (self.run.path / "status.log").read_text()
        for unit in ("a", "b"):
            self.assertIn("S1: {0}: worktree.prepare: 1 command(s) passed".format(unit), log)

    def test_a_failing_prepare_refuses_the_group_and_resume_sets_the_copy_up_again(self):
        self.declare({"prepare": ["test -f ok.flag"]})
        self.fake_df(300000, 200000)
        reason = prepare_worktrees(self.run, self.repo, 1, ["a", "b"], environ=self.env)
        self.assertIn("could not prepare the worktree for a", reason)
        self.assertFalse((self.run.path / ".group-ready-S1").exists())
        self.assertFalse((self.run.path / ".prepared-a").exists())
        (self.run.path / "worktrees" / "a" / "ok.flag").touch()
        (self.run.path / "worktrees" / "b" / "ok.flag").touch()
        self.assertEqual(prepare_worktrees(self.run, self.repo, 1, ["a", "b"], environ=self.env), "")
        self.assertTrue((self.run.path / ".group-ready-S1").exists())

    def test_a_copy_that_exists_without_its_marker_is_set_up_on_resume(self):
        self.declare({"prepare": ["echo built > built.txt"]})
        self.fake_df(300000, 200000)
        prepare_worktrees(self.run, self.repo, 1, ["a"], environ=self.env)
        for name in (".prepared-a", ".group-ready-S1"):
            (self.run.path / name).unlink()
        (self.run.path / "worktrees" / "a" / "built.txt").unlink()
        self.assertEqual(prepare_worktrees(self.run, self.repo, 1, ["a"], environ=self.env), "")
        self.assertTrue((self.run.path / "worktrees" / "a" / "built.txt").is_file())

    def test_worktrees_are_only_cut_where_they_are_also_set_up(self):
        engine = Path(group.__file__).parent
        cutters = sorted(path.name for path in engine.glob("*.py") if '"worktree", "add"' in path.read_text(encoding="utf-8"))
        self.assertEqual(cutters, ["checkout.py", "group.py"])
        source = Path(group.__file__).read_text(encoding="utf-8")
        self.assertIn("prepare_tree(", source.split("def prepare_worktrees", 1)[1].split("def run_group", 1)[0])

    def test_run_group_runs_units_concurrently_and_keeps_pass_on_failure(self):
        self.fake_df(300000, 200000)
        codex = self.bin / "codex"
        codex.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, sys, time\n"
            "unit, worktree, state = sys.argv[1:]\n"
            "state = pathlib.Path(state)\n"
            "(state / (unit + '.ready')).touch()\n"
            "other = 'b' if unit == 'a' else 'a'\n"
            "deadline = time.time() + 5\n"
            "while not (state / (other + '.ready')).exists() and time.time() < deadline: time.sleep(.01)\n"
            "if not (state / (other + '.ready')).exists(): raise SystemExit(2)\n"
            "pathlib.Path(worktree, 'ran').write_text(unit)\n"
            "raise SystemExit(1 if unit == 'b' else 0)\n",
            encoding="utf-8")
        codex.chmod(0o755)
        state = self.root / "agents"
        state.mkdir()

        class Context:
            def __init__(self, run, repo):
                self.lines = []
                self.run = run
                self.repo = repo
                self.checkout = repo

            def progress(self, line):
                self.lines.append(line)

        ctx = Context(self.run, self.repo)

        def runner(unit, worktree):
            result = subprocess.run([str(codex), unit, str(worktree), str(state)], check=False)
            return (result.returncode == 0, "failed b" if unit == "b" else "")

        ok, reason = run_group(ctx, 1, ["a", "b"], runner, environ=self.env)
        self.assertFalse(ok)
        self.assertEqual(reason, "failed b; ")
        self.assertTrue((self.run.path / ".done-a").exists())
        self.assertFalse((self.run.path / ".done-b").exists())
        self.assertEqual((self.run.path / "b" / "reason").read_text(), "failed b\n")
        self.assertIn("S1 início · paralelo · a, b", ctx.lines)

    def test_disk_refusal_removes_created_worktrees_and_can_resume(self):
        self.fake_df(210000, 110000)
        class Context:
            def __init__(self, run, repo):
                self.run = run
                self.repo = repo
                self.checkout = repo

            def progress(self, _line):
                pass

        ctx = Context(self.run, self.repo)
        refusal = run_group(ctx, 1, ["a", "b"], lambda _unit, _path: (True, ""), environ=self.env)
        self.assertFalse(refusal[0])
        refusal = refusal[1]
        self.assertIn("not enough free disk", refusal)
        events = (self.run.path / "status.log").read_text()
        self.assertIn("S1: disk: the first worktree took 97 MB; 1 more need about 122 MB, 107 MB free", events)
        self.assertIn("S1: " + refusal, events)
        self.assertEqual(refusal, "not enough free disk for the parallel group of step 1: the first worktree took 97 MB, the other 1 need about 122 MB with a margin of a quarter, and 107 MB is free where the run lives ({0}). Free some space, then resume. The estimate covers the worktrees only, not what the units create while they run (temporary database clusters, build output).".format(self.run.path))
        self.assertFalse((self.run.path / "worktrees").exists())
        self.assertFalse((self.run.path / ".group-ready-S1").exists())
        self.fake_df(1000, 2000)
        passed, reason = run_group(ctx, 1, ["a", "b"], lambda _unit, _path: (True, ""), environ=self.env)
        self.assertTrue(passed, reason)
        self.assertTrue((self.run.path / ".done-a").exists())
        self.assertTrue((self.run.path / ".done-b").exists())
        self.assertIn("S1: disk: the first worktree took 0 MB; 1 more need about 0 MB", (self.run.path / "status.log").read_text())

    def test_remove_worktrees_cleans_git_registration(self):
        self.fake_df(300000, 200000)
        prepare_worktrees(self.run, self.repo, 1, ["a"], environ=self.env)
        remove_worktrees(self.run, self.repo)
        self.assertFalse((self.run.path / "worktrees").exists())
        entries = [line for line in self.git("worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]
        self.assertEqual(len(entries), 1)


if __name__ == "__main__":
    unittest.main()
