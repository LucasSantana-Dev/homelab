# Secrets Management

This homelab uses **SOPS** (Secrets Operations) with **age** encryption to manage secrets securely.

## Activation (one-time — fixes the secret SPOF)

Until this is done, every secret — including **`KOPIA_REPO_PASSWORD`**, the master
key for the kopia backup repo — exists only as a **single plaintext copy** in the
host `.env`. Lose it and the kopia repo is permanently undecryptable. Activation
stores an **encrypted, git-committed** copy (`.env.enc`) plus a recovery key in
your password manager, so secrets survive a host loss.

Run on the host (where the real `.env` lives):

1. **Generate the age key** (the one thing you must never lose):
   ```bash
   mkdir -p ~/.config/sops/age
   age-keygen -o ~/.config/sops/age/keys.txt && chmod 600 ~/.config/sops/age/keys.txt
   ```
   It prints `# public key: age1...`.

2. **Back up the age PRIVATE key off-host — this is the SPOF fix.** Copy the full
   contents of `~/.config/sops/age/keys.txt` into your **password manager** (and/or
   an offline copy). With this key + the committed `.env.enc` you can recover every
   secret even if the host is gone.

3. **Wire the public key** into `.sops.yaml`: replace the `age1PLACEHOLDER…` value
   with the `age1...` **public** key from step 1.

4. **Export the key path** so sops can decrypt:
   ```bash
   echo 'export SOPS_AGE_KEY_FILE=$HOME/.config/sops/age/keys.txt' >> ~/.bashrc
   export SOPS_AGE_KEY_FILE=$HOME/.config/sops/age/keys.txt
   ```

5. **Encrypt → verify → commit:**
   ```bash
   make sops-encrypt    # .env -> .env.enc (values encrypted; keys stay readable)
   make sops-verify     # asserts .env.enc round-trips back to .env exactly
   git add .sops.yaml .env.enc && git commit -m "chore(secrets): activate SOPS"
   ```
   `.env` stays gitignored; `.env.enc` is committed (encrypted). `make sops-status`
   shows state.

### Day-to-day after activation
- Change a secret: `make sops-edit` (or edit `.env`, then `make sops-encrypt`); commit `.env.enc`.
- Deploy: if `.env` is missing, `make sops-decrypt` first, then your usual `make deploy`.

### Recovery (host lost)
1. Restore `~/.config/sops/age/keys.txt` from your password manager; `export SOPS_AGE_KEY_FILE=...`.
2. `git clone` the repo, then `make sops-decrypt` → regenerates `.env`.
3. `kopia repository connect filesystem --path=...` with the recovered `KOPIA_REPO_PASSWORD`; restore.

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
