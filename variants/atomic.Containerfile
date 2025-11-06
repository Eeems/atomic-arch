#syntax=docker/dockerfile:1.4
FROM eeems/atomic-arch:base

ARG \
  VARIANT="Atomic" \
  VARIANT_ID="atomic"

RUN /usr/lib/system/initialize_pacman \
  && /usr/lib/system/install_packages \
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
  && /usr/lib/system/install_aur_packages \
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
  && /usr/lib/system/remove_pacman_files

RUN systemctl enable \
  greetd \
  udisks2

COPY overlay/atomic /
RUN systemctl enable dconf

ARG VERSION_ID HASH

LABEL \
  os-release.VARIANT="${VARIANT}" \
  os-release.VARIANT_ID="${VARIANT_ID}" \
  os-release.VERSION_ID="${VERSION_ID}" \
  org.opencontainers.image.ref.name="${VARIANT_ID}" \
  hash="${HASH}"

RUN /usr/lib/system/set_variant
