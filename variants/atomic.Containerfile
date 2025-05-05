#syntax=docker/dockerfile:1.4
ARG VARIANT="Atomic"
ARG VARIANT_ID="atomic"

FROM eeems/atomic-arch:base as  ${VARIANT_ID}

ARG VARIANT
ARG VARIANT_ID
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

# RUN /usr/lib/system/install_aur_packages \
#   libastal-io-git \
#   libastal-git \
#   libastal-gjs-git \
#   libastal-4-git \
#   libastal-apps-git \
#   libastal-auth-git \
#   libastal-battery-git \
#   libastal-bluetooth-git \
#   libcava \
#   libastal-cava-git \
#   libastal-greetd-git \
#   libastal-hyprland-git \
#   libastal-mpris-git \
#   libastal-network-git \
#   libastal-notifd-git \
#   libastal-powerprofiles-git \
#   libastal-river-git \
#   appmenu-glib-translator-git \
#   libastal-tray-git \
#   libastal-wireplumber-git \
#   libastal-meta \
#   aylurs-gtk-shell-git \
#   ags-hyprpanel-git

RUN systemctl enable greetd udisks2
COPY overlay/atomic /
