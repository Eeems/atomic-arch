#syntax=docker/dockerfile:1.4
ARG VARIANT="gNOME"
ARG VARIANT_ID="GNOME"

FROM eeems/atomic-arch:base as ${VARIANT_ID}

ARG VARIANT
ARG VARIANT_ID
ARG VERSION_ID

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}"

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
