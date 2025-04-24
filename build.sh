#!/bin/bash
set -e
podman build \
  --target gnome \
  --tag atomic-arch:gnome \
  .
podman run \
  --rm \
  --privileged \
  --security-opt label=disable \
  --volume $XDG_RUNTIME_DIR/podman/podman.sock:/run/podman/podman.sock \
  --entrypoint /usr/bin/os \
  atomic-arch:gnome \
  build
