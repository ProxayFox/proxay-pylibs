FROM mcr.microsoft.com/devcontainers/python:3.14-trixie

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ripgrep jq yq btop \
    && rm -rf /var/lib/apt/lists/*

# Install uv without relying on GHCR image pulls
RUN python -m pip install --no-cache-dir --upgrade pip uv

# Install just (command runner)
RUN curl -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin