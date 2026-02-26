# =============================================================
#  Orion Sandbox — Lightweight development container
#  
#  This gives Orion a full Linux environment to experiment in
#  without being able to touch the host OS. He can install
#  packages, write code, run scripts, break things freely.
#
#  Build:  docker build -t orion-sandbox -f sandbox/Dockerfile .
#  Run:    docker-compose -f sandbox/docker-compose.yml up -d
# =============================================================

FROM python:3.11-slim-bookworm

LABEL maintainer="agent-runtime" \
      description="Sandboxed environment for Orion agent"

# Avoid interactive prompts during install
ENV DEBIAN_FRONTEND=noninteractive

# ------------------------------------------------------------------
# System packages: dev tools, editors, networking, git
# ------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core dev tools
    build-essential \
    git \
    curl \
    wget \
    # Editors
    vim \
    nano \
    # Networking / diagnostics
    net-tools \
    iputils-ping \
    dnsutils \
    htop \
    # Process management
    procps \
    # File tools
    tree \
    jq \
    zip \
    unzip \
    # Python build deps (for compiling packages)
    libffi-dev \
    libssl-dev \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# Python environment: common packages pre-installed
# ------------------------------------------------------------------
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    requests \
    pyyaml \
    flask \
    fastapi \
    uvicorn \
    httpx \
    beautifulsoup4 \
    markdown \
    numpy \
    pytest \
    black \
    ruff \
    ipython

# ------------------------------------------------------------------
# Node.js (for web experiments)
# ------------------------------------------------------------------
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# Workspace setup
# ------------------------------------------------------------------
RUN useradd -m -s /bin/bash orion && \
    mkdir -p /workspace /home/orion/.local && \
    chown -R orion:orion /workspace /home/orion

# The workspace volume is mounted from the host at runtime
VOLUME /workspace

# ------------------------------------------------------------------
# Environment
# ------------------------------------------------------------------
ENV HOME=/home/orion \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/orion/.local/bin:$PATH"

WORKDIR /workspace

# Run as the orion user (not root)
USER orion

# Default command: keep container alive
CMD ["bash", "-c", "echo '🟢 Orion sandbox ready.' && tail -f /dev/null"]
