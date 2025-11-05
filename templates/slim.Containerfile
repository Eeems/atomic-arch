#syntax=docker/dockerfile:1.4
ARG VARIANT_ID
FROM eeems/atomic-arch:${VARIANT_ID} AS build

ARG VARIANT
ARG VERSION_ID
ARG HASH

LABEL \
  os-release.VARIANT="${VARIANT} (slim)" \
  os-release.VARIANT_ID="${VARIANT_ID}-slim" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}-slim" \
  hash="${HASH}"

RUN VARIANT="${VARIANT} (slim)" \
  VARIANT_ID="${VARIANT_ID}-slim" \
  /usr/lib/system/set_variant

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

FROM scratch

COPY --from=build / /
