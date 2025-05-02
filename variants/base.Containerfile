#syntax=docker/dockerfile:1.4
ARG ARCHIVE_YEAR=2025
ARG ARCHIVE_MONTH=05
ARG ARCHIVE_DAY=01
ARG PACSTRAP_TAG=20250427.0.341977

FROM docker.io/library/archlinux:base-devel-${PACSTRAP_TAG} AS pacstrap

ARG ARCHIVE_YEAR
ARG ARCHIVE_MONTH
ARG ARCHIVE_DAY

RUN \
  echo "Server = https://archive.archlinux.org/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch" > /etc/pacman.d/mirrorlist \
  && echo "Server = https://america.archive.pkgbuild.com/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch" >> /etc/pacman.d/mirrorlist \
  && echo "Server = https://asia.archive.pkgbuild.com/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch" >> /etc/pacman.d/mirrorlist \
  && echo "Server = https://europe.archive.pkgbuild.com/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch" >> /etc/pacman.d/mirrorlist
RUN pacman-key --init \
  && pacman -Sy --needed --noconfirm archlinux-keyring moreutils
RUN mkdir /rootfs
WORKDIR /rootfs
RUN mkdir -m 0755 -p var/{cache/pacman/pkg,lib/pacman,log} dev run etc \
  && mkdir -m 1777 tmp \
  && mkdir -m 0555 sys proc
RUN chronic fakeroot pacman -r . -Sy --noconfirm base mkinitcpio moreutils
RUN rm usr/share/libalpm/hooks/60-mkinitcpio-remove.hook \
  && rm usr/share/libalpm/hooks/90-mkinitcpio-install.hook \
  && cp -a {/,}etc/pacman.d/mirrorlist \
  && cp -a {/,}etc/pacman.conf

FROM scratch AS base

WORKDIR /
COPY --from=pacstrap /rootfs /
COPY overlay/pacstrap /
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
