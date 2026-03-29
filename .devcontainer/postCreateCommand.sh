#!/bin/bash
set -e

if [ -f ".env" ]; then
    source ".env"
else
    touch ".env"
    source ".env"
fi

pyproject="$(pwd)/pyproject.toml"

if [ ! -f "$pyproject" ]; then
  uv init
fi

# Ensure user-level bin directory exists for helper commands.
mkdir -p "$HOME/.local/bin"

# Create durable UV helper commands that work in any shell (not just alias-enabled ones).
cat > "$HOME/.local/bin/uv-sync-all" << 'EOF'
#!/bin/bash
set -e
uv sync --all-packages --extra dev --extra profiling --extra docs "$@"
EOF

cat > "$HOME/.local/bin/uv-sync-dev" << 'EOF'
#!/bin/bash
set -e
uv sync --all-packages --extra dev "$@"
EOF

chmod +x "$HOME/.local/bin/uv-sync-all" "$HOME/.local/bin/uv-sync-dev"

# Ensure ~/.local/bin is available in future shells.
if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi

# Sync dependencies
echo "Installing Python dependencies..."
if uv sync --all-packages --extra dev; then
    echo "Dependencies installed successfully"
else
    echo "Failed to install dependencies"
    exit 1
fi
echo ""

