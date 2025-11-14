# syntax=docker/dockerfile:1.4
# x-depends=rootfs
# x-templates=slim
ARG HASH

FROM eeems/atomic-arch:rootfs

ARG \
  VARIANT="Base" \
  VARIANT_ID="base"

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
  mtools \
  rsync \
  dmidecode \
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
  nvme-cli \
  run-parts \
  skopeo \
  pacman-contrib \
  python-pyxattr \
  python-requests \
  python-dbus \
  distrobox \
  xdelta3 \
  && /usr/lib/system/remove_pacman_files \
  && rm /usr/bin/su \
  && ln -s /usr/bin/su{-rs,} \
  && ln -s /usr/bin/sudo{-rs,} \
  && ln -s /usr/bin/visudo{-rs,} \
  && chmod u+s /usr/bin/new{u,g}idmap

RUN systemctl enable \
  NetworkManager \
  bluetooth \
  podman

RUN mkdir -p /var/lib/system

COPY overlay/base /

RUN mkdir /var/home \
  && /usr/lib/system/initialize_pacman \
  && /usr/lib/system/install_aur_packages \
  localepurge \
  && /usr/lib/system/remove_pacman_files \
  && rmdir /var/home

RUN \
  systemctl enable \
  atomic-state-overlay \
  os-daemon \
  os-checkupdates.timer \
  systemd-timesyncd \
  && chmod 400 /etc/sudoers \
  && chmod 644 /etc/pam.d/sudo{,-i}

ARG VERSION_ID HASH

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}" \
  hash="${HASH}"

RUN /usr/lib/system/set_variant
