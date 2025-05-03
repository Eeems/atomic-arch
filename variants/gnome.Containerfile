#syntax=docker/dockerfile:1.4
ARG VARIANT="Atomic"
ARG VARIANT_ID="atomic"
ARG VERSION_ID=$(uuidgen --time-v7 | cut -c-8)

FROM eeems/atomic-arch:base as ${VARIANT_ID}

LABEL \
  os-release.VARIANT="Gnome" \
  os-release.VARIANT_ID="gnome" \
  org.opencontainers.image.ref.name="gnome"

RUN /usr/lib/system/set_variant

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
