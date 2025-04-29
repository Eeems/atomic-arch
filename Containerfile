#syntax=docker/dockerfile:1.4
ARG ARCHIVE_YEAR=2025
ARG ARCHIVE_MONTH=04
ARG ARCHIVE_DAY=27
ARG TAG_VERSION=0.341977

FROM docker.io/library/archlinux:base-devel-${ARCHIVE_YEAR}${ARCHIVE_MONTH}${ARCHIVE_DAY}.${TAG_VERSION} AS pacstrap

ARG ARCHIVE_YEAR
ARG ARCHIVE_MONTH
ARG ARCHIVE_DAY

RUN echo "Server = https://archive.archlinux.org/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch" > /etc/pacman.d/mirrorlist
RUN pacman-key --init
RUN pacman -Sy --needed --noconfirm archlinux-keyring arch-install-scripts
RUN mkdir /rootfs
COPY overlay/pacstrap /rootfs

WORKDIR /rootfs

RUN mkdir -m 0755 -p var/{cache/pacman/pkg,lib/pacman,log} dev run etc
RUN mkdir -m 1777 tmp
RUN mkdir -m 0555 sys proc
RUN fakeroot pacman -r . -Sy --noconfirm base
RUN cp -a {/,}etc/pacman.d/mirrorlist
RUN cp -a {/,}etc/pacman.conf


FROM scratch AS base

WORKDIR /
COPY --from=pacstrap /rootfs /
ENTRYPOINT [ "/bin/bash" ]

ARG ARCHIVE_YEAR
ARG ARCHIVE_MONTH
ARG ARCHIVE_DAY

RUN <<EOF cat > /etc/os-release
NAME="Atomic Arch"
PRETTY_NAME="Atomic Arch Linux"
ID=atomic-arch
HOME_URL="https://github.com/Eeems/atomic-arch"
SUPPORT_URL="https://github.com/Eeems/atomic-arch/issues"
BUG_REPORT_URL="https://github.com/Eeems/atomic-arch/issues"
VERSION_ID=${ARCHIVE_YEAR}.${ARCHIVE_MONTH}.${ARCHIVE_DAY}
VARIANT=Base
VARIANT_ID=base
EOF

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
  nvidia-open-dkms \
  nvidia-container-toolkit \
  nvidia-utils

RUN systemctl enable \
  NetworkManager \
  bluetooth \
  podman

RUN mkdir -p /var/lib/system
COPY overlay/base /
RUN systemctl enable ostree-rollback-to-rescue

FROM base AS gnome

RUN /usr/lib/system/set_variant gnome Gnome

RUN /usr/lib/system/install_packages \
  gdm \
  gnome-shell \
  ghostty \
  xorg-server \
  gnome-software \
  flatpak-xdg-utils \
  gnome-packagekit \
  fwupd \
  gnome-tweaks \
  gnome-control-center

RUN systemctl enable gdm
COPY overlay/gnome /

FROM base as atomic

RUN /usr/lib/system/set_variant atomic Atomic

RUN /usr/lib/system/install_packages \
  ghostty \
  gnome-software \
  flatpak-xdg-utils \
  gnome-packagekit \
  fwupd \
  lemurs \
  niri \
  mako \
  waybar \
  xdg-desktop-portal-gnome \
  swaybg \
  swayidle \
  swaylock \
  xwayland-satellite \
  fuzzel \
  gnome-keyring \
  nautilus

RUN systemctl enable lemurs.service
COPY overlay/atomic /
