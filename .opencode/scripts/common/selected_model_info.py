from __future__ import annotations

import os
import re
from pathlib import Path


PATH_SEPARATOR_TRANSLATION = str.maketrans(
    {
        "\\": "/",
        "＼": "/",
        "￦": "/",
        "₩": "/",
    }
)


def normalize_path_text(value: str) -> str:
    return re.sub(r"/+", "/", str(value).translate(PATH_SEPARATOR_TRANSLATION))


def project_relative_posix(path: Path, base: Path) -> str:
    try:
        return normalize_path_text(path.relative_to(base).as_posix())
    except ValueError:
        try:
            return normalize_path_text(os.path.relpath(path, base))
        except ValueError:
            return normalize_path_text(path.as_posix())


def project_relative_windows(path: Path, base: Path) -> str:
    return project_relative_posix(path, base).replace("/", "\\")


def build_selected_model_info(project: Path, selected_model: Path, model_kind: str) -> dict[str, str]:
    return {
        "model_kind": model_kind,
        "url": f"saved_model/{selected_model.name}",
        "path": f"saved_model\\{selected_model.name}",
        "source_url": project_relative_posix(selected_model, project),
        "source_path": project_relative_windows(selected_model, project),
    }


def selected_model_source_path(payload: dict[str, object]) -> str | None:
    value = (
        payload.get("source_path")
        or payload.get("source_url")
        or payload.get("path")
        or payload.get("url")
    )
    return value if isinstance(value, str) and value.strip() else None


def selected_model_kind(payload: dict[str, object]) -> str | None:
    value = payload.get("model_kind") or payload.get("kind")
    return value if isinstance(value, str) and value.strip() else None
