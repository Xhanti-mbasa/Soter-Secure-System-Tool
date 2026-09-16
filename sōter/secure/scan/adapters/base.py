import asyncio
import hashlib
import json
import os
import signal
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from secure.scan.context import ScanContext


@dataclass
class ToolRun:
    tool: str
    version: str
    command: list[str]
    output_path: Path
    exit_code: int
    stderr: str
    binary_hash: str | None = None
    records: list[dict] = field(default_factory=list)


class ScannerAdapter(ABC):
    name: str
    timeout_seconds: int

    async def version(self) -> str:
        process = await asyncio.create_subprocess_exec(
            self.name, "-version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
        return stdout.decode(errors="replace").strip()[:300]

    @abstractmethod
    async def run(self, context: ScanContext) -> ToolRun: ...

    @abstractmethod
    def parse(self, run: ToolRun) -> list[dict]: ...

    async def execute(self, command: list[str], output_path: Path, stdin: bytes | None = None) -> ToolRun:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(stdin), self.timeout_seconds)
        except TimeoutError:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), 5)
            except TimeoutError:
                os.killpg(process.pid, signal.SIGKILL)
            raise
        output_path.write_bytes(stdout)
        binary = Path(f"/usr/local/bin/{self.name}")
        digest = hashlib.sha256(binary.read_bytes()).hexdigest() if binary.exists() else None
        version = await self.version()
        run = ToolRun(self.name, version, command, output_path, process.returncode, stderr.decode(errors="replace"), digest)
        if process.returncode != 0:
            raise RuntimeError(f"{self.name} exited with {process.returncode}: {run.stderr[-1000:]}")
        return run

    @staticmethod
    def jsonl(path: Path) -> list[dict]:
        records = []
        for line in path.read_text(errors="replace").splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records
