"""Public helper to fetch YClients credentials (user_token + company list).

Designed for non-technical barbershop owners: friend opens the page, types
their YClients login + password, and receives their personal user_token and
the list of salons (with company_id) attached to that account. Uses the
partner_token configured on this server, so the partner token is never
exposed to the visitor.
"""

import httpx
import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.config import settings
from app.integrations.yclients.client import YCLIENTS_BASE_URL

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/yclients-helper", tags=["yclients-helper"])
html_router = APIRouter(tags=["yclients-helper"])


class CredentialsRequest(BaseModel):
    login: str
    password: str


class Company(BaseModel):
    id: int
    title: str
    address: str | None = None


class CredentialsResponse(BaseModel):
    user_token: str
    companies: list[Company]


@router.post("/credentials", response_model=CredentialsResponse)
async def get_credentials(body: CredentialsRequest) -> CredentialsResponse:
    """Use server's partner_token + user login/password to fetch user_token and companies."""
    if not settings.yclients_partner_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервер не сконфигурирован: отсутствует YClients partner token",
        )

    headers_partner_only = {
        "Authorization": f"Bearer {settings.yclients_partner_token}",
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

        # YClients returns 404 with meta.message="Неверный логин или пароль" on bad creds
        # (not 401), so we lean on the success/data shape rather than HTTP status alone.
        try:
            auth_payload = auth_response.json()
        except ValueError:
            auth_payload = {}

        auth_data = auth_payload.get("data") or {}
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

        # Step 2: fetch companies the user has access to
        headers_full = {
            **headers_partner_only,
            "Authorization": f"Bearer {settings.yclients_partner_token}, User {user_token}",
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

    await logger.ainfo(
        "YClients credentials helper succeeded",
        login=body.login,
        company_count=len(companies),
    )

    return CredentialsResponse(user_token=user_token, companies=companies)


@html_router.get("/yclients-helper", response_class=HTMLResponse)
async def helper_page() -> HTMLResponse:
    """Friendly HTML form for non-technical users to fetch their YClients credentials."""
    return HTMLResponse(content=_HELPER_HTML)


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
    background: #f5f5f7;
    margin: 0; padding: 24px;
    color: #1a1a1a;
    min-height: 100vh;
  }
  .card {
    max-width: 520px;
    margin: 24px auto;
    background: #fff;
    border-radius: 16px;
    padding: 28px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 8px 24px rgba(0,0,0,.04);
  }
  h1 { font-size: 22px; margin: 0 0 6px; }
  .sub { color: #666; font-size: 14px; margin-bottom: 22px; line-height: 1.5; }
  label { display: block; font-size: 13px; font-weight: 600; margin: 12px 0 6px; }
  input[type=text], input[type=password] {
    width: 100%; padding: 12px 14px;
    border: 1px solid #d6d6dc; border-radius: 10px;
    font-size: 16px; outline: none;
    -webkit-appearance: none;
  }
  input:focus { border-color: #0070f3; box-shadow: 0 0 0 3px rgba(0,112,243,.15); }
  button.primary {
    width: 100%; padding: 14px; margin-top: 18px;
    background: #0070f3; color: white;
    border: none; border-radius: 10px;
    font-size: 16px; font-weight: 600; cursor: pointer;
  }
  button.primary:disabled { background: #999; cursor: wait; }
  .error {
    margin-top: 16px; padding: 12px 14px;
    background: #fde8e8; color: #b91c1c;
    border-radius: 10px; font-size: 14px;
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
    font-size: 13px; word-break: break-all;
    margin-top: 4px;
  }
  .copy-btn {
    padding: 8px 14px;
    font-size: 13px; font-weight: 600;
    background: #1a1a1a; color: white;
    border: none; border-radius: 8px;
    cursor: pointer; white-space: nowrap;
  }
  .copy-btn.copied { background: #0a8845; }
  .companies-title {
    margin: 18px 0 8px;
    font-size: 13px; font-weight: 600; color: #666; letter-spacing: .04em;
  }
  .company {
    background: #f1f3f6; border-radius: 10px;
    padding: 12px 14px; margin-bottom: 8px;
  }
  .company-title { font-weight: 600; font-size: 15px; }
  .company-meta { color: #666; font-size: 13px; margin: 2px 0 8px; }
  .company-id-row {
    display: flex; align-items: center; gap: 10px;
    background: #fff; border-radius: 8px; padding: 8px 10px;
  }
  .company-id { font-family: ui-monospace, monospace; font-size: 14px; flex: 1; }
  .help { font-size: 12px; color: #888; margin-top: 18px; line-height: 1.5; }
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
      const res = await fetch('/api/v1/yclients-helper/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          login: document.getElementById('login').value.trim(),
          password: document.getElementById('password').value,
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
