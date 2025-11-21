# syntax=docker/dockerfile:1.4
ARG ARCHIVE_YEAR=2025
ARG ARCHIVE_MONTH=11
ARG ARCHIVE_DAY=19
ARG PACSTRAP_TAG=20250427.0.341977
ARG HASH
ARG VERSION_ID

FROM golang:1.25.4-alpine as dockerfile2llbjson

WORKDIR /app
COPY tools/dockerfile2llbjson/go.mod tools/dockerfile2llbjson/go.sum ./
RUN go mod download
COPY tools/dockerfile2llbjson/main.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /app/dockerfile2llbjson .

FROM docker.io/library/archlinux:base-devel-${PACSTRAP_TAG} AS pacstrap

ARG \
  ARCHIVE_YEAR \
  ARCHIVE_MONTH \
  ARCHIVE_DAY

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

COPY overlay/rootfs /overlay
COPY --from=dockerfile2llbjson /app/dockerfile2llbjson /overlay/usr/bin/dockerfile2llbjson

RUN rm usr/share/libalpm/hooks/60-mkinitcpio-remove.hook \
  && rm usr/share/libalpm/hooks/90-mkinitcpio-install.hook \
  && cp -a {/,}etc/pacman.d/mirrorlist \
  && rm -rf home && ln -s var/home home \
  && rm -rf mnt && ln -s var/mnt mnt \
  && rm -rf root && ln -s var/roothome root \
  && rm -rf srv && ln -s var/srv srv \
  && rm -rf usr/local && ln -s ../var/usrlocal usr/local \
  && truncate -s 0 etc/machine-id \
  && cp -a /overlay/. /rootfs/. \
  && cd / \
  && tar --sort=name \
  --owner=0 --group=0 \
  --numeric-owner \
  --pax-option=exthdr.name=%d/PaxHeaders/%p,delete=atime,delete=ctime \
  --mtime="@946684800" \
  -C rootfs \
  -cf rootfs.tar . \
  && rm -rf rootfs \
  && mkdir rootfs \
  && tar -C rootfs -xf rootfs.tar \
  && rm rootfs.tar \
  && /overlay/usr/lib/system/commit_layer /rootfs

FROM scratch AS rootfs

ARG \
  ARCHIVE_YEAR \
  ARCHIVE_MONTH \
  ARCHIVE_DAY \
  PACSTRAP_TAG \
  HASH

LABEL \
  os-release.NAME="Arkēs" \
  os-release.PRETTY_NAME="Arkēs Arch Linux" \
  os-release.ID="arkes" \
  os-release.HOME_URL="https://github.com/Eeems/arkes" \
  os-release.BUG_REPORT_URL="https://github.com/Eeems/arkes/issues" \
  os-release.VERSION="${ARCHIVE_YEAR}.${ARCHIVE_MONTH}.${ARCHIVE_DAY}" \
  os-release.VERSION_ID="${ARCHIVE_YEAR}.${ARCHIVE_MONTH}.${ARCHIVE_DAY}" \
  org.opencontainers.image.authors="eeems@eeems.email" \
  org.opencontainers.image.source="https://github.com/Eeems/arkes" \
  org.opencontainers.image.ref.name="rootfs" \
  org.opencontainers.image.description="Atomic and immutable Linux distribution as a container." \
  hash="${HASH}" \
  mirrorlist="[ \
  \"https://archive.archlinux.org/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch\", \
  \"https://america.archive.pkgbuild.com/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch\", \
  \"https://asia.archive.pkgbuild.com/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch\", \
  \"https://europe.archive.pkgbuild.com/repos/${ARCHIVE_YEAR}/${ARCHIVE_MONTH}/${ARCHIVE_DAY}/\$repo/os/\$arch\" \
  ]"

WORKDIR /

COPY --from=pacstrap /rootfs /

RUN  echo 'NAME="Arkēs"' > /usr/lib/os-release \
  && echo 'PRETTY_NAME="Arkēs Arch Linux"' >> /usr/lib/os-release \
  && echo 'ID=arkes' >> /usr/lib/os-release \
  && echo 'HOME_URL="https://github.com/Eeems/arkes"' >> /usr/lib/os-release \
  && echo 'SUPPORT_URL="https://github.com/Eeems/arkes/issues"' >> /usr/lib/os-release \
  && echo 'BUG_REPORT_URL="https://github.com/Eeems/arkes/issues"' >> /usr/lib/os-release \
  && echo "VERSION=${ARCHIVE_YEAR}.${ARCHIVE_MONTH}.${ARCHIVE_DAY}" >> /usr/lib/os-release \
  && echo "VERSION_ID=${ARCHIVE_YEAR}.${ARCHIVE_MONTH}.${ARCHIVE_DAY}" >> /usr/lib/os-release \
  && echo "VARIANT=Base" >> /usr/lib/os-release \
  && echo "VARIANT_ID=base" >> /usr/lib/os-release \
  && /usr/lib/system/commit_layer

ENTRYPOINT [ "/bin/bash" ]
