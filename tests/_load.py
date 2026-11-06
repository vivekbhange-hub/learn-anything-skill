"""Load helper scripts by file path (skill folders contain hyphens, so they are not packages)."""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load(relative_path: str, name: str):
    path = REPO / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
