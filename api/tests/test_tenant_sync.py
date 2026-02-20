from __future__ import annotations

from app.services.tenancy import sync_tenants_from_shared_config


class _Result:
    def __init__(self, value=0):
        self._value = value

    def scalar(self):
        return self._value


class _FakeDB:
    def __init__(self):
        self.pre = 0
        self.post = 7

    def execute(self, statement, params=None):
        sql = str(statement)
        if "SELECT COUNT(1) FROM tenant" in sql:
            v = self.pre
            self.pre = self.post
            return _Result(v)
        return _Result(0)


def test_sync_tenants_from_shared_config_returns_expected_slugs(monkeypatch):
    monkeypatch.setattr(
        "app.services.tenancy.get_shared_tenant_definitions",
        lambda: [
            {"slug": "cbs", "name": "CBS", "email_domains": ["gsb.columbia.edu"], "theme": {}, "timezone": "America/New_York"},
            {"slug": "hbs", "name": "HBS", "email_domains": ["hbs.edu"], "theme": {}, "timezone": "America/New_York"},
            {"slug": "gsb", "name": "GSB", "email_domains": ["stanford.edu"], "theme": {}, "timezone": "America/Los_Angeles"},
            {"slug": "wharton", "name": "Wharton", "email_domains": ["upenn.edu"], "theme": {}, "timezone": "America/New_York"},
            {"slug": "kellogg", "name": "Kellogg", "email_domains": ["northwestern.edu"], "theme": {}, "timezone": "America/Chicago"},
            {"slug": "booth", "name": "Booth", "email_domains": ["uchicago.edu"], "theme": {}, "timezone": "America/Chicago"},
            {"slug": "sloan", "name": "Sloan", "email_domains": ["mit.edu"], "theme": {}, "timezone": "America/New_York"},
        ],
    )
    out = sync_tenants_from_shared_config(_FakeDB())
    assert out["loaded"] == 7
    assert out["upserted"] == 7
    assert sorted(out["slugs"]) == ["booth", "cbs", "gsb", "hbs", "kellogg", "sloan", "wharton"]
