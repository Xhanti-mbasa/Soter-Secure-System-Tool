WEIGHTS = {"critical": 25, "high": 12, "medium": 5, "low": 2, "info": 0}


def posture_score(findings: list[dict]) -> int:
    charged: set[tuple[str, str]] = set()
    deduction = 0
    for item in findings:
        asset = item.get("affected_url", "").split("/", 3)[:3]
        key = (item.get("source_rule_id") or item.get("category") or item["title"], "/".join(asset))
        if key not in charged:
            deduction += WEIGHTS.get(item.get("severity", "info"), 0)
            charged.add(key)
    return max(0, 100 - deduction)
