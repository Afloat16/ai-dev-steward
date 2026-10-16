"""Load exact upstream source files without importing optional project dependencies."""
import importlib.util
import os
from pathlib import Path

import pytest


@pytest.fixture
def load_source():
    root = Path(os.environ.get("SOURCE_ROOT", Path(__file__).resolve().parents[1] / "baseline"))

    def load(filename):
        path = root / filename
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return load
