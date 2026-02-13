"""
JSON file storage for uptime history
"""
import json
import os
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import defaultdict

from .monitor import CheckResult, Status

DATA_DIR = Path(os.getenv("UPTIME_DATA_DIR", "/root/source/side-projects/uptime-ping/data"))


def ensure_dirs():
    (DATA_DIR / "checks").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "incidents").mkdir(parents=True, exist_ok=True)


def _today_file() -> Path:
    return DATA_DIR / "checks" / f"{date.today().isoformat()}.jsonl"


def save_check(result: CheckResult):
    """Append a check result to today's log file."""
    ensure_dirs()
    
    record = {
        "url": result.url,
        "status": result.status.value,
        "status_code": result.status_code,
        "response_time_ms": result.response_time_ms,
        "error": result.error,
        "checked_at": result.checked_at.isoformat(),
    }
    
    with open(_today_file(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_checks(results: list[CheckResult]):
    """Save multiple check results."""
    for r in results:
        save_check(r)


def load_checks_for_date(date_str: str) -> list[dict]:
    """Load all checks for a specific date."""
    filepath = DATA_DIR / "checks" / f"{date_str}.jsonl"
    
    if not filepath.exists():
        return []
    
    checks = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                checks.append(json.loads(line))
    
    return checks


def load_recent_checks(hours: int = 24) -> list[dict]:
    """Load checks from the last N hours."""
    now = datetime.utcnow()
    checks = []
    
    # Check today and yesterday
    for days_ago in range(2):
        d = (now - timedelta(days=days_ago)).date()
        day_checks = load_checks_for_date(d.isoformat())
        
        cutoff = now - timedelta(hours=hours)
        for c in day_checks:
            check_time = datetime.fromisoformat(c["checked_at"])
            if check_time >= cutoff:
                checks.append(c)
    
    return sorted(checks, key=lambda x: x["checked_at"], reverse=True)


def calculate_uptime(url: str, hours: int = 24) -> dict:
    """Calculate uptime percentage for an endpoint."""
    checks = load_recent_checks(hours)
    url_checks = [c for c in checks if c["url"] == url]
    
    if not url_checks:
        return {"url": url, "uptime_pct": None, "check_count": 0}
    
    up_count = sum(1 for c in url_checks if c["status"] == "up")
    total = len(url_checks)
    
    avg_response = sum(c["response_time_ms"] for c in url_checks) / total
    
    return {
        "url": url,
        "uptime_pct": round(up_count / total * 100, 2),
        "check_count": total,
        "avg_response_ms": round(avg_response, 2),
        "last_check": url_checks[0] if url_checks else None,
    }


def get_status_summary() -> dict:
    """Get current status summary for all monitored endpoints."""
    checks = load_recent_checks(1)  # Last hour
    
    # Group by URL, get latest for each
    latest_by_url = {}
    for c in checks:
        url = c["url"]
        if url not in latest_by_url:
            latest_by_url[url] = c
    
    summary = {
        "endpoints": [],
        "total": len(latest_by_url),
        "up": 0,
        "down": 0,
        "degraded": 0,
    }
    
    for url, check in latest_by_url.items():
        status = check["status"]
        summary["endpoints"].append({
            "url": url,
            "status": status,
            "response_time_ms": check["response_time_ms"],
            "last_check": check["checked_at"],
        })
        
        if status == "up":
            summary["up"] += 1
        elif status == "down":
            summary["down"] += 1
        else:
            summary["degraded"] += 1
    
    return summary


# Incident tracking
_incident_state: dict[str, dict] = {}  # url -> {status, since, notified}


def track_incident(result: CheckResult) -> dict | None:
    """
    Track status changes and return incident info if state changed.
    Returns dict with incident info if notification needed, None otherwise.
    """
    url = result.url
    current_status = result.status.value
    
    if url not in _incident_state:
        _incident_state[url] = {
            "status": current_status,
            "since": result.checked_at.isoformat(),
            "notified": False,
        }
        return None  # First check, no change
    
    prev = _incident_state[url]
    
    if prev["status"] != current_status:
        # Status changed
        incident = {
            "url": url,
            "prev_status": prev["status"],
            "new_status": current_status,
            "changed_at": result.checked_at.isoformat(),
            "was_down_since": prev["since"] if prev["status"] == "down" else None,
            "error": result.error,
        }
        
        # Update state
        _incident_state[url] = {
            "status": current_status,
            "since": result.checked_at.isoformat(),
            "notified": True,
        }
        
        # Save incident to file
        ensure_dirs()
        incident_file = DATA_DIR / "incidents" / f"{date.today().isoformat()}.jsonl"
        with open(incident_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(incident, ensure_ascii=False) + "\n")
        
        return incident
    
    return None
