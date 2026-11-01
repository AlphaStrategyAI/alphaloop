"""Content-addressed material files. A later edit of the same DOI does not overwrite."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from engine.research.gather import Material


def material_content_hash(material: Material) -> str:
    return hashlib.sha256(material.text.encode("utf-8")).hexdigest()


def citation_payload(material: Material) -> dict[str, object]:
    published = material.published_at.isoformat() if material.published_at is not None else None
    rights = "local_only" if material.source == "local" else "metadata_only"
    return {
        "material_id": material.material_id,
        "source": material.source,
        "source_id": material.source,
        "locator": material.url,
        "title": material.title,
        "url": material.url,
        "text": material.text,
        "fetched_at": material.fetched_at.isoformat(),
        "published_at": published,
        "published_precision": material.published_precision,
        "rights": rights,
        "content_hash": material_content_hash(material),
    }


def write_immutable_material(evidence_root: Path, material: Material) -> Path:
    """Store bytes once by content hash and a citation that points at that hash.

    Two materials may share text. Their citations stay distinct. A later edit of
    the same DOI writes a new hash and does not replace the old bytes.
    """
    payload = citation_payload(material)
    digest = str(payload["content_hash"])
    directory = evidence_root / "by-hash"
    directory.mkdir(parents=True, exist_ok=True)
    blob = directory / digest
    if not blob.is_file():
        temporary = blob.with_suffix(".tmp")
        temporary.write_text(material.text, encoding="utf-8")
        temporary.replace(blob)
    identity = hashlib.sha256(material.material_id.encode("utf-8")).hexdigest()[:16]
    path = directory / f"{digest}-{identity}.json"
    if path.is_file():
        return path
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def read_material_text(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("material file is not an object")
    text = payload.get("text")
    if not isinstance(text, str):
        raise TypeError("material file has no text")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    recorded = payload.get("content_hash")
    if recorded != digest:
        raise ValueError("material content hash does not match")
    return text


def material_asdict_fallback(material: Material) -> dict[str, object]:
    """Used only when a caller still wants the dataclass field set."""
    return asdict(material)
