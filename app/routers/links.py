from html import escape
from io import BytesIO
from typing import List, Optional

import qrcode
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app import service
from app.auth import get_current_user, get_optional_user
from app.config import BASE_URL, RATE_LIMIT_PER_MINUTE
from app.database import User, get_db
from app.schemas import (
    AnalyticsResponse,
    BulkShortenRequest,
    BulkShortenResponse,
    ShortenRequest,
    ShortenResponse,
    StatsResponse,
)
from app.service import ResolveStatus

router = APIRouter(tags=["links"])
limiter = Limiter(key_func=get_remote_address)

_RATE = f"{RATE_LIMIT_PER_MINUTE}/minute"

_PASSWORD_FORM = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Protected Link — Snapl</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Plus+Jakarta+Sans:wght@300;400;500&family=JetBrains+Mono:wght@300&display=swap" rel="stylesheet">
<style>
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  :root{{
    --bg:#08090D;--s1:#0D0F15;--s2:#131620;--border:#1F2433;--border-2:#2A3044;
    --text:#E4E8F4;--text-2:#8899BB;--text-3:#3D4A66;
    --accent:#00D9A3;--accent-dim:rgba(0,217,163,0.07);--accent-glow:rgba(0,217,163,0.18);
    --red:#EF6565;
  }}
  html{{height:100%}}
  body{{
    font-family:'Plus Jakarta Sans',system-ui,sans-serif;
    background:var(--bg);color:var(--text);
    min-height:100vh;display:flex;flex-direction:column;
    align-items:center;justify-content:center;padding:24px;
    -webkit-font-smoothing:antialiased;
  }}
  body::before{{
    content:'';position:fixed;inset:0;
    background-image:radial-gradient(circle,var(--border) 1px,transparent 1px);
    background-size:28px 28px;pointer-events:none;z-index:0;
  }}
  body::after{{
    content:'';position:fixed;top:-20%;left:50%;transform:translateX(-50%);
    width:600px;height:400px;
    background:radial-gradient(ellipse,rgba(0,217,163,0.045) 0%,transparent 65%);
    pointer-events:none;z-index:0;
  }}
  .card{{
    position:relative;z-index:1;
    background:var(--s1);border:1px solid var(--border);
    border-radius:14px;padding:36px 32px;width:100%;max-width:380px;
    animation:fadeUp .35s ease;
  }}
  @keyframes fadeUp{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:translateY(0)}}}}
  .logo{{
    font-family:'Syne',sans-serif;font-weight:800;font-size:1.1rem;
    letter-spacing:-0.04em;color:var(--text);text-decoration:none;
    display:flex;align-items:center;gap:8px;margin-bottom:28px;
  }}
  .logo-mark{{
    width:26px;height:26px;background:var(--accent-dim);
    border:1px solid rgba(0,217,163,0.25);border-radius:7px;
    display:flex;align-items:center;justify-content:center;
  }}
  .lock-icon{{
    width:40px;height:40px;background:var(--accent-dim);
    border:1px solid rgba(0,217,163,0.2);border-radius:10px;
    display:flex;align-items:center;justify-content:center;margin-bottom:16px;
  }}
  h1{{font-family:'Syne',sans-serif;font-weight:800;font-size:1.35rem;letter-spacing:-0.03em;margin-bottom:6px}}
  .sub{{font-size:13px;color:var(--text-2);font-weight:300;margin-bottom:24px}}
  label{{
    display:block;font-size:10.5px;font-weight:600;
    letter-spacing:.07em;text-transform:uppercase;
    color:var(--text-3);margin-bottom:6px;
  }}
  input[type=password]{{
    width:100%;background:var(--bg);border:1px solid var(--border);
    border-radius:8px;padding:11px 13px;font-size:14px;color:var(--text);
    font-family:'JetBrains Mono',monospace;font-weight:300;outline:none;
    transition:border-color .15s,box-shadow .15s;
  }}
  input[type=password]:focus{{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-dim)}}
  input::placeholder{{color:var(--text-3)}}
  button{{
    width:100%;margin-top:14px;padding:12px;
    background:var(--accent);color:#040A08;border:none;border-radius:8px;
    font-size:14px;font-weight:600;font-family:'Plus Jakarta Sans',sans-serif;
    cursor:pointer;letter-spacing:-.01em;transition:filter .15s,box-shadow .15s;
  }}
  button:hover{{filter:brightness(1.08);box-shadow:0 0 20px var(--accent-glow)}}
  .err{{
    margin-top:14px;padding:10px 13px;
    background:rgba(239,101,101,.08);border:1px solid rgba(239,101,101,.2);
    border-radius:8px;font-size:13px;color:var(--red);
  }}
  .back{{
    margin-top:20px;text-align:center;font-size:12px;
  }}
  .back a{{color:var(--text-3);text-decoration:none}}
  .back a:hover{{color:var(--text-2)}}
</style>
</head>
<body>
<div class="card">
  <a href="/" class="logo">
    <div class="logo-mark">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#00D9A3" stroke-width="2.5">
        <path d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101"/>
        <path d="M10.172 13.828a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
      </svg>
    </div>
    Snapl
  </a>

  <div class="lock-icon">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00D9A3" stroke-width="2">
      <rect x="3" y="11" width="18" height="11" rx="2"/>
      <path d="M7 11V7a5 5 0 0110 0v4"/>
    </svg>
  </div>

  <h1>Protected link</h1>
  <p class="sub">Enter the password to access this destination.</p>

  <form method="post" action="/{code}/unlock">
    <label>Password</label>
    <input type="password" name="password" placeholder="••••••••" autofocus required>
    <button type="submit">Unlock &rarr;</button>
  </form>
  {error}

  <div class="back"><a href="/">← Back to Snapl</a></div>
</div>
</body>
</html>"""


@router.post("/shorten", response_model=ShortenResponse, status_code=201)
@limiter.limit(_RATE)
def shorten_url(
    request: Request,
    body: ShortenRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        return service.shorten(
            db=db,
            long_url=body.url,
            expiry_days=body.expiry_days,
            custom_alias=body.custom_alias,
            one_time=body.one_time,
            password=body.password,
            starts_at=body.starts_at,
            user_id=current_user.id if current_user else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/bulk", response_model=BulkShortenResponse)
def bulk_shorten(
    body: BulkShortenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if len(body.urls) > 500:
        raise HTTPException(status_code=400, detail="Maximum 500 URLs per request")
    results = []
    for item in body.urls:
        try:
            resp = service.shorten(
                db=db,
                long_url=item.url,
                expiry_days=item.expiry_days,
                custom_alias=item.custom_alias,
                one_time=False,
                password=None,
                starts_at=None,
                user_id=current_user.id,
            )
            results.append(resp)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    return BulkShortenResponse(results=results)


@router.get("/my-links", response_model=List[StatsResponse])
def my_links(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.my_links(db, current_user.id)


@router.delete("/my-links/{short_code}", status_code=204)
def delete_link(
    short_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not service.delete_link(db, short_code, current_user.id):
        raise HTTPException(status_code=404, detail="Link not found or not owned by you")


@router.get("/stats/{short_code}", response_model=StatsResponse)
def get_stats(short_code: str, db: Session = Depends(get_db)):
    result = service.stats(db, short_code)
    if result is None:
        raise HTTPException(status_code=404, detail="Short code not found")
    return result


@router.get("/analytics/{short_code}", response_model=AnalyticsResponse)
def get_analytics(
    short_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.database import URLRecord
    record = db.query(URLRecord).filter(URLRecord.short_code == short_code).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Short code not found")
    if record.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    result = service.analytics(db, short_code)
    if result is None:
        raise HTTPException(status_code=404, detail="Short code not found")
    return result


@router.get("/qr/{short_code}")
def get_qr(short_code: str, db: Session = Depends(get_db)):
    from app.database import URLRecord
    record = db.query(URLRecord).filter(URLRecord.short_code == short_code).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Short code not found")
    short_url = f"{BASE_URL}/{short_code}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(short_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.get("/{short_code}")
@limiter.limit(_RATE)
def redirect(
    request: Request,
    short_code: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    result = service.resolve(db, short_code)

    if result.status == ResolveStatus.NOT_FOUND:
        raise HTTPException(status_code=404, detail="Short code not found")

    if result.status == ResolveStatus.EXPIRED:
        return HTMLResponse(
            "<h2>Link expired</h2><p>This short link has expired.</p>",
            status_code=410,
        )

    if result.status == ResolveStatus.NOT_ACTIVE:
        raise HTTPException(status_code=404, detail="Link not yet active")

    if result.status == ResolveStatus.PASSWORD_REQUIRED:
        return HTMLResponse(_PASSWORD_FORM.format(code=escape(short_code), error=""))

    # Queue geo/device analytics without blocking the redirect
    if result.record_id:
        background_tasks.add_task(
            service.log_click_event,
            result.record_id,
            get_remote_address(request),
            request.headers.get("user-agent", ""),
            request.headers.get("referer", ""),
        )

    return RedirectResponse(url=result.long_url, status_code=302)


@router.post("/{short_code}/unlock")
@limiter.limit(_RATE)
async def unlock(
    request: Request,
    short_code: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        password = body.get("password", "")
    else:
        form = await request.form()
        password = form.get("password", "")

    result = service.unlock(db, short_code, password)

    if result.status == ResolveStatus.NOT_FOUND:
        raise HTTPException(status_code=404, detail="Short code not found")
    if result.status == ResolveStatus.EXPIRED:
        return HTMLResponse(
            "<h2>Link expired</h2><p>This short link has expired.</p>",
            status_code=410,
        )
    if result.status == ResolveStatus.PASSWORD_REQUIRED:
        return HTMLResponse(
            _PASSWORD_FORM.format(code=escape(short_code), error='<p class="err">Wrong password.</p>'),
            status_code=401,
        )

    if result.record_id:
        background_tasks.add_task(
            service.log_click_event,
            result.record_id,
            get_remote_address(request),
            request.headers.get("user-agent", ""),
            request.headers.get("referer", ""),
        )

    return RedirectResponse(url=result.long_url, status_code=302)
