#syntax=docker/dockerfile:1.4
FROM eeems/atomic-arch:system76

ARG VARIANT="System76 (nvidia)"
ARG VARIANT_ID="system76"
ARG VERSION_ID
ARG HASH

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}" \
  hash="${HASH}"

RUN /usr/lib/system/set_variant

RUN /usr/lib/system/initialize_pacman \
  && /usr/lib/system/install_packages \
  nvidia-open-dkms \
  nvidia-container-toolkit \
  nvidia-utils \
  nvidia-settings \
  && /usr/lib/system/remove_pacman_files
