#!/bin/bash

# Call Rust binary, capture output, set as environment variables
eval $(../sysinfo/target/release/sysinfo)

# Now $DISTRO and $PKG_MANAGER are available globally
echo "Detected: $DISTRO with $PKG_MANAGER"

# VPN menu
echo "Select VPN:"
echo "1) ProtonVPN"
echo "2) Windscribe"
echo "3) OpenVPN"
read -p "Enter choice (1-3): " choice

# Install function (uses detected variables)
install_vpn() {
  local vpn=$1

  case "$PKG_MANAGER" in
  apt-get)
    sudo apt-get update && sudo apt-get install -y "$vpn"
    ;;
  pacman)
    sudo pacman -S "$vpn"
    ;;
  dnf)
    sudo dnf install -y "$vpn"
    ;;
  yum)
    sudo yum install -y "$vpn"
    ;;
  *)
    echo "Unsupported package manager: $PKG_MANAGER"
    exit 1
    ;;
  esac
}

case $choice in
1)
  install_vpn "protonvpn-cli"
  ;;
2)
  install_vpn "windscribe-cli"
  ;;
3)
  install_vpn "openvpn"
  ;;
*)
  echo "Invalid choice"
  exit 1
  ;;
esac
