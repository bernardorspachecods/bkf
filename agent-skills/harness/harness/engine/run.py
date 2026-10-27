import re
from collections import namedtuple
from datetime import datetime
from pathlib import Path


Settings = namedtuple("Settings", "model effort review_effort")


class RunError(Exception):
    """An error suitable for display to the user."""


def valid_name(name):
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", name) and name not in (".", ".."))


def valid_pause(text):
    return bool(re.fullmatch(r"(?:none|each|[0-9]+(?:,[0-9]+)*)", text))


def _write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as output:
        output.write(text)


def _settings_text(settings):
    return "{0} {1} {2}\n".format(*settings)


def _read_settings(path):
    with open(path, "r", encoding="utf-8", newline="") as source:
        line = source.readline().rstrip("\n")
    fields = line.split(" ", 2)
    fields.extend([""] * (3 - len(fields)))
    return Settings(*fields[:3])


class RunDir:
    """The persisted state of one workflow run."""

    def __init__(self, path, repo, settings, pause):
        self.path = Path(path)
        self.name = self.path.name
        self.repo = repo
        self.settings = settings
        self.pause = pause

    @property
    def checkout(self):
        """Where the agents work: the run's own worktree when it has one, else the repository's checkout."""
        tree = self.path / "tree"
        return str(tree) if tree.is_dir() else self.repo

    @classmethod
    def create(cls, root, name, repo, settings, pause):
        if not valid_name(name):
            raise RunError("bad run name: {0}".format(name))
        path = Path(root) / name
        try:
            path.mkdir(parents=True)
        except FileExistsError:
            raise RunError("run already exists: {0} (finish it, or resume it)".format(path))
        _write_text(path / "repo", "{0}\n".format(repo))
        _write_text(path / "pause", "{0}\n".format(pause))
        _write_text(path / "settings", _settings_text(settings))
        _write_text(path / "status.log", "time\tevent\n")
        return cls(path, str(repo), settings, pause)

    @classmethod
    def load(cls, root, name):
        if not valid_name(name):
            raise RunError("bad run name: {0}".format(name))
        path = Path(root) / name
        if not path.is_dir():
            raise RunError("no such run: {0}".format(path))
        with open(path / "repo", "r", encoding="utf-8", newline="") as source:
            repo = source.read().rstrip("\n")
        settings_path = path / "settings"
        settings = _read_settings(settings_path) if settings_path.is_file() else None
        try:
            with open(path / "pause", "r", encoding="utf-8", newline="") as source:
                pause = source.read().rstrip("\n")
        except FileNotFoundError:
            pause = ""
        return cls(path, repo, settings, pause)

    def save_settings(self, settings):
        _write_text(self.path / "settings", _settings_text(settings))
        self.settings = settings

    def set_pause(self, text):
        _write_text(self.path / "pause", "{0}\n".format(text))
        self.pause = text

    def note(self, text):
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with open(self.path / "status.log", "a", encoding="utf-8", newline="") as output:
            output.write("{0}\t{1}\n".format(timestamp, text))

    def is_done(self, marker):
        return (self.path / ".done-{0}".format(marker)).exists()

    def mark_done(self, marker):
        (self.path / ".done-{0}".format(marker)).touch()

    def pause_here(self, step):
        if (self.path / ".paused-S{0}".format(step)).exists():
            return False
        if self.pause == "each":
            return True
        if not self.pause or self.pause == "none":
            return False
        return str(step) in self.pause.split(",")

    def mark_paused(self, step):
        (self.path / ".paused-S{0}".format(step)).touch()
