from secure.scan.adapters.base import ScannerAdapter, ToolRun
from secure.scan.context import ScanContext


class KatanaAdapter(ScannerAdapter):
    name = "katana"
    timeout_seconds = 60

    async def run(self, context: ScanContext) -> ToolRun:
        path = context.artifact_dir / "katana" / "results.jsonl"
        command = [self.name, "-u", context.target, "-silent", "-jsonl", "-d", "2", "-jc", "-kf", "robotstxt,sitemapxml", "-fs", "rdn", "-rl", "5", "-c", "2", "-timeout", "10"]
        return await self.execute(command, path)

    def parse(self, run: ToolRun) -> list[dict]:
        return self.jsonl(run.output_path)[:500]
