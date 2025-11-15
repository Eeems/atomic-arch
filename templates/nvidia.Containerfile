# syntax=docker/dockerfile:1.4
ARG BASE_VARIANT_ID

FROM ghcr.io/eeems/atomic-arch:${BASE_VARIANT_ID}

RUN /usr/lib/system/initialize_pacman \
  && /usr/lib/system/install_packages \
  nvidia-open-dkms \
  nvidia-container-toolkit \
  nvidia-utils \
  nvidia-settings \
  && /usr/lib/system/remove_pacman_files

ARG \
  VARIANT \
  VARIANT_ID \
  VERSION_ID \
  HASH

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}" \
  hash="${HASH}"

RUN /usr/lib/system/set_variant
