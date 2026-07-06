from __future__ import annotations

import re
from pathlib import Path


PROJECT_PLACEHOLDERS = {
    "<workspace-root>",
    "<current-project-folder>",
    "<model-project-folder>",
}


def is_absolute_project_arg(raw: str) -> bool:
    value = raw.strip().strip('"').strip("'")
    return value.startswith("~") or Path(value).is_absolute() or bool(re.match(r"^[A-Za-z]:|^\\\\", value))


def resolve_workspace_project(raw_project: str) -> Path:
    raw = raw_project.strip()
    if raw in PROJECT_PLACEHOLDERS:
        raw = "."
    elif "<" in raw or ">" in raw:
        raise ValueError("replace placeholder project path before running, for example: --project .")
    elif is_absolute_project_arg(raw):
        raise ValueError("--project must be a relative path. Use --project . or --project <selected_model_work_folder>")

    project = Path(raw).expanduser().resolve()
    parts = project.parts
    if ".opencode" in parts:
        opencode_index = parts.index(".opencode")
        if opencode_index > 0:
            return Path(*parts[:opencode_index]).resolve()
    return project


def is_filesystem_root(path: Path) -> bool:
    return path.parent == path


def is_opencode_sample_source(path: Path) -> bool:
    return ".opencode" in path.resolve().parts


def unique_paths(paths: list[Path]) -> list[Path]:
    unique = []
    seen = set()
    for path in paths:
        try:
            key = path.resolve()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique
