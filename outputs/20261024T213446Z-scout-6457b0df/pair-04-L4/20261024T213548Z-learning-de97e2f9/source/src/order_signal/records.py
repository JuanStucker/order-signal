"""Researcher-only artifacts. Never pass these records to a prompt builder."""

import dataclasses
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
from types import SimpleNamespace


def jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value):
        return jsonable(dataclasses.asdict(value))
    if isinstance(value, SimpleNamespace):
        return jsonable(vars(value))
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    return value


def safe_json(value, **kwargs):
    text = json.dumps(jsonable(value), allow_nan=False, **kwargs)
    # Provider failures can echo credentials inside otherwise raw response bodies.
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        text = text.replace(json.dumps(key)[1:-1], "[REDACTED]")
    return text


def write(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(safe_json(value, indent=2) + "\n")
    temp.replace(path)


def append(path, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(safe_json(value) + "\n")
        stream.flush()


def provenance(destination, project):
    sources = sorted((project / "src/order_signal").glob("*.py"))
    sources += [
        project / p for p in ("pyproject.toml", "uv.lock", "SOURCE_PROVENANCE.json")
    ]
    hashes = {}
    for source in sources:
        if source.exists():
            relative = source.relative_to(project)
            target = destination / "source" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            hashes[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()
    write(
        destination / "provenance.json",
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "source_sha256": hashes,
            "installed_dependencies": {
                d.metadata["Name"]: d.version
                for d in importlib.metadata.distributions()
            },
        },
    )
