"""
Telegram notification for uptime alerts
"""
import os
import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """Send a Telegram message. Returns True if successful."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"⚠️ Telegram not configured, would send: {message}")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": parse_mode,
            })
            return resp.status_code == 200
    except Exception as e:
        print(f"❌ Failed to send Telegram: {e}")
        return False


def format_incident_message(incident: dict) -> str:
    """Format incident for Telegram notification."""
    url = incident["url"]
    prev = incident["prev_status"]
    new = incident["new_status"]
    
    if new == "down":
        emoji = "🔴"
        title = "服务宕机"
    elif new == "up" and prev == "down":
        emoji = "✅"
        title = "服务恢复"
    elif new == "degraded":
        emoji = "⚠️"
        title = "服务变慢"
    else:
        emoji = "ℹ️"
        title = "状态变化"
    
    lines = [
        f"{emoji} <b>{title}</b>",
        f"",
        f"🔗 {url}",
        f"📊 {prev} → {new}",
    ]
    
    if incident.get("error"):
        lines.append(f"❗ {incident['error']}")
    
    if incident.get("was_down_since"):
        lines.append(f"⏱️ 宕机开始: {incident['was_down_since']}")
    
    lines.append(f"🕐 {incident['changed_at']}")
    
    return "\n".join(lines)


async def notify_incident(incident: dict) -> bool:
    """Send incident notification to Telegram."""
    message = format_incident_message(incident)
    return await send_telegram(message)
