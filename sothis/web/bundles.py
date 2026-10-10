import hashlib
import io
import json
import re
import zipfile


def evidence_bundle(root, data):
    """Package selected archive objects, retaining missing-original provenance."""
    evidence = data.get('evidence', [])
    if not isinstance(evidence, list) or len(evidence) > 50:
        raise ValueError('Choose up to 50 archived originals per bundle.')
    output, total, included, missing = io.BytesIO(), 0, [], []
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        seen = set()
        for item in evidence:
            if not isinstance(item, dict) or not re.fullmatch(r'[a-f0-9]{64}', str(item.get('sha256', ''))):
                raise ValueError('Invalid archive object hash.')
            sha = item['sha256']
            if sha in seen:
                continue
            seen.add(sha)
            file = root / 'archive' / sha
            if not file.is_file() or file.is_symlink():
                missing.append(item)
                continue
            total += file.stat().st_size
            if total > 32 * 1024 * 1024:
                raise ValueError('Split archives larger than 32 MiB into separate bundles.')
            raw = file.read_bytes()
            if hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError('Archived original failed its hash check.')
            name = 'originals/' + sha + '.bin'
            archive.writestr(name, raw)
            included.append({**item, 'bundle_path': name})
        manifest = {**data, 'evidence': included, 'unavailable_originals': missing}
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr('report.md', str(data.get('report', '')))
    return output.getvalue()
