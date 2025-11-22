# syntax=docker/dockerfile:1.4
# x-depends=base
# x-templates=nvidia
ARG HASH

FROM arkes:base as overlay

COPY overlay/atomic /overlay
RUN /usr/lib/system/commit_layer /overlay

FROM arkes:base

ARG \
  VARIANT="Atomic" \
  VARIANT_ID="atomic"

RUN /usr/lib/system/package_layer \
  ghostty \
  gnome-software \
  flatpak-xdg-utils \
  fwupd \
  greetd-tuigreet \
  niri \
  xdg-desktop-portal-gnome \
  xwayland-satellite \
  gnome-keyring \
  nautilus \
  power-profiles-daemon \
  python-numpy \
  pipewire-audio \
  pipewire-pulse \
  swww \
  hyprlock \
  hypridle \
  gamescope \
  vulkan-swrast \
  ttf-roboto-mono-nerd \
  noto-fonts-emoji \
  adw-gtk-theme \
  swaync \
  nwg-clipman \
  libnotify \
  waybar \
  fuzzel \
  brightnessctl \
  nm-connection-editor \
  gnome-power-manager \
  gnome-disk-utility \
  polkit-gnome \
  bluez-utils \
  system-config-printer \
  dex \
  --aur \
  python-imageio-ffmpeg \
  python-screeninfo \
  waypaper \
  syshud \
  overskride \
  networkmanager-dmenu-git \
  distroshelf \
  libwireplumber-4.0-compat \
  pwvucontrol \
  wego \
  prelockd

RUN systemctl enable \
  greetd \
  udisks2 \
  && /usr/lib/system/commit_layer

COPY --from=overlay /overlay /

RUN systemctl enable \
  dconf.service \
  prelockd.service \
  && /usr/lib/system/commit_layer

ARG VERSION_ID HASH

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}" \
  hash="${HASH}"

RUN /usr/lib/system/set_variant \
  && /usr/lib/system/commit_layer
