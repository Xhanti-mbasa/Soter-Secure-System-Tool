from secure.scan.adapters.base import ScannerAdapter, ToolRun
from secure.scan.context import ScanContext


class HttpxAdapter(ScannerAdapter):
    name = "httpx"
    timeout_seconds = 30

    async def run(self, context: ScanContext, hosts: list[str] | None = None) -> ToolRun:
        path = context.artifact_dir / "httpx" / "results.jsonl"
        values = hosts or [context.hostname]
        command = [self.name, "-silent", "-json", "-status-code", "-title", "-server", "-tech-detect", "-ip", "-cname", "-tls-grab", "-rl", "5", "-threads", "2"]
        return await self.execute(command, path, ("\n".join(values) + "\n").encode())

    def parse(self, run: ToolRun) -> list[dict]:
        return self.jsonl(run.output_path)
