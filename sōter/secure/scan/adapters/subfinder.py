from secure.scan.adapters.base import ScannerAdapter, ToolRun
from secure.scan.context import ScanContext


class SubfinderAdapter(ScannerAdapter):
    name = "subfinder"
    timeout_seconds = 30

    async def run(self, context: ScanContext) -> ToolRun:
        path = context.artifact_dir / "subfinder" / "stdout.jsonl"
        return await self.execute([self.name, "-d", context.hostname, "-silent", "-json"], path)

    def parse(self, run: ToolRun) -> list[dict]:
        return self.jsonl(run.output_path)
