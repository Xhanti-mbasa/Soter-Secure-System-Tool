# Secure

Permission-based, low-impact web security assessment orchestration for small businesses.

## Start

```bash
cp .env.example .env
# Replace every placeholder secret in .env
docker compose up -d --build
curl http://127.0.0.1:8100/api/v1/health
```

Submit an authorized Quick Scan:

```bash
curl -X POST http://127.0.0.1:8100/api/v1/scans \
  -H "Authorization: Bearer $SECURE_ADMIN_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"target":"https://example.com","profile":"quick","authorization":{"confirmed":true,"customer_name":"Example Pty Ltd","authorized_by":"Jane Doe"}}'
```

The API is bound to `127.0.0.1:8100`. Postgres, Redis, the worker, and ZAP have no host ports. Point Cloudflare Tunnel at `http://127.0.0.1:8100`.

## Safety

Production rejects loopback, private, link-local, multicast, reserved, and non-global targets. Quick Scan uses conservative concurrency and request rates. Verified and active scanning are deliberately blocked until ownership verification is implemented.

Set `DEV_ALLOW_PRIVATE_TARGETS=true` only in an isolated local development override.
