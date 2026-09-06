# OpenVPN Custom Docker Documentation

> **Notice:** Optimized for Arch Linux running a Dockerized OpenVPN Community Edition container with host networking, OpenVPN Data Channel Offload (DCO), TCP MSS clamping, and automated client profile generation.

---

## 1. System Prerequisites & Host Preparation

Install Docker, enable packet forwarding, disable Wi-Fi power saving, expand interface transmit queue lengths, and create the working directory:

```bash
# Install Docker and enable service
sudo pacman -S docker
sudo systemctl enable --now docker

# Enable IPv4 Packet Forwarding
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" | sudo tee /etc/sysctl.d/30-openvpn-forward.conf

# Wireless Interface Performance Tuning
sudo iw dev wlan0 set power_save off
sudo ip link set dev wlan0 txqueuelen 2000

# Create project working directory
mkdir -p ~/custom-openvpn && cd ~/custom-openvpn

```

---

## 2. Host Firewall & NAT Routing (`iptables`)

Configure stateful forwarding, NAT masquerading, and TCP MSS clamping to prevent throughput bottlenecks and packet fragmentation across the TUN interface:

```bash
# Allow incoming OpenVPN traffic on UDP port 1194
sudo iptables -I INPUT 1 -p udp --dport 1194 -j ACCEPT

# Clamp TCP MSS to Path MTU (prevents stalled connections and packet drops)
sudo iptables -I FORWARD 1 -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu

# Forward VPN tunnel traffic through host WAN interface
sudo iptables -I FORWARD 2 -i tun+ -j ACCEPT
sudo iptables -I FORWARD 3 -i wlan0 -o tun+ -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o wlan0 -j MASQUERADE

# Enable iptables service and persist rules
sudo systemctl enable --now iptables
sudo iptables-save | sudo tee /etc/iptables/iptables.rules

```

---

## 3. Configuration Files

### `Dockerfile`

Create `Dockerfile`:

```dockerfile
FROM alpine:latest

# Install OpenVPN, Easy-RSA PKI tools, iptables, and bash
RUN apk add --no-cache openvpn easy-rsa iptables bash

WORKDIR /etc/openvpn
EXPOSE 1194/udp

# Execute OpenVPN using mounted server configuration
CMD ["openvpn", "--config", "/etc/openvpn/server.conf"]

```

### `server.conf`

Create `server.conf`:

```ini
# Server Mode & Subnet Topology
mode server
tls-server
topology subnet
server 10.8.0.0 255.255.255.0

# Network Protocol & Interface
port 1194
proto udp
dev tun

# PKI & Security Credentials
ca /etc/openvpn/pki/ca.crt
cert /etc/openvpn/pki/issued/server.crt
key /etc/openvpn/pki/private/server.key
dh /etc/openvpn/pki/dh.pem
tls-crypt /etc/openvpn/ta.key

# Cryptography
cipher AES-256-GCM
data-ciphers AES-256-GCM:AES-128-GCM

# Client Gateway & DNS Directives
push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 1.1.1.1"
push "dhcp-option DNS 1.0.0.1"

# MTU & MSS Optimization
tun-mtu 1500
mssfix 1360
push "mssfix 1360"

# Keepalive & Persistence
keepalive 10 120
explicit-exit-notify 1
persist-tun

# Logging & Warnings
verb 2
mute-replay-warnings

```

---

## 4. Build Image & Generate PKI Infrastructure

### Build Container Image

```bash
docker build -t custom-openvpn .

```

### Generate PKI Keys & Certificates (`OpenSSL`)

Create target directories and issue CA, server, client credentials, DH parameters, and `tls-crypt` key using temporary container runs:

```bash
mkdir -p pki/private pki/issued

# 1. Generate Certificate Authority (CA)
docker run --rm -v $(pwd):/etc/openvpn custom-openvpn openssl req -x509 -new -nodes \
  -keyout /etc/openvpn/pki/private/ca.key -sha256 -days 3650 \
  -out /etc/openvpn/pki/ca.crt -subj "/CN=OpenVPN-CA"

# 2. Generate and Sign Server Certificate
docker run --rm -v $(pwd):/etc/openvpn custom-openvpn openssl req -new -newkey rsa:2048 -nodes \
  -keyout /etc/openvpn/pki/private/server.key -out /etc/openvpn/server.req -subj "/CN=server"

docker run --rm -v $(pwd):/etc/openvpn custom-openvpn openssl x509 -req \
  -in /etc/openvpn/server.req -CA /etc/openvpn/pki/ca.crt \
  -CAkey /etc/openvpn/pki/private/ca.key -CAcreateserial \
  -out /etc/openvpn/pki/issued/server.crt -days 3650

# 3. Generate and Sign Client Certificate
docker run --rm -v $(pwd):/etc/openvpn custom-openvpn openssl req -new -newkey rsa:2048 -nodes \
  -keyout /etc/openvpn/pki/private/phone-client.key -out /etc/openvpn/phone-client.req -subj "/CN=phone-client"

docker run --rm -v $(pwd):/etc/openvpn custom-openvpn openssl x509 -req \
  -in /etc/openvpn/phone-client.req -CA /etc/openvpn/pki/ca.crt \
  -CAkey /etc/openvpn/pki/private/ca.key -CAcreateserial \
  -out /etc/openvpn/pki/issued/phone-client.crt -days 3650

# 4. Generate Diffie-Hellman Parameters & tls-crypt Key
docker run --rm -v $(pwd):/etc/openvpn custom-openvpn openssl dhparam -out /etc/openvpn/pki/dh.pem 2048
docker run --rm -v $(pwd):/etc/openvpn custom-openvpn openvpn --genkey secret /etc/openvpn/ta.key

```

---

## 5. Run OpenVPN Container (Host Network Mode)

Launch the container using `--net=host` to bypass Docker bridge network overhead, reduce UDP latency, and utilize Linux kernel Data Channel Offload (DCO):

```bash
# Cleanup previous instances
docker rm -f openvpn-server 2>/dev/null

# Start Container
docker run -d \
  --name openvpn-server \
  --net=host \
  --cap-add=NET_ADMIN \
  --device /dev/net/tun:/dev/net/tun \
  -v $(pwd):/etc/openvpn:ro \
  --restart unless-stopped \
  custom-openvpn

```

---

## 6. Client Profile Generation (`phone-client.ovpn`)

Generate a unified client profile containing embedded keys and certificates for OpenVPN Connect:

```bash
SERVER_IP="192.168.18.68" # Replace with host LAN IP

cat << EOF > phone-client.ovpn
client
dev tun
proto udp
remote ${SERVER_IP} 1194
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher AES-256-GCM
verb 3

<ca>
$(cat pki/ca.crt)
</ca>

<cert>
$(cat pki/issued/phone-client.crt)
</cert>

<key>
$(cat pki/private/phone-client.key)
</key>

<tls-crypt>
$(cat ta.key)
</tls-crypt>
EOF

```

---

## 7. Verification & Debugging

Verify running container status and inspect live logs for successful TLS handshakes:

```bash
# Check container status
docker ps

# Stream runtime logs
docker logs -f openvpn-server

```
