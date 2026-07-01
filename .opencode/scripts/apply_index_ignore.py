#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path


_IMPL = Path(__file__).resolve().parent / "03-environment-check" / "apply_index_ignore.py"


def _load_impl():
    module_name = "_opencode_impl_apply_index_ignore"
    spec = importlib.util.spec_from_file_location(module_name, _IMPL)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load script: {_IMPL}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    runpy.run_path(str(_IMPL), run_name="__main__")
else:
    _module = _load_impl()
    globals().update({name: getattr(_module, name) for name in dir(_module) if not name.startswith("__")})
