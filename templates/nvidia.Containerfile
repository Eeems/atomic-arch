#syntax=docker/dockerfile:1.4
ARG BASE_VARIANT_ID
FROM eeems/atomic-arch:${BASE_VARIANT_ID}

RUN /usr/lib/system/initialize_pacman \
  && /usr/lib/system/install_packages \
  nvidia-open-dkms \
  nvidia-container-toolkit \
  nvidia-utils \
  nvidia-settings \
  && /usr/lib/system/remove_pacman_files
