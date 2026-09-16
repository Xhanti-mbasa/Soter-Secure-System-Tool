from secure.scan.adapters.base import ScannerAdapter, ToolRun
from secure.scan.context import ScanContext


class NucleiAdapter(ScannerAdapter):
    name = "nuclei"
    timeout_seconds = 90

    async def run(self, context: ScanContext) -> ToolRun:
        path = context.artifact_dir / "nuclei" / "results.jsonl"
        command = [self.name, "-silent", "-jsonl", "-severity", "info,low,medium,high,critical", "-exclude-tags", "fuzz,dos,bruteforce,intrusive,headless,code", "-rl", "5", "-c", "2", "-bulk-size", "2"]
        values = context.live_urls or [context.target]
        return await self.execute(command, path, ("\n".join(values) + "\n").encode())

    def parse(self, run: ToolRun) -> list[dict]:
        return self.jsonl(run.output_path)
