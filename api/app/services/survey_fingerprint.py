from __future__ import annotations

import hashlib
import json
from typing import Any


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        if all(isinstance(v, dict) and "value" in v and "label" in v for v in value):
            ordered = sorted(
                [_normalize(v) for v in value],
                key=lambda x: (str(x.get("value")), str(x.get("label"))),
            )
            return ordered
        return [_normalize(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_normalize(value), separators=(",", ":"), ensure_ascii=False)


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def survey_fingerprint(survey_def: dict[str, Any]) -> dict[str, Any]:
    survey_meta = survey_def.get("survey") if isinstance(survey_def, dict) else {}
    slug = str((survey_meta or {}).get("slug") or "")
    version = (survey_meta or {}).get("version")
    return {
        "slug": slug,
        "version": int(version) if str(version).isdigit() else version,
        "hash": sha256_hex(survey_def if isinstance(survey_def, dict) else {}),
    }


def question_semantics_hash(question: dict[str, Any], options: Any = None) -> str:
    payload = {
        "prompt": question.get("text"),
        "type": question.get("response_type"),
        "options": options,
        "validation": {
            "is_required": bool(question.get("is_required", False)),
            "allow_skip": bool(question.get("allow_skip", False)),
            "rules": question.get("rules") or [],
        },
        "scoring": {
            "usage": question.get("usage"),
            "reverse_coded": bool(question.get("reverse_coded", False)),
            "region_tag": question.get("region_tag"),
        },
    }
    return sha256_hex(payload)


def build_question_index(survey_def: dict[str, Any]) -> dict[str, dict[str, Any]]:
    option_sets = survey_def.get("option_sets") if isinstance(survey_def.get("option_sets"), dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for screen in survey_def.get("screens", []) if isinstance(survey_def, dict) else []:
        if not isinstance(screen, dict):
            continue
        for item in screen.get("items", []) if isinstance(screen.get("items"), list) else []:
            if not isinstance(item, dict):
                continue
            q = item.get("question") if isinstance(item.get("question"), dict) else {}
            code = str(q.get("code") or "").strip()
            if not code:
                continue
            opts = item.get("options")
            if isinstance(opts, str):
                resolved_opts = option_sets.get(opts)
            else:
                resolved_opts = opts
            out[code] = {
                "question": q,
                "screen_key": screen.get("key"),
                "is_required": bool(q.get("is_required", False)) and not bool(q.get("allow_skip", False)),
                "question_hash": question_semantics_hash(q, resolved_opts),
            }
    return out
