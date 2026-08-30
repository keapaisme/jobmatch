#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
exec python3 main.py --watch --interval "${JOB_FINDER_INTERVAL:-300}"
