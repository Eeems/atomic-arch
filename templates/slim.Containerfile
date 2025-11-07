#syntax=docker/dockerfile:1.4
ARG BASE_VARIANT_ID

FROM eeems/atomic-arch:${BASE_VARIANT_ID} AS build

RUN /usr/lib/system/initialize_pacman \
  && echo "[system] Removing orphaned packages" \
  && pacman -Qqd | chronic pacman -Rsu --noconfirm - \
  && /usr/lib/system/remove_pacman_files \
  && echo "[system] Removing unneeded files from /usr" \
  && chronic find /usr/lib -name '.a' -exec rm -v {} \; \
  && chronic rm -rf \
  /usr/{include,share/{doc,info,man}} \
  /usr/lib/python*/test \
  && chronic find /usr/lib/python* -name '*.pyo' -exec rm -v {} \;

ARG \
  VARIANT \
  VARIANT_ID

RUN VARIANT="${VARIANT}" \
  VARIANT_ID="${VARIANT_ID}" \
  /usr/lib/system/set_variant

FROM scratch

COPY --from=build / /

ARG \
  VARIANT \
  VARIANT_ID \
  VERSION \
  VERSION_ID \
  MIRRORLIST \
  HASH \
  NAME \
  PRETTY_NAME \
  ID \
  HOME_URL \
  BUG_REPORT_URL

LABEL \
  os-release.NAME="Atomic Arch" \
  os-release.PRETTY_NAME="Atomic Arch Linux" \
  os-release.ID="atomic-arch" \
  os-release.HOME_URL="https://github.com/Eeems/atomic-arch" \
  os-release.BUG_REPORT_URL="https://github.com/Eeems/atomic-arch/issues" \
  os-release.VERSION="${VERSION}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  org.opencontainers.image.authors="eeems@eeems.email" \
  org.opencontainers.image.source="https://github.com/Eeems/atomic-arch" \
  org.opencontainers.image.ref.name="${VARIANT_ID}" \
  hash="${HASH}" \
  mirrorlist="${MIRRORLIST}"

