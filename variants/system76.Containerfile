#syntax=docker/dockerfile:1.4
FROM eeems/atomic-arch:eeems

ARG VARIANT="System76"
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

RUN /usr/lib/system/add_pacman_repository \
  --key=A64228CCD26972801C2CE6E3EC931EA46980BA1B \
  --server=https://repo.eeems.codes/\$repo \
  --server=https://repo.eeems.website/\$repo \
  eeems-system76 \
  && /usr/lib/system/remove_pacman_files

RUN /usr/lib/system/initialize_pacman \
  && /usr/lib/system/install_packages \
  system76-driver \
  system76-dkms \
  system76-acpi-dkms \
  system76-io-dkms \
  system76-power \
  system76-scheduler \
  system76-keyboard-configurator \
  firmware-manager \
  && /usr/lib/system/remove_pacman_files

RUN systemctl enable \
  system76 \
  system76-firmware-daemon \
  com.system76.PowerDaemon \
  com.system76.Scheduler

COPY overlay/system76 /
