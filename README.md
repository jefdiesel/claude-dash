# Claude Max Token Tracker

Local dashboard to track Claude Max 5x token usage since Anthropic's session reporting is unreliable.

## Quick Start

```bash
# Server runs automatically via launchd
open http://localhost:8889
```

## What It Does

- Tracks tokens across **monthly**, **weekly**, and **5-hour session** windows
- Auto-captures usage via OpenTelemetry (once Claude Code is restarted)
- Shows progress bars, daily chart, session history
- Data persists in `usage.json`

## Files

```
~/usage/
├── server.py           # Python HTTP server (port 8889)
├── usage.json          # Token data storage
├── public/index.html   # Dashboard UI
└── README.md

~/Library/LaunchAgents/com.jef.token-tracker.plist  # Auto-start service
~/.claude/settings.json  # Contains OTEL env vars for auto-capture
```

## Telemetry Config

Added to `~/.claude/settings.json`:
```json
"env": {
  "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
  "OTEL_LOGS_EXPORTER": "otlp",
  "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json",
  "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": "http://localhost:8889/v1/logs"
}
```

**IMPORTANT:** Restart Claude Code for telemetry to activate. New sessions will auto-log tokens.

## Service Commands

```bash
# Stop
launchctl unload ~/Library/LaunchAgents/com.jef.token-tracker.plist

# Start
launchctl load ~/Library/LaunchAgents/com.jef.token-tracker.plist

# View logs
tail -f ~/usage/server.log
```

## Current Limits (estimates - adjust in usage.json)

| Period | Limit | Notes |
|--------|-------|-------|
| Monthly | 45M | Resets on 1st |
| Weekly | 11M | Resets Monday |
| Session | 1.5M | 5-hour rolling window |

**TODO:** Session limit may be wrong. Based on 11% usage in ~20min, actual cap might be 4-6M. Update `sessionLimit` in `usage.json` once real data comes in.

## API Endpoints

- `GET /api/usage` - Get all data
- `POST /api/session` - Add manual entry `{input, output, note}`
- `POST /api/delete-session` - Delete entry `{index}`
- `POST /v1/logs` - OTEL receiver (auto-capture)

## Next Steps

1. Restart Claude Code to activate telemetry
2. Use Claude normally - tokens will auto-log
3. Check dashboard to see actual token counts
4. Compare with claude.ai/settings/usage percentages
5. Adjust limits in usage.json based on real data
