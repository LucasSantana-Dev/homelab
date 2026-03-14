# SOPS-managed Secrets

This folder stores encrypted manifests only (`*.enc.yaml`).

## Setup

```bash
./scripts/migration/sops-age-init.sh
```

Update `.sops.yaml` with your generated public key, then encrypt manifests.

## Encrypt a manifest

```bash
./scripts/migration/encrypt-k8s-secret.sh \
  k8s/secrets/homepage-env.secret.yaml.template \
  k8s/secrets/homepage-env.secret.enc.yaml
```

## Decrypt for local inspection

```bash
sops --decrypt k8s/secrets/homepage-env.secret.enc.yaml
```
