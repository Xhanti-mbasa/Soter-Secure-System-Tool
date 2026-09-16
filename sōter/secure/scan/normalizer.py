import hashlib
from urllib.parse import urlsplit


SEVERITIES = {"informational": "info", "info": "info", "low": "low", "medium": "medium", "high": "high", "critical": "critical"}


def fingerprint(category: str, url: str, cwe: str | None = None, parameter: str | None = None) -> str:
    parsed = urlsplit(url)
    value = "|".join([category.lower(), parsed.hostname or "", parsed.path or "/", parameter or "", cwe or ""])
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_nuclei(record: dict) -> dict:
    info = record.get("info") or {}
    classification = info.get("classification") or {}
    url = record.get("matched-at") or record.get("url") or record.get("host") or ""
    rule = record.get("template-id") or "unknown"
    category = ",".join(info.get("tags") or []) or rule
    cwe_values = classification.get("cwe-id") or []
    cwe = cwe_values[0] if isinstance(cwe_values, list) and cwe_values else None
    return {
        "source": "nuclei", "source_rule_id": rule, "title": info.get("name") or rule,
        "severity": SEVERITIES.get(str(info.get("severity", "info")).lower(), "info"),
        "confidence": "medium", "affected_url": url, "category": category, "cwe": cwe,
        "owasp": None, "summary": info.get("description") or "Nuclei observed a matching security template.",
        "evidence": [{"scanner": "nuclei", "matcher": record.get("matcher-name"), "extracted": record.get("extracted-results", [])}],
        "remediation": info.get("remediation") or "Review the evidence and remediate the underlying exposed or vulnerable component.",
        "references": info.get("reference") or [], "fingerprint": fingerprint(category, url, cwe), "status": "signal",
    }


def normalize_zap(record: dict) -> dict:
    url = record.get("url") or ""
    rule = str(record.get("pluginId") or record.get("alertRef") or "unknown")
    category = f"zap-{rule}"
    severity = {"0": "info", "1": "low", "2": "medium", "3": "high", "4": "critical"}.get(str(record.get("riskcode")), "info")
    confidence = {"0": "low", "1": "low", "2": "medium", "3": "high", "4": "confirmed"}.get(str(record.get("confidence")), "medium")
    cwe = f"CWE-{record['cweid']}" if str(record.get("cweid", "-1")) not in {"", "-1", "0"} else None
    return {
        "source": "zap", "source_rule_id": rule, "title": record.get("alert") or "ZAP observation",
        "severity": severity, "confidence": confidence, "affected_url": url, "category": category,
        "cwe": cwe, "owasp": None, "summary": record.get("description") or "ZAP reported a passive scan observation.",
        "evidence": [{"scanner": "zap", "evidence": record.get("evidence"), "parameter": record.get("param")}],
        "remediation": record.get("solution") or "Review and remediate the observed condition.",
        "references": [x for x in str(record.get("reference") or "").splitlines() if x],
        "fingerprint": fingerprint(category, url, cwe, record.get("param")), "status": "signal",
    }
