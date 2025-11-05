#syntax=docker/dockerfile:1.4
ARG VARIANT="Base"
ARG VARIANT_ID="base"

FROM eeems/atomic-arch:rootfs

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
  run-parts \
  skopeo \
  pacman-contrib \
  python-pyxattr \
  python-requests \
  python-dbus \
  distrobox \
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
