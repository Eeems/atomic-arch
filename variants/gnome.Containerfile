#syntax=docker/dockerfile:1.4
FROM eeems/atomic-arch:base

ARG VARIANT="gnome"
ARG VARIANT_ID="GNOME"
ARG VERSION_ID

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}"

RUN /usr/lib/system/set_variant

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
