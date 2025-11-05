#syntax=docker/dockerfile:1.4
ARG VARIANT="GNOME"
ARG VARIANT_ID="gnome"

FROM eeems/atomic-arch:base

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
