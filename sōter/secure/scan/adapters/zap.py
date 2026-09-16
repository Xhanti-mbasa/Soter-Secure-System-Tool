import asyncio
import json

import httpx

from secure.config import get_settings
from secure.scan.adapters.base import ScannerAdapter, ToolRun
from secure.scan.context import ScanContext


class ZapAdapter(ScannerAdapter):
    name = "zap"
    timeout_seconds = 120

    async def version(self) -> str:
        settings = get_settings()
        async with httpx.AsyncClient(base_url=settings.zap_api_url, timeout=10) as client:
            response = await client.get("/JSON/core/view/version/", params={"apikey": settings.zap_api_key})
            response.raise_for_status()
            return response.json().get("version", "unknown")

    async def run(self, context: ScanContext) -> ToolRun:
        settings = get_settings()
        output = context.artifact_dir / "zap" / "report.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(base_url=settings.zap_api_url, timeout=15) as client:
            params = {"apikey": settings.zap_api_key, "url": context.target, "maxChildren": 500, "recurse": "true"}
            response = await client.get("/JSON/spider/action/scan/", params=params)
            response.raise_for_status()
            scan_id = response.json()["scan"]
            for _ in range(self.timeout_seconds // 2):
                await asyncio.sleep(2)
                state = await client.get("/JSON/spider/view/status/", params={"apikey": settings.zap_api_key, "scanId": scan_id})
                if int(state.json().get("status", 0)) >= 100:
                    break
            else:
                await client.get("/JSON/spider/action/stop/", params={"apikey": settings.zap_api_key, "scanId": scan_id})
                raise TimeoutError("ZAP baseline spider timed out")
            await asyncio.sleep(5)
            report = await client.get("/JSON/core/view/alerts/", params={"apikey": settings.zap_api_key, "baseurl": context.target})
            report.raise_for_status()
        output.write_text(json.dumps(report.json(), indent=2))
        return ToolRun(self.name, await self.version(), ["zap-api", "passive-baseline", context.target], output, 0, "", records=report.json().get("alerts", []))

    def parse(self, run: ToolRun) -> list[dict]:
        return run.records
