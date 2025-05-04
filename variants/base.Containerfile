#syntax=docker/dockerfile:1.4
ARG VARIANT="Base"
ARG VARIANT_ID="base"

FROM eeems/atomic-arch:rootfs as ${VARIANT_ID}

ARG VARIANT
ARG VARIANT_ID
ARG VERSION_ID

LABEL \
    os-release.VARIANT="${VARIANT}" \
    os-release.VARIANT_ID="${VARIANT_ID}" \
    os-release.VERSION_ID="${VERSION_ID}" \
    org.opencontainers.image.ref.name="${VARIANT_ID}"

RUN /usr/lib/system/set_variant

RUN /usr/lib/system/install_packages \
  base \
  nano \
  micro \
  sudo \
  tmux \
  less \
  htop \
  fastfetch \
  bluez \
  broadcom-wl-dkms \
  linux-firmware \
  linux-zen \
  linux-zen-headers \
  networkmanager \
  fuse-overlayfs \
  podman \
  efibootmgr \
  grub \
  flatpak \
  ostree \
  xorriso \
  squashfs-tools \
  btrfs-progs \
  e2fsprogs \
  exfatprogs \
  ntfs-3g \
  xfsprogs \
  git \
  fakeroot \
  debugedit \
  terminus-font \
  pv \
  run-parts \
  skopeo \
  pacman-contrib

RUN systemctl enable \
  NetworkManager \
  bluetooth \
  podman

RUN mkdir -p /var/lib/system
COPY overlay/base /
RUN systemctl enable ostree-rollback-to-rescue
