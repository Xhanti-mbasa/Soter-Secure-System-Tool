import asyncio
import html
import json
from collections import Counter
from datetime import datetime, timezone

from celery.result import AsyncResult
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from secure.auth import require_api_key
from secure.config import get_settings
from secure.db import Base, engine, get_db
from secure.models import Asset, Finding, Scan, ScanStatus
from secure.schemas import FindingRead, ScanCreate, ScanRead
from secure.scan.target_policy import TargetRejected, validate_target
from secure.tasks import celery_app, run_scan_task

app = FastAPI(title="Secure API", version="0.1.0", docs_url="/docs", openapi_url="/api/v1/openapi.json")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)
    get_settings().artifact_root.mkdir(parents=True, exist_ok=True)


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


@app.post("/api/v1/scans", response_model=ScanRead, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
def create_scan(payload: ScanCreate, db: Session = Depends(get_db)) -> Scan:
    if not payload.authorization.confirmed:
        raise HTTPException(status_code=400, detail="Explicit authorization confirmation is required")
    if payload.profile != "quick":
        raise HTTPException(status_code=403, detail="Verified scans require completed ownership verification and are not enabled in this build")
    try:
        target = validate_target(str(payload.target), get_settings().dev_allow_private_targets)
    except TargetRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    scan = Scan(target=target.url, hostname=target.hostname, profile=payload.profile, status=ScanStatus.QUEUED.value, authorization_record=payload.authorization.model_dump())
    db.add(scan)
    db.commit()
    db.refresh(scan)
    task = run_scan_task.delay(scan.id)
    scan.celery_task_id = task.id
    db.commit()
    db.refresh(scan)
    return scan


@app.get("/api/v1/scans/{scan_id}", response_model=ScanRead, dependencies=[Depends(require_api_key)])
def get_scan(scan_id: str, db: Session = Depends(get_db)) -> Scan:
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@app.delete("/api/v1/scans/{scan_id}", status_code=202, dependencies=[Depends(require_api_key)])
def cancel_scan(scan_id: str, db: Session = Depends(get_db)) -> dict:
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status in {ScanStatus.COMPLETED.value, ScanStatus.FAILED.value, ScanStatus.CANCELLED.value}:
        return {"id": scan.id, "status": scan.status}
    if scan.celery_task_id:
        AsyncResult(scan.celery_task_id, app=celery_app).revoke(terminate=True, signal="SIGTERM")
    scan.status = ScanStatus.CANCELLED.value
    scan.finished_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": scan.id, "status": scan.status}


@app.get("/api/v1/scans/{scan_id}/findings", response_model=list[FindingRead], dependencies=[Depends(require_api_key)])
def findings(scan_id: str, db: Session = Depends(get_db)) -> list[Finding]:
    if not db.get(Scan, scan_id):
        raise HTTPException(status_code=404, detail="Scan not found")
    return list(db.scalars(select(Finding).where(Finding.scan_id == scan_id)))


@app.get("/api/v1/scans/{scan_id}/assets", dependencies=[Depends(require_api_key)])
def assets(scan_id: str, db: Session = Depends(get_db)) -> list[dict]:
    if not db.get(Scan, scan_id):
        raise HTTPException(status_code=404, detail="Scan not found")
    return [{"id": x.id, "hostname": x.hostname, "url": x.url, "metadata": x.metadata_} for x in db.scalars(select(Asset).where(Asset.scan_id == scan_id))]


@app.get("/api/v1/scans/{scan_id}/events", dependencies=[Depends(require_api_key)])
async def events(scan_id: str) -> StreamingResponse:
    async def stream():
        last = None
        while True:
            with Session(engine) as db:
                scan = db.get(Scan, scan_id)
                current = scan.status if scan else "NOT_FOUND"
            if current != last:
                yield f"event: stage\ndata: {json.dumps({'type': 'stage.changed', 'stage': current})}\n\n"
                last = current
            if current in {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "NOT_FOUND"}:
                break
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/v1/scans/{scan_id}/report", dependencies=[Depends(require_api_key)])
def report(scan_id: str, format: str = "json", db: Session = Depends(get_db)) -> Response:
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    items = list(db.scalars(select(Finding).where(Finding.scan_id == scan_id)))
    counts = Counter(x.severity for x in items)
    payload = {"scan": ScanRead.model_validate(scan).model_dump(mode="json"), "severity_counts": counts, "findings": [FindingRead.model_validate(x).model_dump() for x in items]}
    if format == "json":
        return Response(json.dumps(payload, default=str, indent=2), media_type="application/json")
    if format != "html":
        raise HTTPException(status_code=400, detail="format must be json or html")
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(x.severity.upper())}</td>"
        f"<td>{html.escape(x.title)}</td>"
        f"<td>{html.escape(x.affected_url)}</td>"
        f"<td>{html.escape(x.remediation)}</td>"
        "</tr>"
        for x in items
    )
    document = f"""<!doctype html><html><head><meta charset='utf-8'><title>Secure report</title><style>body{{font:16px system-ui;background:#111827;color:#e5e7eb;max-width:1100px;margin:40px auto}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #374151;text-align:left}}code{{font-family:monospace}}</style></head><body><h1>Security assessment: <code>{html.escape(scan.hostname)}</code></h1><p>Status: {html.escape(scan.status)} · Posture score: {scan.summary.get('posture_score', 'pending')}/100</p><p>This report contains automated observations, not a certification or penetration-test guarantee.</p><h2>Findings</h2><table><thead><tr><th>Severity</th><th>Finding</th><th>URL</th><th>Remediation</th></tr></thead><tbody>{rows}</tbody></table></body></html>"""
    return HTMLResponse(document)
