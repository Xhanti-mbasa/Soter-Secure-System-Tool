import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select

from secure.config import get_settings
from secure.db import SessionLocal
from secure.models import Asset, Finding, Scan, ScanStatus
from secure.scan.adapters import HttpxAdapter, KatanaAdapter, NucleiAdapter, SubfinderAdapter, ZapAdapter
from secure.scan.context import ScanContext
from secure.scan.normalizer import normalize_nuclei, normalize_zap
from secure.scan.scoring import posture_score
from secure.scan.target_policy import validate_target


def set_status(scan_id: str, status: ScanStatus) -> None:
    with SessionLocal.begin() as db:
        scan = db.get(Scan, scan_id)
        if scan:
            scan.status = status.value
            if status == ScanStatus.VALIDATING:
                scan.started_at = datetime.now(timezone.utc)


def save_assets(scan_id: str, records: list[dict]) -> list[str]:
    hosts: list[str] = []
    with SessionLocal.begin() as db:
        for record in records:
            host = record.get("host") or record.get("input")
            if host and host not in hosts:
                db.add(Asset(scan_id=scan_id, hostname=host, metadata_=record))
                hosts.append(host)
    return hosts


def save_live_assets(scan_id: str, records: list[dict]) -> list[str]:
    urls: list[str] = []
    with SessionLocal.begin() as db:
        for record in records:
            url = record.get("url")
            if not url:
                continue
            urls.append(url)
            host = record.get("host") or record.get("input") or url
            db.add(Asset(scan_id=scan_id, hostname=host, url=url, metadata_=record))
    return list(dict.fromkeys(urls))


def save_findings(scan_id: str, items: list[dict]) -> int:
    with SessionLocal.begin() as db:
        existing = {f.fingerprint: f for f in db.scalars(select(Finding).where(Finding.scan_id == scan_id))}
        for item in items:
            if item["fingerprint"] in existing:
                current = existing[item["fingerprint"]]
                current.evidence = [*current.evidence, *item["evidence"]]
                continue
            finding = Finding(scan_id=scan_id, **item)
            db.add(finding)
            existing[item["fingerprint"]] = finding
    return len(existing)


async def run_scan(scan_id: str) -> None:
    settings = get_settings()
    failures: list[str] = []
    with SessionLocal() as db:
        scan = db.get(Scan, scan_id)
        if not scan:
            return
        target, hostname, profile = scan.target, scan.hostname, scan.profile
    artifact_dir = settings.artifact_root / scan_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    context = ScanContext(scan_id, target, hostname, profile, artifact_dir)
    manifest: dict = {"scan_id": scan_id, "target": target, "tools": [], "failures": failures}
    try:
        set_status(scan_id, ScanStatus.VALIDATING)
        validate_target(target, settings.dev_allow_private_targets)

        set_status(scan_id, ScanStatus.DISCOVERING)
        try:
            adapter = SubfinderAdapter()
            run = await adapter.run(context)
            hosts = save_assets(scan_id, adapter.parse(run))
            manifest["tools"].append(vars(run) | {"output_path": str(run.output_path), "records": []})
        except Exception as exc:
            failures.append(f"subfinder: {exc}")
            hosts = [hostname]

        set_status(scan_id, ScanStatus.PROBING)
        try:
            adapter = HttpxAdapter()
            run = await adapter.run(context, list(dict.fromkeys([hostname, *hosts])))
            context.live_urls = save_live_assets(scan_id, adapter.parse(run))
            manifest["tools"].append(vars(run) | {"output_path": str(run.output_path), "records": []})
        except Exception as exc:
            failures.append(f"httpx: {exc}")
            context.live_urls = [target]

        set_status(scan_id, ScanStatus.CRAWLING)
        try:
            adapter = KatanaAdapter()
            run = await adapter.run(context)
            context.endpoints = [r.get("request", {}).get("endpoint") or r.get("url") for r in adapter.parse(run)]
            context.endpoints = [x for x in context.endpoints if x][:500]
            manifest["tools"].append(vars(run) | {"output_path": str(run.output_path), "records": []})
        except Exception as exc:
            failures.append(f"katana: {exc}")

        normalized: list[dict] = []
        set_status(scan_id, ScanStatus.PASSIVE_SCANNING)
        try:
            adapter = ZapAdapter()
            run = await adapter.run(context)
            normalized.extend(normalize_zap(x) for x in adapter.parse(run))
            manifest["tools"].append(vars(run) | {"output_path": str(run.output_path), "records": []})
        except Exception as exc:
            failures.append(f"zap: {exc}")

        set_status(scan_id, ScanStatus.VULNERABILITY_SCANNING)
        try:
            adapter = NucleiAdapter()
            run = await adapter.run(context)
            normalized.extend(normalize_nuclei(x) for x in adapter.parse(run))
            manifest["tools"].append(vars(run) | {"output_path": str(run.output_path), "records": []})
        except Exception as exc:
            failures.append(f"nuclei: {exc}")

        set_status(scan_id, ScanStatus.NORMALIZING)
        count = save_findings(scan_id, normalized)
        summary = {
            "assets_discovered": len(hosts), "live_websites": len(context.live_urls),
            "endpoints_crawled": len(context.endpoints), "findings": count,
            "posture_score": posture_score(normalized), "failed_stages": failures,
            "disclaimer": "Automated observations only; not a certification or penetration-test guarantee.",
        }
        set_status(scan_id, ScanStatus.REPORTING)
        with SessionLocal.begin() as db:
            scan = db.get(Scan, scan_id)
            scan.summary = summary
            scan.status = (ScanStatus.PARTIAL if failures else ScanStatus.COMPLETED).value
            scan.finished_at = datetime.now(timezone.utc)
        manifest["summary"] = summary
    except asyncio.CancelledError:
        set_status(scan_id, ScanStatus.CANCELLED)
        raise
    except Exception as exc:
        failures.append(f"pipeline: {exc}")
        with SessionLocal.begin() as db:
            scan = db.get(Scan, scan_id)
            if scan:
                scan.status = ScanStatus.FAILED.value
                scan.finished_at = datetime.now(timezone.utc)
                scan.summary = {"failed_stages": failures}
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
