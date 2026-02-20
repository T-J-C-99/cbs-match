import pytest

pytest.importorskip("fastapi")

import app.main as m


def _iter_http_routes():
    for route in m.app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for method in sorted(methods):
            if method in {"HEAD", "OPTIONS"}:
                continue
            yield method, path


def test_no_duplicate_http_method_path_pairs():
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for pair in _iter_http_routes():
        if pair in seen:
            duplicates.append(pair)
        seen.add(pair)
    assert duplicates == []


def test_scaffold_namespace_contains_only_health_routes():
    scaffold_routes = [(method, path) for method, path in _iter_http_routes() if path.startswith("/_scaffold/")]
    assert scaffold_routes, "Expected scaffold routes to exist during migration"
    for method, path in scaffold_routes:
        assert method == "GET"
        assert path.endswith("/health")
