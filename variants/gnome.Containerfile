# syntax=docker/dockerfile:1.4
# x-depends=base
ARG HASH

FROM arkes:base as overlay

COPY overlay/gnome /overlay
RUN /usr/lib/system/commit_layer /overlay

FROM arkes:base

ARG \
  VARIANT="GNOME" \
  VARIANT_ID="gnome"

RUN /usr/lib/system/package_layer \
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

RUN systemctl enable gdm \
  && /usr/lib/system/commit_layer

COPY --from=overlay /overlay /

ARG VERSION_ID HASH

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}" \
  hash="${HASH}"

RUN /usr/lib/system/set_variant \
  && /usr/lib/system/commit_layer
