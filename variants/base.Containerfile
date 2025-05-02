#syntax=docker/dockerfile:1.4
FROM atomic-arch:rootfs as base

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
  run-parts

RUN systemctl enable \
  NetworkManager \
  bluetooth \
  podman

RUN mkdir -p /var/lib/system
COPY overlay/base /
RUN systemctl enable ostree-rollback-to-rescue
