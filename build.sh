#!/bin/bash
set -e

if (($EUID != 0)); then
  echo 'Must be run as root'
  exit 1
fi

TAG=${1:-gnome}
SYSTEM_PATH=${2:-/var/lib/system}

mkdir -p "${SYSTEM_PATH}"

if [ -d /ostree ]; then
  OSTREE_PATH="/ostree"
  ln -sf /ostree "${SYSTEM_PATH}"
else
  OSTREE_PATH="${SYSTEM_PATH}/ostree"
  mkdir -p "${SYSTEM_PATH}/ostree"
  if ! [ -d "${SYSTEM_PATH}/ostree/repo" ]; then
    ostree --repo="${SYSTEM_PATH}/ostree/repo" init
  fi
fi

podman build \
  --target "${TAG}" \
  --tag "atomic-arch:${TAG}" \
  --force-rm \
  .
podman run \
  --rm \
  --privileged \
  --security-opt label=disable \
  --volume "/run/podman/podman.sock:/run/podman/podman.sock" \
  --volume "${SYSTEM_PATH}:/var/lib/system" \
  --volume "${OSTREE_PATH}:/ostree" \
  --entrypoint /usr/bin/os \
  "atomic-arch:${TAG}" \
  build
podman run \
  --rm \
  --privileged \
  --security-opt label=disable \
  --volume "/run/podman/podman.sock:/run/podman/podman.sock" \
  --volume "${SYSTEM_PATH}:/var/lib/system" \
  --volume "${OSTREE_PATH}:/ostree" \
  --entrypoint /usr/bin/os \
  "atomic-arch:${TAG}" \
  iso
