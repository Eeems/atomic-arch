#!/bin/bash
set -e

if (($EUID != 0)); then
  echo 'Must be run as root'
  exit 1
fi

TAG=${1:-gnome}
podman build \
  --target "$TAG" \
  --tag "atomic-arch:$TAG" \
  .
podman run \
  --rm \
  --privileged \
  --security-opt label=disable \
  --volume "/run/podman/podman.sock:/run/podman/podman.sock" \
  --entrypoint /usr/bin/os \
  "atomic-arch:$TAG" \
  build
mkdir -p build
podman run \
  --rm \
  --privileged \
  --security-opt label=disable \
  --volume "/run/podman/podman.sock:/run/podman/podman.sock" \
  --volume ./build:/var/lib/system \
  --entrypoint /usr/bin/os \
  "atomic-arch:$TAG" \
  iso
