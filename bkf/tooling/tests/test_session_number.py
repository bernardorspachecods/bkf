from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))
import session_number


class SessionNumberTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.sessions, self.state, self.repo = root / "sessions", root / "state", root / "myrepo"
        self.sessions.mkdir()
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def register(self, sid: str, name: str, source: str = "derived", pid: int | None = None, kind: str = "interactive") -> int:
        pid = pid or os.getpid()
        entry = {"pid": pid, "sessionId": sid, "name": name, "nameSource": source, "kind": kind}
        (self.sessions / f"{sid}.json").write_text(json.dumps(entry))
        return pid

    def ask(self, sid: str, event: str = "UserPromptSubmit") -> str | None:
        data = {"hook_event_name": event, "session_id": sid, "cwd": str(self.repo)}
        return session_number.session_name(data, self.sessions, self.state)

    def test_first_session_gets_number_one(self) -> None:
        self.register("a", "myrepo-1a")
        self.assertEqual(self.ask("a"), "myrepo1")

    def test_takes_lowest_free_number_among_live_sessions(self) -> None:
        self.register("a", "myrepo1", "user")
        self.register("b", "myrepo3", "user")
        self.register("c", "myrepo-9z")
        self.assertEqual(self.ask("c"), "myrepo2")

    def test_dead_session_frees_its_number(self) -> None:
        dead = subprocess.Popen(["true"])
        dead.wait()
        self.register("a", "myrepo1", "user", pid=dead.pid)
        self.register("b", "myrepo-9z")
        self.assertEqual(self.ask("b"), "myrepo1")

    def test_keeps_a_name_the_user_chose(self) -> None:
        self.register("a", "my-own-name", "user")
        self.assertIsNone(self.ask("a"))

    def test_keeps_an_existing_number_name(self) -> None:
        self.register("a", "myrepo4")
        self.assertIsNone(self.ask("a"))

    def test_only_interactive_sessions_on_prompt_submit(self) -> None:
        self.register("a", "myrepo-1a", kind="agent")
        self.assertIsNone(self.ask("a"))
        self.register("b", "myrepo-2b")
        self.assertIsNone(self.ask("b", "Stop"))
        self.assertIsNone(self.ask("unknown"))

    def test_a_fresh_claim_holds_the_number_for_a_session_not_registered_yet(self) -> None:
        self.register("a", "myrepo-1a", pid=os.getppid())
        self.register("b", "myrepo-2b")
        self.assertEqual(self.ask("a"), "myrepo1")
        self.assertEqual(self.ask("b"), "myrepo2")
        claims = json.loads((self.state / "session-names.json").read_text())
        claims["myrepo1"][1] = time.time() - session_number.CLAIM_SECONDS - 1
        (self.state / "session-names.json").write_text(json.dumps(claims))
        self.assertEqual(self.ask("b"), "myrepo1")

    def test_asking_again_gives_the_same_name(self) -> None:
        self.register("a", "myrepo-1a")
        self.assertEqual(self.ask("a"), "myrepo1")
        self.assertEqual(self.ask("a"), "myrepo1")

    def test_worktree_uses_the_main_repository_name(self) -> None:
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x"], check=True)
        tree = Path(self.tmp.name) / "elsewhere"
        subprocess.run(["git", "-C", str(self.repo), "worktree", "add", "-q", str(tree)], check=True)
        self.assertEqual(session_number.repo_name(tree), "myrepo")


if __name__ == "__main__":
    unittest.main()
