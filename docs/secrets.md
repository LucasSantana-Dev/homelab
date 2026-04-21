# Secrets Management

This homelab uses **SOPS** (Secrets Operations) with **age** encryption to manage secrets securely.

## Setup (One-time)

### Install Tools
```bash
brew install sops age
```

### Generate Age Key
```bash
age-keygen -o ~/.config/sops/age/keys.txt
chmod 600 ~/.config/sops/age/keys.txt
```

The public key will print to stdout; save it for reference.

### Set Environment Variable
```bash
export SOPS_AGE_KEY_FILE=$HOME/.config/sops/age/keys.txt
```

Add to your shell profile for persistence.

## Secrets Storage

- **.env**: Application environment variables. Add to `.gitignore` (already done).
- **Encrypted files**: Use `.sops.yaml` rules to designate which files encrypt automatically.
  - `*.enc.yaml` files will auto-encrypt on save.
  - Config files in `config/*/` can be marked `.enc.yaml`.

## Workflow

### Create/Edit a Secret
```bash
# Create a new encrypted file
sops config/.env.enc.yaml

# Edit existing encrypted file
sops path/to/file.enc.yaml

# View encrypted file (without editing)
sops -d path/to/file.enc.yaml | less
```

SOPS automatically encrypts on save if the file extension is `.enc.yaml` and `.sops.yaml` rule matches.

### Decrypt for Docker Compose
Scripts that load secrets should decrypt at runtime:
```bash
export $(sops -d .env.enc.yaml | xargs)
```

Or use SOPS_AGE_KEY_FILE environment variable in container context.

## .sops.yaml Rules

The `.sops.yaml` file defines which files encrypt with which age key:
- All `.enc.yaml` files use the local age key from `~/.config/sops/age/keys.txt`.
- Paths matching regex patterns in `creation_rules` auto-encrypt.

**Initial setup.** The `.sops.yaml` key field ships with an obvious
placeholder (`age1PLACEHOLDER…`). Running `sops -e` against it will
fail — that is intentional. Replace it with the *public* half of the
key printed by `age-keygen` above before encrypting any secrets in
this repo. No `.enc.yaml` files currently exist, so no re-encryption
is required on first setup.

## Rotation/Migration

If rotating the age key in the future:
1. Generate a new age key.
2. Update `.sops.yaml` with new key.
3. Re-encrypt all files:
   ```bash
   for file in **/*.enc.yaml; do
     sops -e -i "$file"
   done
   ```

## References

- SOPS: https://github.com/getsops/sops
- age: https://github.com/FiloSottile/age
- `.sops.yaml` config: https://github.com/getsops/sops#using-sopsyaml-conf-to-select-kms-pgp-age-key-files-to-encrypt-with
