"""Interactive server setup. Run from sothis/; secrets are not printed."""
import argparse
import getpass
import os
import re
from pathlib import Path
from .auth import password_hash

ROOT = Path(__file__).resolve().parent.parent


def write_private(file, content):
    file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)


def main():
    parser = argparse.ArgumentParser(description='Configure the Sothis website on your server')
    parser.add_argument('--reset-password', action='store_true')
    parser.add_argument('--tunnel-token', action='store_true')
    args = parser.parse_args()
    if args.tunnel_token:
        token = getpass.getpass('Cloudflare Tunnel token (hidden): ').strip()
        if not re.fullmatch(r'[A-Za-z0-9_+/=-]{20,20000}', token):
            raise SystemExit('Token is not in the expected format.')
        write_private(ROOT / 'secrets/cloudflare-token', token + '\n')
        # cloudflared's non-root container must be able to read this bind-mounted
        # secret. Protect the host directory, not only its file mode.
        (ROOT / 'secrets').chmod(0o700)
        (ROOT / 'secrets/cloudflare-token').chmod(0o644)
        print('Tunnel token saved. The containing directory is private.')
        return
    env = ROOT / '.env'
    if env.exists() and not args.reset_password:
        raise SystemExit('Configuration exists. Use --reset-password to change the login, or --tunnel-token to save the tunnel token.')
    if args.reset_password:
        if not env.exists():
            raise SystemExit('Run setup without --reset-password first.')
        lines = env.read_text().splitlines()
    else:
        domain = input('Website hostname [sothis.xhantidaka.online]: ').strip() or 'sothis.xhantidaka.online'
        if not re.fullmatch(r'(?=.{1,253}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', domain) or '.' not in domain:
            raise SystemExit('Enter a hostname without https:// or a path.')
        username = input('Workspace username [xhanti]: ').strip() or 'xhanti'
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', username):
            raise SystemExit('Use letters, digits, dots, underscores or hyphens for the username.')
        lines = [f'SOTHIS_DOMAIN={domain.lower()}', f'SOTHIS_PUBLIC_ORIGIN=https://{domain.lower()}',
                 f'SOTHIS_USERNAME={username}', 'SOTHIS_BRAVE_API_KEY=']
    password = getpass.getpass('Workspace password (at least 12 characters, hidden): ')
    if password != getpass.getpass('Repeat password: '):
        raise SystemExit('Passwords do not match; configuration was not changed.')
    encoded = password_hash(password)
    lines = [line for line in lines if not line.startswith('SOTHIS_PASSWORD_HASH=')]
    lines.append('SOTHIS_PASSWORD_HASH=' + encoded)
    write_private(env, '\n'.join(lines) + '\n')
    print('Website configuration saved. Recreate the app container after a password reset.')


if __name__ == '__main__':
    main()
