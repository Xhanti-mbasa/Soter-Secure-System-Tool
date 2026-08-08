# OpenVPN Custom Docker Documentation

> **Notice:** Adapted from official OpenVPN Access Server documentation for Arch Linux users building a custom, lightweight, zero-log container using Alpine Linux and OpenVPN Community Edition.

---

## 1. System Prerequisites & Docker Setup

Install Docker and enable the service on Arch Linux:

```bash
sudo pacman -S docker
sudo systemctl enable --now docker

```

Create and enter your project working directory:

```bash
mkdir -p ~/custom-openvpn && cd ~/custom-openvpn

```

---

## 2. Configuration Files

### `Dockerfile`

Create `Dockerfile` using `nvim Dockerfile`:

```dockerfile
FROM alpine:latest

# Install community OpenVPN, easy-rsa PKI tools, iptables, and bash
RUN apk add --no-cache openvpn easy-rsa iptables bash

WORKDIR /etc/openvpn
EXPOSE 1194/udp

# Default command runs OpenVPN with local server configuration
CMD ["openvpn", "--config", "/etc/openvpn/server.conf"]

```

### `server.conf`

Create `server.conf` using `nvim server.conf`:

```ini
# Network & Protocol Setup
port 1194
proto udp
dev tun

# PKI & Security Credentials
ca /etc/openvpn/pki/ca.crt
cert /etc/openvpn/pki/issued/server.crt
key /etc/openvpn/pki/private/server.key
dh /etc/openvpn/pki/dh.pem
tls-crypt /etc/openvpn/ta.key

# Cryptography & Performance Tuning
cipher AES-256-GCM
fast-io
sndbuf 524288
rcvbuf 524288
push "sndbuf 524288"
push "rcvbuf 524288"

# Anonymity & Zero-Log Policies
verb 0
mute-replay-warnings
push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 1.1.1.1"
explicit-exit-notify 1
persist-key
persist-tun

```

---

## 3. Image Build & PKI Key Generation

### Build the Image

```bash
docker build -t custom-openvpn .

```

### Generate Keys & Certificates (PKI Setup)

Run a temporary container to generate `ta.key` and build the Easy-RSA Certificate Authority, server certificate, and Diffie-Hellman parameters:

```bash
# Generate pre-shared tls-crypt key
docker run --rm -v $(pwd):/etc/openvpn custom-openvpn openvpn --genkey secret /etc/openvpn/ta.key

# Initialize Easy-RSA PKI and generate certificates
docker run --rm -v $(pwd):/etc/openvpn custom-openvpn bash -c "
  easyrsa init-pki && \
  echo 'custom-ca' | easyrsa build-ca nopass && \
  easyrsa build-server-full server nopass && \
  easyrsa gen-dh
"

```

---

## 4. Run the OpenVPN Container

Cleanup any crashing instances and start the operational container with network capabilities and volume mounts:

```bash
# Remove failed container instance if present
docker rm -f openvpn-server 2>/dev/null

# Launch OpenVPN Server
docker run -d \
  --name openvpn-server \
  --cap-add=NET_ADMIN \
  --device /dev/net/tun:/dev/net/tun \
  -p 1194:1194/udp \
  -v $(pwd):/etc/openvpn:ro \
  --restart unless-stopped \
  custom-openvpn

```

---

## 5. Verification & Debugging

Check container status to confirm `Up` state:

```bash
docker ps

```

If the container fails or restarts, inspect the runtime logs directly:

```bash
docker logs openvpn-server

```