# F5 Terraform VIP Generator

Generate Terraform configurations for F5 BIG-IP LTM VIPs from CSV spreadsheets.

## Features

- Define VIPs in simple CSV format
- Jinja2 templates for customizable output
- iRules as code (version controlled `.tcl` files)
- Keyring integration for secure credential storage
- Device name lookup via deviceBox

## Project Structure

```
f5-terraform/
├── deploy.py                 # Main script
├── templates/
│   └── vip.tf.j2             # Jinja2 template for TF output
└── <device_name>/            # One folder per F5 device
    ├── vips.csv              # VIP definitions
    ├── provider.tf           # Terraform provider config
    ├── irules/               # iRule .tcl files (optional)
    │   └── redirect_http.tcl
    └── *.tf                  # Generated Terraform files
```

## Quick Start

### 1. Clone and Setup

```bash
git clone git@github:jmmirabile/f5-terraform.git
cd f5-terraform

# Rename lb1 to your device's short name (used by deviceBox)
mv lb1 labf5
```

### 2. Edit the CSV

Edit `labf5/vips.csv` with your VIP configuration:

```csv
vip_name,vip_address,port,hostname,pool_members,snatpool,irule1,irule2,irule3,pool_monitor,tcp_profile,serverssl_profile
my_app,10.100.1.100,443,www.example.com,"10.0.1.10:8080,10.0.1.11:8080",my_snatpool,redirect_http,,,http,tcp-wan-optimized,
```

### 3. Initialize Terraform

```bash
python3 deploy.py labf5/vips.csv --init
```

### 4. Plan (Preview Changes)

```bash
python3 deploy.py labf5/vips.csv --plan --bigip-user admin
```

### 5. Apply

```bash
python3 deploy.py labf5/vips.csv --apply --bigip-user admin
```

## CSV Columns

| Column | Required | Description |
|--------|----------|-------------|
| `vip_name` | Yes | Name for the VIP, pool, etc. |
| `vip_address` | Yes | VIP IP address |
| `port` | Yes | VIP port (e.g., 443, 80) |
| `hostname` | No | Used for client SSL profile name |
| `pool_members` | Yes | Comma-separated `ip:port` pairs |
| `snatpool` | No | SNAT pool name (blank = automap) |
| `irule1`, `irule2`, `irule3` | No | iRules in order |
| `pool_monitor` | No | Health monitor name |
| `tcp_profile` | No | TCP profile name |
| `serverssl_profile` | No | Server SSL profile name |

## iRules as Code

Place `.tcl` files in `<device>/irules/` to have Terraform manage them:

```
labf5/irules/redirect_http.tcl
```

- **File exists locally**: Terraform creates/manages the iRule
- **No local file**: Assumes iRule exists on F5 (static reference)

## Command Reference

```bash
# Generate .tf files only (no terraform)
python3 deploy.py labf5/vips.csv

# Generate + terraform init
python3 deploy.py labf5/vips.csv --init

# Generate + terraform plan
python3 deploy.py labf5/vips.csv --plan --bigip-user admin

# Generate + terraform apply
python3 deploy.py labf5/vips.csv --apply --bigip-user admin

# Generate + terraform destroy
python3 deploy.py labf5/vips.csv --destroy --bigip-user admin

# Override device address (skip deviceBox lookup)
python3 deploy.py labf5/vips.csv --plan --bigip-address 192.168.1.245 --bigip-user admin

# Use different keyring credential
python3 deploy.py labf5/vips.csv --plan --bigip-user admin --credential my_cred
```

## Dependencies

**Required:**
- Python 3.8+
- Jinja2: `pip install jinja2`
- Terraform with F5 provider

**Optional (for --plan/--apply/--destroy):**
- krcrud: Keyring credential retrieval
- deviceBox: Device name to FQDN lookup

## Notes

- Generated `.tf` files are recreated each run from the CSV
- Terraform state is stored per-device in `<device>/terraform.tfstate`
- Objects referenced in CSV (monitors, snatpools, profiles) must exist on the F5 unless managed by Terraform
