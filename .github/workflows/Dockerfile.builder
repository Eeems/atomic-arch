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
        jq \
        meson \
        uidmap \
        netavark \
        skopeo \
        fuse-overlayfs \
        containernetworking-plugins \
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
    # Install docker-ce
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg | tee /etc/apt/keyrings/docker.asc > /dev/null \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        docker-ce-cli \
    # Install python 3.12
    && curl https://pyenv.run | bash \
    && pyenv install 3.12 \
    && pyenv global 3.12 \
    && pyenv exec python -m pip install --root-user-action ignore --upgrade \
        pip \
        setuptools \
        requests \
        wheel \
    # Cleanup
    && pip cache purge \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf \
        /var/lib/apt/lists/* \
        /tmp/* \
        /var/tmp/*

RUN mkdir /github \
    && usermod --login runner "$(id -nu 1000)" \
    && echo 'runner:runner' | chpasswd \
    && usermod -aG sudo runner \
    && printf 'runner ALL=(ALL) NOPASSWD: ALL\nDefaults:runner env_keep += "PATH PYENV_ROOT", secure_path = "%s"\n' "$PATH" > /etc/sudoers.d/runner \
    && mkdir -p \
        /github/{workspace,workflow,home} \
        /etc/containers \
        /tmp/podman-run \
        /var/lib/containers/storage \
        /var/cache/podman \
        /var/cache/pacman \
        /var/lib/pacman \
        /etc/pacman.d/gnupg \
    && ln -s /usr/bin/false /usr/local/bin/systemd-detect-virt

RUN <<EOF cat > /etc/containers/registries.conf.d/10-docker.conf
unqualified-search-registries = ["docker.io"]
EOF

RUN <<EOF cat > /etc/containers/containers.conf
[engine]
runroot = "/tmp/podman-run"
storageroot = "/var/lib/containers/storage"
EOF

USER 0
