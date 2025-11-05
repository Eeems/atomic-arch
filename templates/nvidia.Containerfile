#syntax=docker/dockerfile:1.4
ARG VARIANT_ID
FROM eeems/atomic-arch:${VARIANT_ID}

ARG VARIANT
ARG VERSION_ID
ARG HASH

LABEL \
  os-release.VARIANT="${VARIANT} (nvidia)" \
  os-release.VARIANT_ID="${VARIANT_ID}-nvidia" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}-nvidia" \
  hash="${HASH}"

RUN VARIANT="${VARIANT} (nvidia)" \
  VARIANT_ID="${VARIANT_ID}-nvidia" \
  /usr/lib/system/set_variant

RUN /usr/lib/system/initialize_pacman \
  && /usr/lib/system/install_packages \
  nvidia-open-dkms \
  nvidia-container-toolkit \
  nvidia-utils \
  nvidia-settings \
  && /usr/lib/system/remove_pacman_files
