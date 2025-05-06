#syntax=docker/dockerfile:1.4
FROM eeems/atomic-arch:base

ARG VARIANT="Atomic"
ARG VARIANT_ID="atomic"
ARG VERSION_ID

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}"

RUN /usr/lib/system/set_variant

RUN /usr/lib/system/install_packages \
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
  pavucontrol \
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
  dex \
  swaync \
  nwg-clipman \
  libnotify \
  waybar \
  fuzzel \
  brightnessctl \
  nm-connection-editor \
  gnome-power-manager \
  polkit-gnome \
  bluez-utils \
  switchboard \
  switchboard-plug-network \
  switchboard-plug-mouse-touchpad \
  switchboard-plug-display \
  switchboard-plug-wacom \
  switchboard-plug-printers

RUN /usr/lib/system/install_aur_packages \
  python-imageio-ffmpeg \
  python-screeninfo \
  waypaper \
  syshud \
  overskride

RUN systemctl enable greetd udisks2
COPY overlay/atomic /
