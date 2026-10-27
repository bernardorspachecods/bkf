"""Check, before a run starts, that the agent backend it will use is installed."""
import shutil

from ..agent import get_backend, resolve_backend
from .run import RunError


def require_backend(name=None):
    """Raise RunError unless the backend (the named one, else HARNESS_BACKEND, else codex) can be launched."""
    backend_class = get_backend(name)
    if backend_class is None:
        raise RunError("backend not implemented: {0}".format(resolve_backend(name)))
    if shutil.which(backend_class.executable) is None:
        raise RunError("{0} not found".format(backend_class.executable))
