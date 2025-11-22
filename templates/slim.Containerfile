# syntax=docker/dockerfile:1.4
ARG BASE_VARIANT_ID

FROM arkes:${BASE_VARIANT_ID} AS build

RUN /usr/lib/system/initialize_pacman \
  && echo "[system] Installing bleachbit" \
  && mkdir -p /var/roothome/.config \
  && chronic pacman -S --noconfirm bleachbit \
  && echo "[system] Running bleachbit" \
  && chronic bleachbit --clean \
  system.cache \
  system.custom \
  system.desktop_entry \
  system.localizations \
  system.recent_documents \
  system.rotated_logs \
  system.tmp \
  system.trash \
  && echo "[system] Removing bleachbit" \
  && chronic pacman -R --noconfirm bleachbit \
  && echo "[system] Removing orphaned packages" \
  && pacman -Qqd | chronic pacman -Rsu --noconfirm - \
  && /usr/lib/system/remove_pacman_files \
  && echo "[system] Removing unneeded files from /usr" \
  && chronic find /usr/lib -name '.a' -exec rm -v {} \; \
  && chronic rm -rf \
  /usr/{include,share/{doc,info,man}} \
  /usr/lib/python*/test \
  && chronic find /usr/lib/python* -name '*.pyo' -exec rm -v {} \; \
  && /usr/lib/system/commit_layer

ARG \
  VARIANT \
  VARIANT_ID \
  VERSION_ID

RUN VARIANT="${VARIANT}" \
  VARIANT_ID="${VARIANT_ID}" \
  /usr/lib/system/set_variant \
  && /usr/lib/system/commit_layer

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
  os-release.NAME="${NAME}" \
  os-release.PRETTY_NAME="${PRETTY_NAME}" \
  os-release.ID="${ID}" \
  os-release.HOME_URL="${HOME_URL}" \
  os-release.BUG_REPORT_URL="${BUG_REPORT_URL}" \
  os-release.VERSION="${VERSION}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  org.opencontainers.image.authors="eeems@eeems.email" \
  org.opencontainers.image.source="https://github.com/Eeems/arkes" \
  org.opencontainers.image.ref.name="${VARIANT_ID}" \
  hash="${HASH}" \
  mirrorlist="${MIRRORLIST}"

WORKDIR /
ENTRYPOINT [ "/bin/bash" ]
