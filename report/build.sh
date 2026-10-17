#!/usr/bin/env bash
# Build report.pdf from report.html (A4, MathJax rendered offline by headless Chromium).
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .mjx/package/es5/tex-svg.js ]; then
  mkdir -p .mjx && (cd .mjx && npm pack mathjax@3.2.2 --silent >/dev/null && tar xzf mathjax-3.2.2.tgz)
fi
CHROME=${CHROME:-$(ls /opt/pw-browsers/chromium-*/chrome-linux/chrome 2>/dev/null | head -1)}
CHROME=${CHROME:-chromium}
"$CHROME" --headless --no-sandbox --disable-gpu --allow-file-access-from-files \
  --virtual-time-budget=20000 --no-pdf-header-footer \
  --print-to-pdf="$PWD/report.pdf" "file://$PWD/report.html" 2>/dev/null
python3 - <<'EOF'
import re
d = open("report.pdf", "rb").read()
print("pages:", len(re.findall(rb"/Type\s*/Page[^s]", d)))
EOF
