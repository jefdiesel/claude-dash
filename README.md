# Claude Max Token Tracker

Local dashboard to track Claude Max 5x token usage since Anthropic's session reporting is unreliable.

## Quick Start

```bash
# Server runs automatically via launchd
open http://localhost:8889
```

## Features

- **Auto-capture** via OpenTelemetry integration with Claude Code
- **Multi-window tracking**: Session (5hr), Weekly, Monthly
- **Per-API-call chart**: Green = Opus, Blue = Haiku
- **Comparison logging**: Record Claude's reported % alongside tracked data
- **Calibration log**: Build training data to learn actual limits
- **Session time input**: Enter reset time from Claude to calculate session window

## Dashboard

### Usage Section
- Progress bars for Session/Weekly/Monthly
- "Limit" buttons to record when you hit a limit
- Stats: tracked tokens, API call count

### Comparison Logging
- Enter Claude's session % and weekly %
- Click "Log" to save comparison data
- Does NOT modify displayed percentages
- Builds calibration data over time

### Reset Time Input
- Enter time remaining from Claude (e.g. "2:45")
- Calculates actual session start time
- Persists across page refresh

## Files

```
~/usage/
├── server.py           # Python HTTP server (port 8889)
├── usage.json          # Token + calibration data
├── public/index.html   # Dashboard UI
└── README.md

~/Library/LaunchAgents/com.jef.token-tracker.plist  # Auto-start service
~/.claude/settings.json  # OTEL env vars for auto-capture
```

## Telemetry Config

Add to `~/.claude/settings.json`:
```json
"env": {
  "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
  "OTEL_LOGS_EXPORTER": "otlp",
  "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json",
  "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": "http://localhost:8889/v1/logs"
}
```

**Restart Claude Code for telemetry to activate.**

## Service Commands

```bash
# Stop
launchctl unload ~/Library/LaunchAgents/com.jef.token-tracker.plist

# Start
launchctl load ~/Library/LaunchAgents/com.jef.token-tracker.plist

# View logs
tail -f ~/usage/server.log
```

## Tier Limits

### Max 5x (calibrated Jan 15, 2026)
| Period | Limit | Notes |
|--------|-------|-------|
| Session | **2.0M** | 5-hour rolling window |
| Weekly | **20M** | Resets Thursday |
| Monthly | 45M | Resets on 1st |

### Pro (estimated)
| Period | Limit |
|--------|-------|
| Session | 500K |
| Weekly | 3.5M |
| Monthly | 10M |

### Max 20x (estimated, 4x Max 5x)
| Period | Limit |
|--------|-------|
| Session | 8M |
| Weekly | 80M |
| Monthly | 180M |

**Token counting notes:**
- Cache read tokens don't count toward limits. Only input + output + cache_creation.
- Compaction events (>100K input AND >1K output) are auto-detected and excluded.
- Use the "Count" toggle in Recent API Calls to manually include/exclude any entry.

## API Endpoints

- `GET /api/usage` - Get all data
- `POST /api/session` - Add manual entry `{input, output, note}`
- `POST /api/delete-session` - Delete entry `{index}`
- `POST /api/calibration` - Log comparison data
- `POST /v1/logs` - OTEL receiver (auto-capture)

## Calibration Workflow

1. Use Claude Code normally
2. Periodically check Claude's usage page
3. Enter Claude's % in dashboard and click "Log"
4. Over time, calibration data reveals actual limits
5. Adjust limits in `usage.json` based on findings
