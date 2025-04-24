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
        sudo
    yes | pacman -Scc
    rm -rf etc/pacman.d/gnupg/{openpgp-revocs.d/,private-keys-v1.d/,pubring.gpg~,gnupg.S.}*
EOT

ENTRYPOINT [ "/bin/bash" ]

FROM rootfs AS base

RUN <<EOT
    set -e
    pacman-key --init
    pacman-key --populate archlinux
    pacman -Syu --needed --noconfirm \
        broadcom-wl-dkms \
        efibootmgr \
        grub \
        linux-firmware \
        linux-zen \
        linux-zen-headers \
        bluez \
        networkmanager \
        dosfstools \
        grub \
        squashfs-tools \
        xorriso \
        podman \
        fuse-overlayfs \
        mkinitcpio-archiso \
        syslinux
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
    systemctl enable NetworkManager bluetooth
    mkdir /etc/system
EOT

RUN <<EOF cat > /etc/system/mkinitcpio-iso.conf
MODULES=()
BINARIES=()
FILES=()
HOOKS=(base udev modconf memdisk archiso archiso_loop_mnt kms block filesystems keyboard)
EOF

RUN <<EOF cat > /etc/system/Systemfile
FROM atomic-arch:base
EOF

COPY os /usr/bin

FROM base AS gnome

RUN <<EOT
    set -e
    pacman-key --init
    pacman-key --populate archlinux
    pacman -Syu --needed --noconfirm \
        gdm \
        gnome-shell \
        ghostty \
        xorg-server
    yes | pacman -Scc
    rm -rf etc/pacman.d/gnupg/{openpgp-revocs.d/,private-keys-v1.d/,pubring.gpg~,gnupg.S.}*
EOT

RUN <<EOT
    set -e
    systemctl enable gdm
EOT

RUN <<EOF cat > /etc/system/Systemfile
FROM atomic-arch:gnome
EOF
