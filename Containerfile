#syntax=docker/dockerfile:1.4
ARG ARCHIVE_YEAR=2025
ARG ARCHIVE_MONTH=04
ARG ARCHIVE_DAY=20
ARG TAG_VERSION=0.338771

FROM docker.io/library/archlinux:base-devel-${ARCHIVE_YEAR}${ARCHIVE_MONTH}${ARCHIVE_DAY}.${TAG_VERSION} AS pacstrap

ARG ARCHIVE_YEAR
ARG ARCHIVE_MONTH
ARG ARCHIVE_DAY

RUN echo "Server = https://archive.archlinux.org/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch" > /etc/pacman.d/mirrorlist
RUN pacman-key --init
RUN pacman -Sy --needed --noconfirm archlinux-keyring arch-install-scripts
RUN mkdir /rootfs
WORKDIR /rootfs
RUN <<EOT
  set -e
  mkdir -m 0755 -p var/{cache/pacman/pkg,lib/pacman,log} dev run etc
  mkdir -m 1777 tmp
  mkdir -m 0555 sys proc
  fakeroot pacman -r . -Sy --noconfirm base
  cp -a {/,}etc/pacman.d/mirrorlist
  cp -a {/,}etc/pacman.conf
EOT

FROM scratch AS rootfs

WORKDIR /

COPY --from=pacstrap /rootfs /

RUN <<EOT
  set -e
  pacman-key --init
  pacman-key --populate archlinux
  pacman -Syu --needed --noconfirm \
    base \
    nano \
    micro \
    sudo \
    tmux \
    less \
    htop \
    fastfetch
  yes | pacman -Scc
  rm -rf etc/pacman.d/gnupg/{openpgp-revocs.d/,private-keys-v1.d/,pubring.gpg~,gnupg.S.}*
EOT

ENTRYPOINT [ "/bin/bash" ]

FROM rootfs AS base

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

RUN <<EOT
  set -e
  pacman-key --init
  pacman-key --populate archlinux
  pacman -Syu --needed --noconfirm \
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
    squashfs-tools \
    xorriso \
    dosfstools \
    flatpak
  yes | pacman -Scc
  rm -rf etc/pacman.d/gnupg/{openpgp-revocs.d/,private-keys-v1.d/,pubring.gpg~,gnupg.S.}*
EOT

RUN <<EOT
  set -e
  pacman-key --init
  pacman-key --populate archlinux
  pacman -Syu --needed --noconfirm \
    nvidia-dkms \
    nvidia-container-toolkit
  yes | pacman -Scc
  rm -rf etc/pacman.d/gnupg/{openpgp-revocs.d/,private-keys-v1.d/,pubring.gpg~,gnupg.S.}*
EOT

RUN <<EOT
  set -e
  echo 'unqualified-search-registries = ["docker.io"]' > /etc/containers/registries.conf.d/10-docker.conf
  echo "kernel.unprivileged_userns_clone=1" > /usr/lib/sysctl.d/99-podman.conf
  echo "%wheel ALL=(ALL) ALL" > /etc/sudoers.d/wheel
  systemctl enable NetworkManager bluetooth podman
  mkdir /etc/system
EOT

RUN <<EOF cat > /etc/system/Systemfile
FROM atomic-arch:base

RUN echo "BUILD_ID=$(date +'%Y-%m-%d')" >> /etc/os-release
EOF

COPY os /usr/bin
COPY Isofile /etc/system

FROM base AS gnome

RUN <<EOT
  set -e
  sed -i '/FROM atomic-arch:/ s|base|gnome|' /etc/system/{System,Iso}file
  sed -i '/Variant=/ s|Base|Gnome|' /etc/os-release
  sed -i '/Variant_id=/ s|base|gnome|' /etc/os-release
EOT

RUN <<EOT
  set -e
  pacman-key --init
  pacman-key --populate archlinux
  pacman -Syu --needed --noconfirm \
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
  yes | pacman -Scc
  rm -rf etc/pacman.d/gnupg/{openpgp-revocs.d/,private-keys-v1.d/,pubring.gpg~,gnupg.S.}*
EOT

RUN <<EOT
  set -e
  systemctl enable gdm
EOT
