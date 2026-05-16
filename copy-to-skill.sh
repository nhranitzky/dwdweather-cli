#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <target-skill-dir>" >&2
    exit 2
fi

TARGET="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/dwdweather"

mkdir -p "$TARGET/bin" "$TARGET/scripts"
rsync -a \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$SRC/" "$TARGET/scripts/"

cat > "$TARGET/bin/dwdweather" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

CLI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"

unset VIRTUAL_ENV CONDA_PREFIX CONDA_DEFAULT_ENV
exec uv run --project "$CLI_DIR" --directory "$CLI_DIR" dwdweather "$@"
EOF

chmod +x "$TARGET/bin/dwdweather"
