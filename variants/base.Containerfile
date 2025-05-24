#syntax=docker/dockerfile:1.4
FROM eeems/atomic-arch:rootfs

ARG VARIANT="Base"
ARG VARIANT_ID="base"
ARG VERSION_ID

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}"

RUN /usr/lib/system/set_variant

RUN /usr/lib/system/initialize_pacman \
  && /usr/lib/system/install_packages \
  base \
  nano \
  micro \
  sudo-rs \
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
  dosfstools \
  git \
  fakeroot \
  debugedit \
  terminus-font \
  pv \
  run-parts \
  skopeo \
  pacman-contrib \
  python-pyxattr \
  python-requests \
  distrobox \
  && /usr/lib/system/remove_pacman_files

RUN systemctl enable \
  NetworkManager \
  bluetooth \
  podman

RUN mkdir -p /var/lib/system

COPY overlay/base /

RUN \
  systemctl enable atomic-state-overlay \
  && rm /usr/bin/su \
  && chmod 644 /etc/pam.d/sudo{,-i} \
  && chmod 400 /etc/sudoers \
  && ln -s /usr/bin/su{-rs,} \
  && ln -s /usr/bin/sudo{-rs,} \
  && ln -s /usr/bin/visudo{-rs,} \
  && chmod u+s /usr/bin/new{u,g}idmap
