# syntax = docker/dockerfile:1.7
FROM ubuntu:24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYENV_ROOT=/opt/pyenv \
    PATH=/opt/pyenv/shims:/opt/pyenv/bin:$PATH

# Install core tools + build deps for pyenv + your system deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        gnupg \
        ostree \
        podman \
        sudo \
        meson \
        uidmap \
        ninja-build \
        build-essential \
        pkg-config \
        python3-dev \
        libpython3-dev \
        libdbus-1-dev \
        libglib2.0-dev \
        libcairo2-dev \
        libgirepository-2.0-dev \
        # Pyenv extra dependencies
        libssl-dev \
        zlib1g-dev \
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
    # Install python 3.12
    && curl https://pyenv.run | bash \
    && pyenv install 3.12 \
    && pyenv global 3.12 \
    # Cleanup
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf \
        /var/lib/apt/lists/* \
        /tmp/* \
        /var/tmp/*

RUN mkdir /github \
    && usermod --login runner "$(id -nu 1000)" \
    && mkdir -p /github/{workspace,workflow,home} \
    && echo 'runner:runner' | chpasswd \
    && usermod -aG sudo runner \
    && printf 'runner ALL=(ALL) NOPASSWD: ALL\nDefaults:runner env_keep += "PATH PYENV_ROOT", secure_path = "%s"\n' "$PATH" > /etc/sudoers.d/runner \
    && mkdir -p \
        /etc/containers \
        /tmp/podman-run \
        /var/lib/containers/storage \
        /var/cache/podman \
        /var/cache/pacman \
        /var/lib/pacman \
        /etc/pacman.d/gnupg \
    && printf '[engine]\nrunroot = "/tmp/podman-run"\nstorageroot = "/var/lib/containers/storage"\n' > /etc/containers/containers.conf \
    && printf 'unqualified-search-registries = ["docker.io"]' > /etc/containers/registries.conf.d/10-docker.conf \
    && ln -s /usr/bin/false /usr/local/bin/systemd-detect-virt

USER 0
