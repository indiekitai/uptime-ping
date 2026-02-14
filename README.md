# 🏓 Uptime Ping

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Simple API health monitoring with Telegram alerts.

轻量级服务健康监控，支持 Telegram 告警。

## Features

- ⏰ 定时健康检查（默认每分钟）
- 📊 响应时间追踪
- ⚠️ 自动识别"变慢"状态（degraded）
- 🔔 状态变化时 Telegram 通知
- 📈 Uptime 百分比统计
- 🔧 REST API 管理

## Quick Start

```bash
cd /root/source/side-projects/uptime-ping

# Install
pip install httpx fastapi uvicorn python-dotenv apscheduler

# Configure (optional Telegram)
cp .env.example .env

# Edit config.json to add your endpoints
cat > config.json << 'EOF'
{
  "endpoints": [
    {"url": "https://your-api.com/health", "name": "My API"},
    {"url": "https://another-service.com", "name": "Another Service"}
  ],
  "check_interval_seconds": 60
}
EOF

# Run
uvicorn src.main:app --port 8081
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/status` | GET | Current status of all endpoints |
| `/uptime/{url}` | GET | Uptime stats for specific URL |
| `/checks` | GET | Recent check history |
| `/config` | GET | Current configuration |
| `/config/endpoints` | POST | Add endpoint |
| `/config/endpoints` | DELETE | Remove endpoint |
| `/check` | POST | Trigger immediate check |

## API 使用示例

```bash
# 查看所有服务状态
curl https://up.indiekit.ai/status

# 添加监控端点
curl -X POST https://up.indiekit.ai/config/endpoints \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-api.com/health", "name": "My API"}'

# 删除监控端点
curl -X DELETE https://up.indiekit.ai/config/endpoints \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-api.com/health"}'

# 手动触发检查
curl -X POST https://up.indiekit.ai/check

# 获取检查历史
curl https://up.indiekit.ai/checks?limit=10
```

## Telegram Setup

1. Create a bot via @BotFather
2. Get your chat ID (message @userinfobot)
3. Set environment variables:

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-xxx
TELEGRAM_CHAT_ID=12345678
```

## Data Storage

All data is stored as JSON files:

```
data/
├── checks/
│   ├── 2026-02-13.jsonl  # Daily check logs
│   └── ...
└── incidents/
    ├── 2026-02-13.jsonl  # Status change events
    └── ...
```

## Alert Example

```
🔴 服务宕机

🔗 https://api.example.com/health
📊 up → down
❗ Expected 200, got 503
🕐 2026-02-13T10:30:00
```

## License

MIT
