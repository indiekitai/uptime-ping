"""
Uptime Ping - API Server with scheduled monitoring
"""
import os
import json
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .monitor import Endpoint, check_all, CheckResult, Status
from .storage import save_checks, track_incident, get_status_summary, calculate_uptime, load_recent_checks
from .notifier import notify_incident

load_dotenv()

# Config
CONFIG_FILE = Path(os.getenv("UPTIME_CONFIG", "/root/source/side-projects/uptime-ping/config.json"))
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL", "60"))  # Default: 1 minute

# Global state
scheduler = AsyncIOScheduler()
endpoints: list[Endpoint] = []


def load_config():
    """Load endpoints from config file."""
    global endpoints
    
    if not CONFIG_FILE.exists():
        # Create default config
        default = {
            "endpoints": [
                {"url": "https://httpbin.org/status/200", "name": "httpbin-test"},
            ],
            "check_interval_seconds": 60,
        }
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(default, indent=2))
    
    config = json.loads(CONFIG_FILE.read_text())
    
    endpoints = [
        Endpoint(
            url=ep["url"],
            name=ep.get("name"),
            expected_status=ep.get("expected_status", 200),
            timeout_ms=ep.get("timeout_ms", 10000),
            degraded_threshold_ms=ep.get("degraded_threshold_ms", 3000),
        )
        for ep in config.get("endpoints", [])
    ]
    
    return config


async def run_checks():
    """Run health checks on all endpoints."""
    if not endpoints:
        return
    
    print(f"🔍 Running health checks on {len(endpoints)} endpoints...")
    results = await check_all(endpoints)
    
    # Save results
    save_checks(results)
    
    # Check for incidents and notify
    for result in results:
        incident = track_incident(result)
        if incident:
            print(f"🚨 Incident detected: {result.url} {incident['prev_status']} -> {incident['new_status']}")
            await notify_incident(incident)
    
    # Log summary
    up = sum(1 for r in results if r.status == Status.UP)
    down = sum(1 for r in results if r.status == Status.DOWN)
    degraded = sum(1 for r in results if r.status == Status.DEGRADED)
    print(f"✅ Check complete: {up} up, {down} down, {degraded} degraded")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Uptime Ping starting...")
    load_config()
    print(f"📋 Loaded {len(endpoints)} endpoints")
    
    # Run initial check
    await run_checks()
    
    # Start scheduler
    scheduler.add_job(
        run_checks,
        trigger=IntervalTrigger(seconds=CHECK_INTERVAL_SECONDS),
        id="health_check",
        replace_existing=True,
    )
    scheduler.start()
    print(f"⏰ Scheduler started (interval: {CHECK_INTERVAL_SECONDS}s)")
    
    yield
    
    # Shutdown
    scheduler.shutdown()
    print("👋 Uptime Ping stopped")


app = FastAPI(
    title="Uptime Ping",
    description="Simple API health monitoring with Telegram alerts",
    version="0.1.0",
    lifespan=lifespan,
)


class EndpointConfig(BaseModel):
    url: str
    name: str | None = None
    expected_status: int = 200
    timeout_ms: int = 10000
    degraded_threshold_ms: int = 3000


@app.get("/")
async def root():
    return {
        "name": "Uptime Ping",
        "endpoints_monitored": len(endpoints),
        "check_interval_seconds": CHECK_INTERVAL_SECONDS,
        "api": {
            "/status": "Current status of all endpoints",
            "/status/{url}": "Status and uptime for specific endpoint",
            "/checks": "Recent check history",
            "/config": "View current configuration",
            "/check": "Trigger immediate check (POST)",
        }
    }


@app.get("/status")
async def get_status():
    """Get current status summary."""
    return get_status_summary()


@app.get("/uptime/{url:path}")
async def get_endpoint_uptime(url: str, hours: int = 24):
    """Get uptime stats for a specific endpoint."""
    # URL decode if needed
    if not url.startswith("http"):
        url = f"https://{url}"
    
    return calculate_uptime(url, hours)


@app.get("/checks")
async def get_checks(hours: int = 24, limit: int = 100):
    """Get recent check history."""
    checks = load_recent_checks(hours)[:limit]
    return {"checks": checks, "count": len(checks)}


@app.get("/config")
async def get_config():
    """Get current configuration."""
    return {
        "endpoints": [
            {
                "url": ep.url,
                "name": ep.name,
                "expected_status": ep.expected_status,
                "timeout_ms": ep.timeout_ms,
                "degraded_threshold_ms": ep.degraded_threshold_ms,
            }
            for ep in endpoints
        ],
        "check_interval_seconds": CHECK_INTERVAL_SECONDS,
    }


@app.post("/config/endpoints")
async def add_endpoint(ep: EndpointConfig):
    """Add a new endpoint to monitor."""
    # Load current config
    config = json.loads(CONFIG_FILE.read_text())
    
    # Check if already exists
    existing_urls = [e["url"] for e in config["endpoints"]]
    if ep.url in existing_urls:
        raise HTTPException(status_code=400, detail="Endpoint already exists")
    
    # Add new endpoint
    config["endpoints"].append(ep.model_dump())
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    
    # Reload
    load_config()
    
    return {"success": True, "endpoints_count": len(endpoints)}


@app.delete("/config/endpoints")
async def remove_endpoint(url: str):
    """Remove an endpoint from monitoring."""
    config = json.loads(CONFIG_FILE.read_text())
    config["endpoints"] = [e for e in config["endpoints"] if e["url"] != url]
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    
    load_config()
    
    return {"success": True, "endpoints_count": len(endpoints)}


@app.post("/check")
async def trigger_check():
    """Trigger an immediate health check."""
    await run_checks()
    return get_status_summary()


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
