#!/usr/bin/env bash
# Build a flat Zenodo replication zip (LICENSE and README at archive root).
# Also upload LICENSE, README.md, and sbcars2026-camera-ready.pdf as standalone
# files at the Zenodo record root (same content, not inside the zip only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-v1.0.6}"
OUT="${2:-${ROOT}/../iso-nfr-enrichment-humaneval-${VERSION}-flat.zip}"

cd "$ROOT"
rm -f "$OUT"
zip -r "$OUT" . \
  -x '.git/*' \
  -x '.git/**' \
  -x '*/.git/*' \
  -x '*__pycache__/*' \
  -x '*.pyc'

echo "Created: $OUT"
echo "Also upload standalone on Zenodo: LICENSE, README.md, sbcars2026-camera-ready.pdf"
echo "Root entries:"
unzip -l "$OUT" | awk 'NR<=20 {print}'
