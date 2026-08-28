#!/usr/bin/env bash
# Install NFRGen-8175 Python deps on Ubuntu 26+ where system Graphviz is 14.x
# (incompatible with pygraphviz==1.11). Builds Graphviz 2.50.0 locally and
# compiles pygraphviz against it, then installs requirements.txt.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRAPHVIZ_PREFIX="${GRAPHVIZ_PREFIX:-$HOME/.local/graphviz-2.50.0}"
SRC="${GRAPHVIZ_SRC:-$HOME/.local/src}"
TARBALL="$SRC/graphviz-2.50.0.tar.gz"
URL="https://distfiles.macports.org/graphviz/graphviz-2.50.0.tar.gz"

if ! command -v python3.9 >/dev/null 2>&1; then
  echo "python3.9 not found. Install: sudo apt install python3.9 python3.9-venv python3.9-dev" >&2
  exit 1
fi

if [[ ! -x "$GRAPHVIZ_PREFIX/bin/dot" ]]; then
  echo "[*] Building Graphviz 2.50.0 -> $GRAPHVIZ_PREFIX"
  mkdir -p "$SRC"
  if [[ ! -f "$TARBALL" ]] || [[ ! -s "$TARBALL" ]]; then
    wget -q --show-progress -O "$TARBALL" "$URL"
  fi
  rm -rf "$SRC/graphviz-2.50.0"
  tar xzf "$TARBALL" -C "$SRC"
  (
    cd "$SRC/graphviz-2.50.0"
    ./configure --prefix="$GRAPHVIZ_PREFIX" --disable-static --without-x
    make -j"$(nproc)"
    make install
  )
fi

echo "[*] Graphviz: $("$GRAPHVIZ_PREFIX/bin/dot" -V)"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "[*] Creating venv at $ROOT/.venv"
  python3.9 -m venv "$ROOT/.venv"
fi

# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"
python -m pip install -U pip wheel

export PATH="$GRAPHVIZ_PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="$GRAPHVIZ_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export CFLAGS="-I$GRAPHVIZ_PREFIX/include"
export LDFLAGS="-L$GRAPHVIZ_PREFIX/lib -Wl,-rpath,$GRAPHVIZ_PREFIX/lib"

echo "[*] Installing pygraphviz==1.11 (legacy Graphviz headers)"
pip install pygraphviz==1.11 --no-cache-dir

echo "[*] Installing requirements.txt"
pip install -r "$ROOT/requirements.txt"

echo "[*] Done. Activate with: source $ROOT/.venv/bin/activate"
echo "[*] For runtime, export LD_LIBRARY_PATH=$GRAPHVIZ_PREFIX/lib:\$LD_LIBRARY_PATH if pygraphviz fails to load."
