#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Keep credentials and overrides scoped to this instance.
if env | grep -q '^FREQTRADE__'; then
    echo "请先清除 FREQTRADE__ 环境变量，避免覆盖独立实盘配置。" >&2
    exit 1
fi
.venv/bin/python - <<'CHECK'
import json
from pathlib import Path
c = json.loads(Path("user_data/config.live.private.json").read_text())
if not all(c.get("exchange", {}).get(k, "").strip() for k in ("key", "secret")):
    raise SystemExit("请先在 user_data/config.live.private.json 本机填写币安 API key 和 secret。")
CHECK
exec .venv/bin/freqtrade trade \
    --config user_data/config.live.json \
    --config user_data/config.live.private.json \
    --db-url sqlite:///user_data/trades-live.sqlite \
    --logfile user_data/logs/freqtrade-live.log
