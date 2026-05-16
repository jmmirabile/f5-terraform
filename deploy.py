#!/usr/bin/env python3
"""
Generate Terraform .tf files from CSV VIP definitions using Jinja2 templates.

Usage:
    python deploy.py lb1/vips.csv
    python deploy.py lb1/vips.csv --output-dir lb1/generated
    python deploy.py lb1/vips.csv --template templates/vip.tf.j2

    # Run terraform with credentials from keyring (FQDN looked up from directory name):
    python deploy.py lb1/vips.csv --plan --bigip-user admin
    python deploy.py lb1/vips.csv --apply --bigip-user admin

    # Or specify address explicitly:
    python deploy.py lb1/vips.csv --plan --bigip-address 192.168.1.245 --bigip-user admin
"""

import csv
import argparse
import os
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

try:
    import krcrud
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

try:
    import deviceBox
    HAS_DEVICEBOX = True
except ImportError:
    HAS_DEVICEBOX = False


def resolve_bigip_address(device_name: str, explicit_address: str = None) -> str:
    """Resolve BIG-IP address from device name or use explicit address."""
    if explicit_address:
        return explicit_address

    if not HAS_DEVICEBOX:
        raise RuntimeError(
            f"deviceBox module not found. Either install it (pip install deviceBox) "
            f"or provide --bigip-address explicitly"
        )

    # Look up FQDN from short device name using deviceBox
    fqdn = deviceBox.lookup(device_name)
    if not fqdn:
        raise RuntimeError(f"Could not resolve FQDN for device '{device_name}' using deviceBox")

    print(f"Resolved '{device_name}' -> '{fqdn}'")
    return fqdn


def parse_csv_row(row: dict, partition: str) -> dict:
    """Parse a CSV row and prepare context for Jinja2 template."""
    # Parse pool members (format: ip:port,ip:port)
    pool_members = []
    if row.get('pool_members'):
        pool_members = [m.strip() for m in row['pool_members'].split(',') if m.strip()]

    # Build profile lists
    client_profiles = []
    server_profiles = []
    profiles = []

    # TCP profile
    if row.get('tcp_profile'):
        client_profiles.append(f"/Common/{row['tcp_profile']}")

    # Client SSL (based on hostname)
    if row.get('hostname') and row.get('port') == '443':
        client_profiles.append(f"/{partition}/{row['hostname']}_clientssl")

    # Server SSL
    if row.get('serverssl_profile'):
        server_profiles.append(f"/Common/{row['serverssl_profile']}")

    # HTTP profile for port 443
    if row.get('port') == '443':
        profiles.append('/Common/http')

    # Build iRules list (ordered)
    irules = []
    for irule_field in ['irule1', 'irule2', 'irule3']:
        if row.get(irule_field):
            irules.append(f"/{partition}/{row[irule_field]}")

    return {
        'partition': partition,
        'vip_name': row['vip_name'],
        'vip_address': row['vip_address'],
        'port': row['port'],
        'hostname': row.get('hostname', ''),
        'pool_members': pool_members,
        'pool_monitor': row.get('pool_monitor', ''),
        'snatpool': row.get('snatpool', ''),
        'client_profiles': client_profiles,
        'server_profiles': server_profiles,
        'profiles': profiles,
        'irules': irules,
    }


def run_terraform(command: str, working_dir: Path, bigip_address: str, bigip_user: str, credential: str):
    """Run terraform with credentials from keyring."""
    if not HAS_KEYRING:
        raise RuntimeError("krcrud module not found. Install it or provide credentials via terraform.tfvars")

    # Get password from keyring
    password = krcrud.get_passwd(credential, bigip_user)
    if not password:
        raise RuntimeError(f"Could not retrieve password for {bigip_user} from keyring credential '{credential}'")

    # Set environment variables for terraform
    env = os.environ.copy()
    env['TF_VAR_bigip_address'] = bigip_address
    env['TF_VAR_bigip_username'] = bigip_user
    env['TF_VAR_bigip_password'] = password

    # Run terraform
    subprocess.run(['terraform', command], cwd=working_dir, env=env)


def main():
    parser = argparse.ArgumentParser(description='Generate Terraform files from CSV using Jinja2')
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--output-dir', '-o', help='Output directory (default: same as CSV)')
    parser.add_argument('--template', '-t', default='templates/vip.tf.j2', help='Jinja2 template path')
    parser.add_argument('--partition', '-p', default='Common', help='F5 partition (default: Common)')

    # Terraform execution options
    parser.add_argument('--init', action='store_true', help='Run terraform init')
    parser.add_argument('--plan', action='store_true', help='Run terraform plan')
    parser.add_argument('--apply', action='store_true', help='Run terraform apply')
    parser.add_argument('--destroy', action='store_true', help='Run terraform destroy')

    # Credential options (for --plan, --apply, --destroy)
    parser.add_argument('--bigip-address', help='BIG-IP address/FQDN (optional if deviceBox installed - uses directory name)')
    parser.add_argument('--bigip-user', default='admin', help='BIG-IP username (default: admin)')
    parser.add_argument('--credential', default='app_config', help='Keyring credential name (default: app_config)')

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    csv_path = Path(args.csv_file)
    output_dir = Path(args.output_dir) if args.output_dir else csv_path.parent
    template_path = script_dir / args.template

    output_dir.mkdir(parents=True, exist_ok=True)

    # Setup Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_path.name)

    # Process CSV
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)

        for row in reader:
            context = parse_csv_row(row, args.partition)
            tf_content = template.render(**context)

            output_file = output_dir / f"{context['vip_name']}.tf"
            with open(output_file, 'w') as out:
                out.write(tf_content)

            print(f"Generated: {output_file}")

    # Run terraform if requested
    if args.init or args.plan or args.apply or args.destroy:
        # Get device name from directory (e.g., lb1/vips.csv -> lb1)
        device_name = output_dir.name

        # Resolve FQDN from device name or use explicit address
        bigip_address = resolve_bigip_address(device_name, args.bigip_address)

        if args.init:
            subprocess.run(['terraform', 'init'], cwd=output_dir)

        if args.plan:
            run_terraform('plan', output_dir, bigip_address, args.bigip_user, args.credential)
        elif args.apply:
            run_terraform('apply', output_dir, bigip_address, args.bigip_user, args.credential)
        elif args.destroy:
            run_terraform('destroy', output_dir, bigip_address, args.bigip_user, args.credential)


if __name__ == '__main__':
    main()
