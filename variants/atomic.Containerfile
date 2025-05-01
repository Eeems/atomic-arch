#syntax=docker/dockerfile:1.4
FROM atomic-arch:base as atomic

RUN /usr/lib/system/set_variant atomic Atomic

RUN /usr/lib/system/install_packages \
  ghostty \
  gnome-software \
  flatpak-xdg-utils \
  fwupd \
  greetd-tuigreet \
  niri \
  xdg-desktop-portal-gnome \
  xwayland-satellite \
  fuzzel \
  gnome-keyring \
  nautilus \
  power-profiles-daemon \
  pavucontrol \
  python-numpy \
  waybar \
  pipewire-audio \
  pipewire-pulse \
  swww \
  hyprlock \
  gamescope \
  vulkan-swrast

RUN /usr/lib/system/install_aur_packages \
  python-imageio \
  python-imageio-ffmpeg \
  python-screeninfo \
  waypaper

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

RUN systemctl enable greetd
COPY overlay/atomic /
