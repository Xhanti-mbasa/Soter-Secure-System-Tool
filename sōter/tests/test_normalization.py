from secure.scan.normalizer import normalize_nuclei, normalize_zap
from secure.scan.scoring import posture_score


def test_nuclei_normalization():
    item = normalize_nuclei({"template-id": "missing-csp", "matched-at": "https://example.com/", "info": {"name": "Missing CSP", "severity": "medium", "tags": ["headers"]}})
    assert item["source"] == "nuclei"
    assert item["severity"] == "medium"
    assert len(item["fingerprint"]) == 64


def test_zap_normalization():
    item = normalize_zap({"pluginId": "10038", "alert": "CSP Header Not Set", "url": "https://example.com/", "riskcode": "2", "confidence": "3", "cweid": "693"})
    assert item["severity"] == "medium"
    assert item["confidence"] == "high"
    assert item["cwe"] == "CWE-693"


def test_score_caps_at_zero_and_ignores_info():
    findings = [{"severity": "critical", "source_rule_id": str(i), "affected_url": "https://example.com"} for i in range(5)]
    findings.append({"severity": "info", "source_rule_id": "info", "affected_url": "https://example.com"})
    assert posture_score(findings) == 0
