# syntax = docker/dockerfile:1.7
FROM ubuntu:22.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install core tools + Python 3.12 + your deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        software-properties-common \
        ca-certificates \
        curl \
        gnupg && \
    add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        # Python 3.12
        python3.12 \
        python3.12-dev \
        python3.12-venv \
        python3.12-distutils \
        python3-pip \
        # Your system deps
        build-essential \
        libpython3-dev \
        libdbus-1-dev \
        libglib2.0-dev \
        libcairo2-dev \
        libgirepository-2.0-dev \
        ostree \
        podman \
    && \
    # Set python3.12 as default
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 100 \
        --slave /usr/bin/python3-config python3-config /usr/bin/python3.12-config && \
    # Minimal pip setup
    python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    # Cleanup
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Verify
RUN python3 --version | grep -q "3.12" && \
    podman --version && \
    ostree --version

WORKDIR /workspace
