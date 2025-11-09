#syntax=docker/dockerfile:1.4
ARG HASH

FROM ghcr.io/eeems/atomic-arch:atomic

ARG \
  VARIANT="Eeems" \
  VARIANT_ID="eeems"

RUN /usr/lib/system/add_pacman_repository \
  --keyfile=https://download.sublimetext.com/sublimehq-pub.gpg \
  --key=8A8F901A \
  --server=https://download.sublimetext.com/arch/stable/\$arch \
  sublime-text \
  && /usr/lib/system/add_pacman_repository \
  --key=A64228CCD26972801C2CE6E3EC931EA46980BA1B \
  --server=https://repo.eeems.website/\$repo \
  --server=https://repo.eeems.codes/\$repo \
  eeems-linux \
  && /usr/lib/system/install_packages eeems-keyring \
  && /usr/lib/system/remove_pacman_files

RUN /usr/lib/system/initialize_pacman \
  && /usr/lib/system/install_packages \
  sublime-text \
  zsh \
  man-pages \
  man-db \
  zerotier-one \
  kdeconnect \
  zram-generator \
  v4l2loopback-utils \
  v4l2loopback-dkms \
  pyenv \
  spotify \
  podman-docker \
  podman-compose \
  && /usr/lib/system/install_aur_packages \
  wego \
  && /usr/lib/system/remove_pacman_files

RUN systemctl enable zerotier-one

COPY overlay/eeems /

ARG VERSION_ID HASH

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}" \
  hash="${HASH}"

RUN /usr/lib/system/set_variant
