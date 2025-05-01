#syntax=docker/dockerfile:1.4
FROM atomic-arch:base as gnome

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
