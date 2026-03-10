#!/usr/bin/env python3
import json
import os
import random
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE_URL = os.getenv('API_BASE_URL', '').rstrip('/')
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', '').strip()
SMOKE_TENANT_SLUG = os.getenv('SMOKE_TENANT_SLUG', 'cbs').strip()
SMOKE_PASSWORD = os.getenv('SMOKE_PASSWORD', 'community12345')
SMOKE_TIMEOUT = float(os.getenv('SMOKE_TIMEOUT_SECONDS', '20'))


def fail(msg: str, code: int = 1) -> None:
    print(f'[FAIL] {msg}')
    raise SystemExit(code)


def req(method: str, path: str, body: dict | None = None, headers: dict | None = None, token: str | None = None):
    if not API_BASE_URL:
        fail('API_BASE_URL is required')
    url = f"{API_BASE_URL}{path}"
    hdrs = {'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
    if token:
        hdrs['Authorization'] = f'Bearer {token}'

    data = None
    if body is not None:
        data = json.dumps(body).encode('utf-8')

    request = urllib.request.Request(url=url, method=method.upper(), data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(request, timeout=SMOKE_TIMEOUT) as resp:
            raw = resp.read().decode('utf-8')
            return resp.getcode(), (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        payload = e.read().decode('utf-8')
        try:
            parsed = json.loads(payload)
        except Exception:
            parsed = {'raw': payload}
        return e.code, parsed
    except Exception as e:
        fail(f'{method} {path} request error: {e}')


def expect(status: int, allowed: set[int], label: str, payload: dict):
    if status not in allowed:
        fail(f'{label} expected {sorted(allowed)} got {status} payload={payload}')
    print(f'[PASS] {label} ({status})')


def random_email() -> str:
    suffix = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10))
    return f'stage2-smoke-{suffix}@gsb.columbia.edu'


def main() -> None:
    if not API_BASE_URL:
        fail('Set API_BASE_URL, e.g. https://api-staging.example.com')

    print(f'[INFO] API_BASE_URL={API_BASE_URL}')

    status, payload = req('GET', '/health')
    expect(status, {200}, 'health', payload)

    email = random_email()
    register_body = {'email': email, 'password': SMOKE_PASSWORD}
    status, payload = req('POST', '/auth/register', body=register_body, headers={'X-Auth-Mode': 'bearer', 'X-Tenant-Slug': SMOKE_TENANT_SLUG})
    expect(status, {201}, 'register', payload)
    access_token = payload.get('access_token')
    if not access_token:
        fail(f'register did not return access_token: {payload}')

    status, payload = req('GET', '/auth/me', token=access_token)
    expect(status, {200}, 'auth me', payload)

    status, payload = req('POST', '/auth/login', body={'identifier': email, 'password': SMOKE_PASSWORD}, headers={'X-Auth-Mode': 'bearer', 'X-Tenant-Slug': SMOKE_TENANT_SLUG})
    expect(status, {200}, 'login', payload)
    login_token = payload.get('access_token')
    if not login_token:
        fail(f'login did not return access_token: {payload}')

    status, payload = req('POST', '/sessions', token=login_token)
    expect(status, {200}, 'create survey session', payload)
    session_id = payload.get('session_id')
    if not session_id:
        fail(f'create session missing session_id: {payload}')

    status, payload = req('GET', f'/sessions/{session_id}', token=login_token)
    expect(status, {200}, 'get survey session', payload)

    if ADMIN_TOKEN:
        status, payload = req('POST', f'/admin/matches/run-weekly?tenant_slug={urllib.parse.quote(SMOKE_TENANT_SLUG)}', headers={'X-Admin-Token': ADMIN_TOKEN})
        expect(status, {200}, 'admin run-weekly', payload)
    else:
        print('[WARN] ADMIN_TOKEN not set; skipping admin run-weekly smoke step')

    status, payload = req('GET', '/matches/current', token=login_token)
    expect(status, {200}, 'matches current', payload)

    print('[PASS] Stage 2 staging smoke completed')


if __name__ == '__main__':
    random.seed(time.time())
    main()
