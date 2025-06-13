#syntax=docker/dockerfile:1.4
ARG ARCHIVE_YEAR=2025
ARG ARCHIVE_MONTH=06
ARG ARCHIVE_DAY=13
ARG PACSTRAP_TAG=20250427.0.341977

FROM docker.io/library/archlinux:base-devel-${PACSTRAP_TAG} AS pacstrap

ARG ARCHIVE_YEAR
ARG ARCHIVE_MONTH
ARG ARCHIVE_DAY

RUN \
  echo "Server = https://archive.archlinux.org/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch" > /etc/pacman.d/mirrorlist \
  && echo "Server = https://america.archive.pkgbuild.com/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch" >> /etc/pacman.d/mirrorlist \
  && echo "Server = https://asia.archive.pkgbuild.com/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch" >> /etc/pacman.d/mirrorlist \
  && echo "Server = https://europe.archive.pkgbuild.com/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch" >> /etc/pacman.d/mirrorlist
RUN pacman-key --init \
  && pacman -Sy --needed --noconfirm archlinux-keyring moreutils
RUN mkdir /rootfs
WORKDIR /rootfs
RUN mkdir -m 0755 -p var/{cache/pacman/pkg,lib/pacman,log} dev run etc \
  && mkdir -m 1777 tmp \
  && mkdir -m 0555 sys proc
RUN chronic fakeroot pacman -r . -Sy --noconfirm base mkinitcpio moreutils
RUN rm usr/share/libalpm/hooks/60-mkinitcpio-remove.hook \
  && rm usr/share/libalpm/hooks/90-mkinitcpio-install.hook \
  && cp -a {/,}etc/pacman.d/mirrorlist \
  && rm -rf home && ln -s var/home home \
  && rm -rf mnt && ln -s var/mnt mnt \
  && rm -rf root && ln -s var/roothome root \
  && rm -rf srv && ln -s var/srv srv \
  && rm -rf usr/local && ln -s ../var/usrlocal usr/local

FROM scratch AS rootfs

ARG ARCHIVE_YEAR
ARG ARCHIVE_MONTH
ARG ARCHIVE_DAY
ARG PACSTRAP_TAG
ARG HASH

LABEL \
  os-release.NAME="Atomic Arch" \
  os-release.PRETTY_NAME="Atomic Arch Linux" \
  os-release.ID="atomic-arch" \
  os-release.HOME_URL="https://github.com/Eeems/atomic-arch" \
  os-release.BUG_REPORT_URL="https://github.com/Eeems/atomic-arch/issues" \
  os-release.VERSION="${ARCHIVE_YEAR}.${ARCHIVE_MONTH}.${ARCHIVE_DAY}" \
  os-release.VERSION_ID="${ARCHIVE_YEAR}.${ARCHIVE_MONTH}.${ARCHIVE_DAY}" \
  org.opencontainers.image.authors="eeems@eeems.email" \
  org.opencontainers.image.source="https://github.com/Eeems/atomic-arch" \
  org.opencontainers.image.ref.name="rootfs" \
  hash="${HASH}"

WORKDIR /
COPY --from=pacstrap /rootfs /
COPY overlay/rootfs /

RUN  echo 'NAME="Atomic Arch"' > /usr/lib/os-release \
  && echo 'PRETTY_NAME="Atomic Arch Linux"' >> /usr/lib/os-release \
  && echo 'ID=atomic-arch' >> /usr/lib/os-release \
  && echo 'HOME_URL="https://github.com/Eeems/atomic-arch"' >> /usr/lib/os-release \
  && echo 'SUPPORT_URL="https://github.com/Eeems/atomic-arch/issues"' >> /usr/lib/os-release \
  && echo 'BUG_REPORT_URL="https://github.com/Eeems/atomic-arch/issues"' >> /usr/lib/os-release \
  && echo "VERSION=${ARCHIVE_YEAR}.${ARCHIVE_MONTH}.${ARCHIVE_DAY}" >> /usr/lib/os-release \
  && echo "VERSION_ID=${ARCHIVE_YEAR}.${ARCHIVE_MONTH}.${ARCHIVE_DAY}" >> /usr/lib/os-release \
  && echo "VARIANT=Base" >> /usr/lib/os-release \
  && echo "VARIANT_ID=base" >> /usr/lib/os-release

ENTRYPOINT [ "/bin/bash" ]
