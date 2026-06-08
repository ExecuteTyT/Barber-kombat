"""Standalone Vercel-deployable YClients credentials helper.

Single FastAPI app:
- GET  /                          -> HTML form (login + password)
- POST /api/credentials           -> proxies to YClients, returns user_token + companies
- GET  /api/health                -> liveness check

Required env vars (set in Vercel dashboard):
- YCLIENTS_PARTNER_TOKEN          -> your integrator partner token (required)
- YCLIENTS_HELPER_ACCESS_KEY      -> optional shared secret; if set, friend's URL must
                                     include ?key=<value> and the form submits it back

Vercel routes everything through this single function via vercel.json.
"""

import os

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

YCLIENTS_BASE_URL = "https://api.yclients.com/api/v1"

app = FastAPI(title="YClients Credentials Helper", docs_url=None, redoc_url=None)


def _partner_token() -> str:
    token = os.environ.get("YCLIENTS_PARTNER_TOKEN", "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервер не сконфигурирован: отсутствует YCLIENTS_PARTNER_TOKEN",
        )
    return token


def _check_access_key(supplied: str | None) -> None:
    expected = os.environ.get("YCLIENTS_HELPER_ACCESS_KEY", "").strip()
    if not expected:
        return  # access key not configured — endpoint is open
    if (supplied or "").strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверный или отсутствующий ключ доступа",
        )


class CredentialsRequest(BaseModel):
    login: str
    password: str
    access_key: str | None = None


class Company(BaseModel):
    id: int
    title: str
    address: str | None = None


class CredentialsResponse(BaseModel):
    user_token: str
    companies: list[Company]


@app.get("/api/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "partner_token_configured": bool(os.environ.get("YCLIENTS_PARTNER_TOKEN", "").strip()),
        "access_key_required": bool(os.environ.get("YCLIENTS_HELPER_ACCESS_KEY", "").strip()),
    }


@app.post("/api/credentials", response_model=CredentialsResponse)
async def get_credentials(body: CredentialsRequest) -> CredentialsResponse:
    _check_access_key(body.access_key)
    partner_token = _partner_token()

    headers_partner_only = {
        "Authorization": f"Bearer {partner_token}",
        "Accept": "application/vnd.yclients.v2+json",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(base_url=YCLIENTS_BASE_URL, timeout=20.0) as client:
        # Step 1: authenticate user → user_token
        try:
            auth_response = await client.post(
                "/auth",
                headers=headers_partner_only,
                json={"login": body.login, "password": body.password},
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Не удалось связаться с YClients: {e}",
            ) from None

        try:
            auth_payload = auth_response.json()
        except ValueError:
            auth_payload = {}

        auth_data = auth_payload.get("data") or {} if isinstance(auth_payload, dict) else {}
        user_token = auth_data.get("user_token") if isinstance(auth_data, dict) else None

        if not user_token:
            yc_message = (auth_payload.get("meta") or {}).get("message") if isinstance(auth_payload, dict) else None
            if auth_response.status_code in (401, 403, 404) or yc_message:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=yc_message or "Неверный логин или пароль YClients",
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"YClients вернул ошибку {auth_response.status_code}",
            )

        # Step 2: fetch companies user has access to
        headers_full = {
            **headers_partner_only,
            "Authorization": f"Bearer {partner_token}, User {user_token}",
        }
        try:
            companies_response = await client.get(
                "/companies",
                headers=headers_full,
                params={"my": 1},
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Не удалось получить список салонов: {e}",
            ) from None

        if companies_response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"YClients вернул {companies_response.status_code} на /companies",
            )

        companies_data = companies_response.json().get("data") or []
        companies = [
            Company(
                id=item["id"],
                title=item.get("title") or "—",
                address=item.get("address"),
            )
            for item in companies_data
            if isinstance(item, dict) and "id" in item
        ]

    return CredentialsResponse(user_token=user_token, companies=companies)


_HELPER_HTML = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Получить токен YClients</title>
<style>
  *,*::before,*::after { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f5f7; margin: 0; padding: 24px; color: #1a1a1a; min-height: 100vh;
  }
  .card {
    max-width: 520px; margin: 24px auto; background: #fff;
    border-radius: 16px; padding: 28px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 8px 24px rgba(0,0,0,.04);
  }
  h1 { font-size: 22px; margin: 0 0 6px; }
  .sub { color: #666; font-size: 14px; margin-bottom: 22px; line-height: 1.5; }
  label { display: block; font-size: 13px; font-weight: 600; margin: 12px 0 6px; }
  input[type=text], input[type=password] {
    width: 100%; padding: 12px 14px;
    border: 1px solid #d6d6dc; border-radius: 10px;
    font-size: 16px; outline: none; -webkit-appearance: none;
  }
  input:focus { border-color: #0070f3; box-shadow: 0 0 0 3px rgba(0,112,243,.15); }
  button.primary {
    width: 100%; padding: 14px; margin-top: 18px;
    background: #0070f3; color: white; border: none; border-radius: 10px;
    font-size: 16px; font-weight: 600; cursor: pointer;
  }
  button.primary:disabled { background: #999; cursor: wait; }
  .error {
    margin-top: 16px; padding: 12px 14px;
    background: #fde8e8; color: #b91c1c; border-radius: 10px; font-size: 14px;
  }
  .result { margin-top: 22px; }
  .field {
    background: #f1f3f6; border-radius: 10px;
    padding: 12px 14px; margin-bottom: 10px;
    display: flex; align-items: center; gap: 10px;
  }
  .field-label { font-size: 12px; color: #666; font-weight: 600; letter-spacing: .04em; }
  .field-value {
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 13px; word-break: break-all; margin-top: 4px;
  }
  .copy-btn {
    padding: 8px 14px; font-size: 13px; font-weight: 600;
    background: #1a1a1a; color: white; border: none; border-radius: 8px;
    cursor: pointer; white-space: nowrap;
  }
  .copy-btn.copied { background: #0a8845; }
  .companies-title {
    margin: 18px 0 8px;
    font-size: 13px; font-weight: 600; color: #666; letter-spacing: .04em;
  }
  .company { background: #f1f3f6; border-radius: 10px; padding: 12px 14px; margin-bottom: 8px; }
  .company-title { font-weight: 600; font-size: 15px; }
  .company-meta { color: #666; font-size: 13px; margin: 2px 0 8px; }
  .company-id-row {
    display: flex; align-items: center; gap: 10px;
    background: #fff; border-radius: 8px; padding: 8px 10px;
  }
  .company-id { font-family: ui-monospace, monospace; font-size: 14px; flex: 1; }
  .help { font-size: 12px; color: #888; margin-top: 18px; line-height: 1.5; }
  .badge {
    display: inline-block; padding: 2px 8px; margin-left: 8px;
    background: #fff3cd; color: #856404; border-radius: 6px;
    font-size: 11px; font-weight: 600;
  }
</style>
</head>
<body>
  <div class="card">
    <h1>Получить токен YClients</h1>
    <div class="sub">Введите логин и пароль от вашего аккаунта YClients — получите ваш <b>user_token</b> и <b>ID салона</b>.</div>

    <form id="form">
      <label for="login">Логин (e-mail или телефон)</label>
      <input id="login" name="login" type="text" autocomplete="username" required>

      <label for="password">Пароль</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required>

      <button type="submit" class="primary" id="submit">Получить</button>
    </form>

    <div id="error" class="error" style="display:none"></div>
    <div id="result" class="result" style="display:none"></div>

    <div class="help">
      Логин и пароль не сохраняются — используются один раз, чтобы YClients выдал ваш персональный токен. Токен можно отозвать в YClients, сменив пароль.
    </div>
  </div>

<script>
(function () {
  const form = document.getElementById('form');
  const submit = document.getElementById('submit');
  const errorEl = document.getElementById('error');
  const resultEl = document.getElementById('result');

  // Pull access key from URL ?key=...
  const accessKey = new URLSearchParams(window.location.search).get('key') || '';

  function esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function bindCopy(btn) {
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        const orig = btn.textContent;
        btn.textContent = 'Скопировано';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = orig; btn.classList.remove('copied'); }, 1500);
      } catch (_) {
        alert('Не удалось скопировать. Выделите текст вручную.');
      }
    });
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.style.display = 'none';
    resultEl.style.display = 'none';
    submit.disabled = true;
    submit.textContent = 'Загружаем...';

    try {
      const res = await fetch('/api/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          login: document.getElementById('login').value.trim(),
          password: document.getElementById('password').value,
          access_key: accessKey,
        }),
      });

      if (!res.ok) {
        let msg = 'Ошибка ' + res.status;
        try { const j = await res.json(); if (j.detail) msg = j.detail; } catch (_) {}
        throw new Error(msg);
      }

      const data = await res.json();
      const companiesHtml = data.companies.length
        ? data.companies.map(c => `
          <div class="company">
            <div class="company-title">${esc(c.title)}</div>
            ${c.address ? `<div class="company-meta">${esc(c.address)}</div>` : ''}
            <div class="company-id-row">
              <div class="company-id">ID: <b>${c.id}</b></div>
              <button class="copy-btn" data-copy="${c.id}">Копировать ID</button>
            </div>
          </div>`).join('')
        : '<div class="company">На этом аккаунте нет салонов</div>';

      resultEl.innerHTML = `
        <div class="field">
          <div style="flex:1; min-width:0">
            <div class="field-label">USER_TOKEN</div>
            <div class="field-value">${esc(data.user_token)}</div>
          </div>
          <button class="copy-btn" data-copy="${esc(data.user_token)}">Копировать</button>
        </div>
        <div class="companies-title">Ваши салоны:</div>
        ${companiesHtml}
      `;
      resultEl.style.display = 'block';
      resultEl.querySelectorAll('.copy-btn').forEach(bindCopy);
    } catch (err) {
      errorEl.textContent = err.message || 'Что-то пошло не так';
      errorEl.style.display = 'block';
    } finally {
      submit.disabled = false;
      submit.textContent = 'Получить';
    }
  });
})();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return HTMLResponse(content=_HELPER_HTML)
