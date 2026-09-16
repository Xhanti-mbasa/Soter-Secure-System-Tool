from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScanContext:
    scan_id: str
    target: str
    hostname: str
    profile: str
    artifact_dir: Path
    live_urls: list[str] = field(default_factory=list)
    endpoints: list[str] = field(default_factory=list)
