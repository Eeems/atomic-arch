# syntax = docker/dockerfile:1.7
FROM ubuntu:24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYENV_ROOT=/opt/pyenv \
    PATH=/opt/pyenv/shims:/opt/pyenv/bin:$PATH

# Install core tools + build deps for pyenv + your system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        gnupg \
        # Pyenv dependencies
        build-essential \
        libssl-dev zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        curl \
        git \
        libncursesw5-dev \
        xz-utils \
        tk-dev \
        libxml2-dev \
        libxmlsec1-dev \
        libffi-dev \
        liblzma-dev \
        libzstd-dev \
        # Builder dependencies
        libpython3-dev \
        libdbus-1-dev \
        libglib2.0-dev \
        libcairo2-dev \
        libgirepository-2.0-dev \
        ostree \
        podman \
    && \
    # Install pyenv
    curl https://pyenv.run | bash && \
    # Install Python 3.12 via pyenv
    pyenv install 3.12 && \
    pyenv global 3.12 && \
    # Ensure pip is available and upgraded
    python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    # Cleanup
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Verify
RUN python --version | grep -q "3.12" && \
    pip --version && \
    podman --version && \
    ostree --version

WORKDIR /workspace
