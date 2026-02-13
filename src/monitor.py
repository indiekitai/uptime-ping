"""
Monitor - Check endpoint health
"""
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import httpx


class Status(str, Enum):
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"  # Slow but responding


@dataclass
class CheckResult:
    url: str
    status: Status
    status_code: int | None
    response_time_ms: float
    error: str | None
    checked_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_healthy(self) -> bool:
        return self.status == Status.UP


@dataclass
class Endpoint:
    url: str
    name: str | None = None
    expected_status: int = 200
    timeout_ms: int = 10000  # 10 seconds
    degraded_threshold_ms: int = 3000  # 3 seconds = degraded
    
    @property
    def display_name(self) -> str:
        return self.name or self.url


async def check_endpoint(endpoint: Endpoint) -> CheckResult:
    """Check a single endpoint's health."""
    start = time.perf_counter()
    
    try:
        async with httpx.AsyncClient(timeout=endpoint.timeout_ms / 1000) as client:
            resp = await client.get(endpoint.url)
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            if resp.status_code == endpoint.expected_status:
                if elapsed_ms > endpoint.degraded_threshold_ms:
                    status = Status.DEGRADED
                else:
                    status = Status.UP
            else:
                status = Status.DOWN
            
            return CheckResult(
                url=endpoint.url,
                status=status,
                status_code=resp.status_code,
                response_time_ms=round(elapsed_ms, 2),
                error=None if status != Status.DOWN else f"Expected {endpoint.expected_status}, got {resp.status_code}",
            )
    
    except httpx.TimeoutException:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return CheckResult(
            url=endpoint.url,
            status=Status.DOWN,
            status_code=None,
            response_time_ms=round(elapsed_ms, 2),
            error="Timeout",
        )
    
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return CheckResult(
            url=endpoint.url,
            status=Status.DOWN,
            status_code=None,
            response_time_ms=round(elapsed_ms, 2),
            error=str(e),
        )


async def check_all(endpoints: list[Endpoint]) -> list[CheckResult]:
    """Check all endpoints in parallel."""
    tasks = [check_endpoint(ep) for ep in endpoints]
    return await asyncio.gather(*tasks)


if __name__ == "__main__":
    # Quick test
    async def main():
        endpoints = [
            Endpoint(url="https://httpbin.org/status/200", name="httpbin-ok"),
            Endpoint(url="https://httpbin.org/status/500", name="httpbin-500"),
            Endpoint(url="https://httpbin.org/delay/5", name="httpbin-slow", degraded_threshold_ms=2000),
        ]
        
        results = await check_all(endpoints)
        for r in results:
            emoji = "✅" if r.status == Status.UP else "⚠️" if r.status == Status.DEGRADED else "❌"
            print(f"{emoji} {r.url}: {r.status.value} ({r.response_time_ms}ms)")
            if r.error:
                print(f"   Error: {r.error}")
    
    asyncio.run(main())
