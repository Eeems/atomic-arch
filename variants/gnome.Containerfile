#syntax=docker/dockerfile:1.4
FROM eeems/atomic-arch:base

ARG VARIANT="GNOME"
ARG VARIANT_ID="gnome"

ARG \
  VARIANT="GNOME" \
  VARIANT_ID="gnome" \
  VERSION_ID \
  HASH

RUN /usr/lib/system/initialize_pacman \
  && /usr/lib/system/install_packages \
  gdm \
  gnome-shell \
  ghostty \
  xorg-server \
  gnome-software \
  flatpak-xdg-utils \
  gnome-packagekit \
  fwupd \
  gnome-tweaks \
  gnome-control-center \
  && /usr/lib/system/remove_pacman_files

RUN systemctl enable gdm
COPY overlay/gnome /
