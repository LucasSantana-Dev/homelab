#!/bin/bash
# Idempotent Authentik application/provider registration bootstrap for homelab phase-1 SSO.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
ENV_FILE="${PROJECT_ROOT}/.env"
LOG_DIR="${PROJECT_ROOT}/logs/authentik-registration"

MODE="apply"
ROTATE_SECRETS="false"

usage() {
    cat <<'USAGE'
Usage: authentik-register-apps.sh [--dry-run] [--status] [--rotate-secrets]

Options:
  --dry-run         Show planned Authentik changes without mutating state.
  --status          Show current Authentik registration status.
  --rotate-secrets  Rotate Grafana/Portainer OAuth client credentials (apply mode only).
  --help            Show this help message.
USAGE
}

log() {
    printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Missing required command: $cmd" >&2
        exit 1
    fi
}

env_value() {
    local key="$1"
    if [ ! -f "${ENV_FILE}" ]; then
        return
    fi
    awk -F= -v k="${key}" '
        $0 ~ /^[[:space:]]*#/ { next }
        $1 == k { value = substr($0, index($0, "=") + 1) }
        END { if (value != "") print value }
    ' "${ENV_FILE}" | tr -d '\r' | sed -E 's/^[[:space:]]+|[[:space:]]+$//g; s/^"(.*)"$/\1/; s/^'\''(.*)'\''$/\1/'
}

upsert_env_key() {
    local key="$1"
    local value="$2"
    local file="$3"
    local tmp_file
    local file_mode

    tmp_file="$(mktemp)"
    file_mode="$(stat -c '%a' "$file" 2>/dev/null || echo '600')"

    awk -F= -v k="${key}" -v v="${value}" '
        BEGIN { done = 0 }
        {
            if ($0 ~ /^[[:space:]]*#/) {
                print $0
                next
            }
            if ($1 == k) {
                if (done == 0) {
                    print k "=" v
                    done = 1
                }
                next
            }
            print $0
        }
        END {
            if (done == 0) {
                print k "=" v
            }
        }
    ' "$file" > "$tmp_file"

    mv "$tmp_file" "$file"
    chmod "$file_mode" "$file" 2>/dev/null || true
}

extract_json_payload() {
    local raw_output="$1"
    printf '%s\n' "$raw_output" | sed -n '/^AK_JSON_START$/,/^AK_JSON_END$/p' | sed '1d;$d'
}

run_authentik_python() {
    local action="$1"
    local raw_output
    local payload

    raw_output="$({
        docker exec -i \
            -e AK_ACTION="${action}" \
            -e AK_DOMAIN="${DOMAIN}" \
            -e AK_ALLOWED_EMAIL="${AUTHENTIK_ALLOWED_EMAIL}" \
            -e AK_ALLOWED_GITHUB_USERNAME="${AUTHENTIK_ALLOWED_GITHUB_USERNAME}" \
            -e AK_GRAFANA_CLIENT_ID="${AUTHENTIK_GRAFANA_CLIENT_ID}" \
            -e AK_GRAFANA_CLIENT_SECRET="${AUTHENTIK_GRAFANA_CLIENT_SECRET}" \
            -e AK_PORTAINER_CLIENT_ID="${AUTHENTIK_PORTAINER_CLIENT_ID}" \
            -e AK_PORTAINER_CLIENT_SECRET="${AUTHENTIK_PORTAINER_CLIENT_SECRET}" \
            -e AK_ROTATE_SECRETS="${ROTATE_SECRETS}" \
            authentik-server sh -lc 'export PATH=/ak-root/venv/bin:/lifecycle:$PATH; python /manage.py shell -c "$(cat)"' <<'PY'
import json
import os
import re
import secrets
from django.db import transaction
from authentik.core.models import Application
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.expression.models import ExpressionPolicy
from authentik.policies.models import PolicyBinding
from authentik.providers.oauth2.models import OAuth2Provider
from authentik.providers.proxy.models import ProxyProvider

ACTION = os.getenv("AK_ACTION", "status")
DOMAIN = (os.getenv("AK_DOMAIN", "") or "luk-homeserver.com.br").strip()
ALLOWED_EMAIL = (os.getenv("AK_ALLOWED_EMAIL", "") or "").strip().lower()
ALLOWED_GITHUB = (os.getenv("AK_ALLOWED_GITHUB_USERNAME", "") or "").strip().lower()
GRAFANA_CLIENT_ID_ENV = (os.getenv("AK_GRAFANA_CLIENT_ID", "") or "").strip()
GRAFANA_CLIENT_SECRET_ENV = (os.getenv("AK_GRAFANA_CLIENT_SECRET", "") or "").strip()
PORTAINER_CLIENT_ID_ENV = (os.getenv("AK_PORTAINER_CLIENT_ID", "") or "").strip()
PORTAINER_CLIENT_SECRET_ENV = (os.getenv("AK_PORTAINER_CLIENT_SECRET", "") or "").strip()
ROTATE_SECRETS = (os.getenv("AK_ROTATE_SECRETS", "false") or "false").lower() == "true"

MARKER = "homelab-sso-bootstrap"
KEEP_OAUTH_PROVIDER_NAMES = {"OAuth Provider"}
POLICY_ALLOWLIST_NAME = "homelab-allowlist-policy"
POLICY_ADMIN_BYPASS_NAME = "homelab-admin-bypass-policy"

PHASE1_HOSTS = [
    f"{DOMAIN}",
    f"www.{DOMAIN}",
    f"homeassistant.{DOMAIN}",
    f"grafana.{DOMAIN}",
    f"portainer.{DOMAIN}",
    f"n8n.{DOMAIN}",
    f"cloud.{DOMAIN}",
    f"docs.{DOMAIN}",
    f"vault.{DOMAIN}",
]

NATIVE_OAUTH_TARGETS = [
    {
        "key": "grafana",
        "provider_name": "homelab-oauth:grafana",
        "redirect_url": f"https://grafana.{DOMAIN}/login/generic_oauth",
        "env_client_id": GRAFANA_CLIENT_ID_ENV,
        "env_client_secret": GRAFANA_CLIENT_SECRET_ENV,
        "result_client_id_key": "AUTHENTIK_GRAFANA_CLIENT_ID",
        "result_client_secret_key": "AUTHENTIK_GRAFANA_CLIENT_SECRET",
    },
    {
        "key": "portainer",
        "provider_name": "homelab-oauth:portainer",
        "redirect_url": f"https://portainer.{DOMAIN}",
        "env_client_id": PORTAINER_CLIENT_ID_ENV,
        "env_client_secret": PORTAINER_CLIENT_SECRET_ENV,
        "result_client_id_key": "AUTHENTIK_PORTAINER_CLIENT_ID",
        "result_client_secret_key": "AUTHENTIK_PORTAINER_CLIENT_SECRET",
    },
]


def normalize_host(value: str) -> str:
    v = (value or "").strip().lower()
    v = re.sub(r"^https?://", "", v)
    v = v.rstrip("/")
    return v


def app_slug_for_host(host: str) -> str:
    return "homelab-proxy-" + re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")


def provider_name_for_host(host: str) -> str:
    return f"homelab-proxy:{host}"


def phase1_proxy_spec():
    items = []
    for host in PHASE1_HOSTS:
        url = f"https://{host}"
        items.append(
            {
                "host": host,
                "url": url,
                "app_slug": app_slug_for_host(host),
                "app_name": host,
                "provider_name": provider_name_for_host(host),
            }
        )
    return items


def snapshot_state():
    apps = []
    for app in Application.objects.select_related("provider").all().order_by("slug"):
        provider = app.provider
        apps.append(
            {
                "slug": app.slug,
                "name": app.name,
                "provider_name": getattr(provider, "name", None),
                "provider_id": getattr(provider, "id", None),
                "meta_publisher": app.meta_publisher,
                "managed": getattr(app, "managed", None),
                "policies": list(app.policies.values_list("name", flat=True)),
                "policy_engine_mode": app.policy_engine_mode,
            }
        )

    oauth2 = []
    for provider in OAuth2Provider.objects.all().order_by("name"):
        oauth2.append(
            {
                "id": provider.id,
                "name": provider.name,
                "client_id": provider.client_id,
                "redirect_uris": provider._redirect_uris,
            }
        )

    proxies = []
    for provider in ProxyProvider.objects.all().order_by("name"):
        proxies.append(
            {
                "id": provider.id,
                "name": provider.name,
                "external_host": provider.external_host,
                "internal_host": provider.internal_host,
                "mode": provider.mode,
            }
        )

    outposts = []
    for outpost in Outpost.objects.all().order_by("name"):
        outposts.append(
            {
                "name": outpost.name,
                "type": outpost.type,
                "managed": outpost.managed,
                "providers": list(outpost.providers.values_list("name", flat=True)),
            }
        )

    policies = list(
        ExpressionPolicy.objects.filter(name__in=[POLICY_ALLOWLIST_NAME, POLICY_ADMIN_BYPASS_NAME])
        .order_by("name")
        .values("name", "expression")
    )

    return {
        "applications": apps,
        "oauth2_providers": oauth2,
        "proxy_providers": proxies,
        "outposts": outposts,
        "expression_policies": policies,
    }


def current_status(snapshot):
    desired_hosts = sorted(set(PHASE1_HOSTS))
    desired_urls = {f"https://{h}" for h in desired_hosts}

    existing_proxy_by_host = {
        normalize_host(item.get("external_host", ""))
        for item in snapshot["proxy_providers"]
        if item.get("external_host")
    }

    missing_proxy_hosts = [h for h in desired_hosts if h not in existing_proxy_by_host]

    embedded = next(
        (
            o
            for o in snapshot["outposts"]
            if o.get("name") == "authentik Embedded Outpost" and o.get("type") == "proxy"
        ),
        None,
    )

    outpost_provider_names = set((embedded or {}).get("providers", []))
    expected_provider_names = {provider_name_for_host(host) for host in desired_hosts}

    return {
        "application_count": len(snapshot["applications"]),
        "oauth2_provider_count": len(snapshot["oauth2_providers"]),
        "proxy_provider_count": len(snapshot["proxy_providers"]),
        "embedded_outpost_provider_count": len(outpost_provider_names),
        "phase1_missing_proxy_hosts": missing_proxy_hosts,
        "embedded_outpost_has_phase1_proxy_set": expected_provider_names.issubset(outpost_provider_names),
        "allowlist_policy_exists": any(p["name"] == POLICY_ALLOWLIST_NAME for p in snapshot["expression_policies"]),
        "admin_bypass_policy_exists": any(p["name"] == POLICY_ADMIN_BYPASS_NAME for p in snapshot["expression_policies"]),
        "phase1_expected_urls": sorted(desired_urls),
    }


def plan_cleanup(snapshot):
    apps_to_delete = [
        item
        for item in snapshot["applications"]
        if (item.get("managed") in (None, ""))
    ]

    oauth_to_delete = [
        item
        for item in snapshot["oauth2_providers"]
        if item.get("name") not in KEEP_OAUTH_PROVIDER_NAMES
    ]

    proxies_to_delete = list(snapshot["proxy_providers"])

    embedded = next(
        (
            o
            for o in snapshot["outposts"]
            if o.get("name") == "authentik Embedded Outpost" and o.get("type") == "proxy"
        ),
        None,
    )

    return {
        "applications": sorted(item["slug"] for item in apps_to_delete),
        "oauth2_providers": sorted(item["name"] for item in oauth_to_delete),
        "proxy_providers": sorted(item["name"] for item in proxies_to_delete),
        "embedded_outpost_provider_bindings": sorted((embedded or {}).get("providers", [])),
    }


def ensure_expression_policy(name: str, expression: str):
    policy, created = ExpressionPolicy.objects.get_or_create(
        name=name,
        defaults={
            "expression": expression,
            "execution_logging": False,
        },
    )
    updated = False
    if policy.expression != expression:
        policy.expression = expression
        updated = True
    if policy.execution_logging:
        policy.execution_logging = False
        updated = True
    if updated:
        policy.save()
    return policy, created, updated


def credentials_for_provider(existing_provider, env_client_id: str, env_client_secret: str):
    env_pair = bool(env_client_id and env_client_secret)

    if ROTATE_SECRETS:
        return (
            secrets.token_urlsafe(24),
            secrets.token_urlsafe(48),
            "rotated",
        )

    if env_pair:
        return env_client_id, env_client_secret, "env"

    if existing_provider is not None and existing_provider.client_id and existing_provider.client_secret:
        return existing_provider.client_id, existing_provider.client_secret, "existing"

    return (
        env_client_id or secrets.token_urlsafe(24),
        env_client_secret or secrets.token_urlsafe(48),
        "generated",
    )


def apply_changes():
    actions = {
        "deleted": {
            "applications": [],
            "oauth2_providers": [],
            "proxy_providers": [],
            "embedded_outpost_bindings": 0,
        },
        "created": {
            "applications": [],
            "oauth2_providers": [],
            "proxy_providers": [],
            "policies": [],
        },
        "updated": {
            "applications": [],
            "oauth2_providers": [],
            "proxy_providers": [],
            "policies": [],
        },
    }

    credentials = {}

    allowlist_expression = (
        f"allowed_email = {json.dumps(ALLOWED_EMAIL)}\n"
        f"allowed_github = {json.dumps(ALLOWED_GITHUB)}\n"
        "user = request.user\n"
        "if not user:\n"
        "    return False\n"
        "email = (user.email or '').strip().lower()\n"
        "if email != allowed_email:\n"
        "    return False\n"
        "attrs = user.attributes if isinstance(getattr(user, 'attributes', None), dict) else {}\n"
        "candidate_usernames = {\n"
        "    (user.username or '').strip().lower(),\n"
        "    str(attrs.get('github_username', '')).strip().lower(),\n"
        "    str(attrs.get('preferred_username', '')).strip().lower(),\n"
        "    str(attrs.get('username', '')).strip().lower(),\n"
        "}\n"
        "return allowed_github in candidate_usernames\n"
    )

    admin_bypass_expression = (
        "user = request.user\n"
        "return user is not None and (user.username or '').strip().lower() == 'admin'\n"
    )

    with transaction.atomic():
        allow_policy, created, updated = ensure_expression_policy(
            POLICY_ALLOWLIST_NAME,
            allowlist_expression,
        )
        if created:
            actions["created"]["policies"].append(POLICY_ALLOWLIST_NAME)
        elif updated:
            actions["updated"]["policies"].append(POLICY_ALLOWLIST_NAME)

        admin_policy, created, updated = ensure_expression_policy(
            POLICY_ADMIN_BYPASS_NAME,
            admin_bypass_expression,
        )
        if created:
            actions["created"]["policies"].append(POLICY_ADMIN_BYPASS_NAME)
        elif updated:
            actions["updated"]["policies"].append(POLICY_ADMIN_BYPASS_NAME)

        embedded_outpost = Outpost.objects.filter(name="authentik Embedded Outpost", type="proxy").first()
        if embedded_outpost is None:
            raise RuntimeError("authentik Embedded Outpost (type=proxy) was not found")

        authorization_flow = (
            Flow.objects.filter(slug="default-provider-authorization-implicit-consent").first()
            or Flow.objects.filter(designation="authorization").order_by("slug").first()
        )
        if authorization_flow is None:
            raise RuntimeError("No authorization flow found for proxy providers")

        invalidation_flow = (
            Flow.objects.filter(slug="default-provider-invalidation-flow").first()
            or Flow.objects.filter(slug="default-invalidation-flow").first()
            or Flow.objects.filter(designation="invalidation").order_by("slug").first()
        )
        if invalidation_flow is None:
            raise RuntimeError("No invalidation flow found for proxy providers")

        existing_bindings = embedded_outpost.providers.count()
        actions["deleted"]["embedded_outpost_bindings"] = existing_bindings
        if existing_bindings:
            embedded_outpost.providers.clear()

        existing_proxy_names = list(ProxyProvider.objects.values_list("name", flat=True))
        if existing_proxy_names:
            actions["deleted"]["proxy_providers"] = sorted(existing_proxy_names)
            ProxyProvider.objects.filter(name__in=existing_proxy_names).delete()

        oauth_to_delete_qs = OAuth2Provider.objects.exclude(name__in=KEEP_OAUTH_PROVIDER_NAMES)
        oauth_to_delete_names = list(oauth_to_delete_qs.values_list("name", flat=True))
        if oauth_to_delete_names:
            actions["deleted"]["oauth2_providers"] = sorted(oauth_to_delete_names)
            oauth_to_delete_qs.delete()

        app_to_delete_qs = Application.objects.all()
        app_to_delete_slugs = list(app_to_delete_qs.values_list("slug", flat=True))
        if app_to_delete_slugs:
            actions["deleted"]["applications"] = sorted(app_to_delete_slugs)
            app_to_delete_qs.delete()

        proxy_providers_for_outpost = []

        for spec in phase1_proxy_spec():
            provider, created = ProxyProvider.objects.get_or_create(name=spec["provider_name"])
            before_client_type = provider.client_type
            before_signing_key_id = provider.signing_key_id
            before_include_claims = provider.include_claims_in_id_token
            before_redirects = list(provider._redirect_uris or [])
            before_scope_mappings = sorted(
                provider.property_mappings.values_list("managed", flat=True)
            )
            changed = False

            if provider.external_host != spec["url"]:
                provider.external_host = spec["url"]
                changed = True
            if provider.internal_host != spec["url"]:
                provider.internal_host = spec["url"]
                changed = True
            if provider.mode != "forward_single":
                provider.mode = "forward_single"
                changed = True
            if provider.authorization_flow_id != authorization_flow.pk:
                provider.authorization_flow = authorization_flow
                changed = True
            if provider.invalidation_flow_id != invalidation_flow.pk:
                provider.invalidation_flow = invalidation_flow
                changed = True
            if provider.internal_host_ssl_validation is not True:
                provider.internal_host_ssl_validation = True
                changed = True

            # Ensure proxy providers get the same defaults as API-created providers
            # (OIDC redirect callbacks + required scope mappings).
            provider.set_oauth_defaults()
            if provider.client_type != before_client_type:
                changed = True
            if provider.signing_key_id != before_signing_key_id:
                changed = True
            if provider.include_claims_in_id_token != before_include_claims:
                changed = True
            if list(provider._redirect_uris or []) != before_redirects:
                changed = True
            after_scope_mappings = sorted(
                provider.property_mappings.values_list("managed", flat=True)
            )
            if after_scope_mappings != before_scope_mappings:
                changed = True

            if created or changed:
                provider.save()

            if created:
                actions["created"]["proxy_providers"].append(provider.name)
            elif changed:
                actions["updated"]["proxy_providers"].append(provider.name)

            app, app_created = Application.objects.get_or_create(
                slug=spec["app_slug"],
                defaults={
                    "name": spec["app_name"],
                    "provider": provider,
                    "meta_launch_url": spec["url"],
                    "meta_description": f"Protected via Authentik for {spec['host']}",
                    "meta_publisher": MARKER,
                    "open_in_new_tab": False,
                    "policy_engine_mode": "any",
                },
            )

            app_changed = False
            if app.name != spec["app_name"]:
                app.name = spec["app_name"]
                app_changed = True
            if app.provider_id != provider.id:
                app.provider = provider
                app_changed = True
            if app.meta_launch_url != spec["url"]:
                app.meta_launch_url = spec["url"]
                app_changed = True
            desired_description = f"Protected via Authentik for {spec['host']}"
            if app.meta_description != desired_description:
                app.meta_description = desired_description
                app_changed = True
            if app.meta_publisher != MARKER:
                app.meta_publisher = MARKER
                app_changed = True
            if app.policy_engine_mode != "any":
                app.policy_engine_mode = "any"
                app_changed = True

            if app_created or app_changed:
                app.save()

            # Explicit bindings are required because PolicyBinding.order is non-null.
            PolicyBinding.objects.filter(target=app).delete()
            PolicyBinding.objects.create(
                policy=allow_policy,
                target=app,
                order=0,
                enabled=True,
            )
            PolicyBinding.objects.create(
                policy=admin_policy,
                target=app,
                order=10,
                enabled=True,
            )

            if app_created:
                actions["created"]["applications"].append(app.slug)
            elif app_changed:
                actions["updated"]["applications"].append(app.slug)

            proxy_providers_for_outpost.append(provider)

        embedded_outpost.providers.set(proxy_providers_for_outpost)

        oauth_template = OAuth2Provider.objects.filter(name__in=KEEP_OAUTH_PROVIDER_NAMES).first()

        for target in NATIVE_OAUTH_TARGETS:
            existing_provider = OAuth2Provider.objects.filter(name=target["provider_name"]).first()
            client_id, client_secret, _ = credentials_for_provider(
                existing_provider,
                target["env_client_id"],
                target["env_client_secret"],
            )

            provider, created = OAuth2Provider.objects.get_or_create(name=target["provider_name"])
            changed = False

            if oauth_template is not None:
                if provider.client_type != oauth_template.client_type:
                    provider.client_type = oauth_template.client_type
                    changed = True
                if provider.include_claims_in_id_token != oauth_template.include_claims_in_id_token:
                    provider.include_claims_in_id_token = oauth_template.include_claims_in_id_token
                    changed = True
                if provider.access_code_validity != oauth_template.access_code_validity:
                    provider.access_code_validity = oauth_template.access_code_validity
                    changed = True
                if provider.access_token_validity != oauth_template.access_token_validity:
                    provider.access_token_validity = oauth_template.access_token_validity
                    changed = True
                if provider.refresh_token_validity != oauth_template.refresh_token_validity:
                    provider.refresh_token_validity = oauth_template.refresh_token_validity
                    changed = True
                if provider.sub_mode != oauth_template.sub_mode:
                    provider.sub_mode = oauth_template.sub_mode
                    changed = True
                if provider.issuer_mode != oauth_template.issuer_mode:
                    provider.issuer_mode = oauth_template.issuer_mode
                    changed = True
                if provider.authentication_flow_id != oauth_template.authentication_flow_id:
                    provider.authentication_flow_id = oauth_template.authentication_flow_id
                    changed = True
                if provider.authorization_flow_id != oauth_template.authorization_flow_id:
                    provider.authorization_flow_id = oauth_template.authorization_flow_id
                    changed = True
                if provider.invalidation_flow_id != oauth_template.invalidation_flow_id:
                    provider.invalidation_flow_id = oauth_template.invalidation_flow_id
                    changed = True
            else:
                if provider.client_type != "confidential":
                    provider.client_type = "confidential"
                    changed = True

            desired_redirects = [{"url": target["redirect_url"], "matching_mode": "strict"}]
            if provider._redirect_uris != desired_redirects:
                provider._redirect_uris = desired_redirects
                changed = True
            if provider.client_id != client_id:
                provider.client_id = client_id
                changed = True
            if provider.client_secret != client_secret:
                provider.client_secret = client_secret
                changed = True

            if created or changed:
                provider.save()

            if created:
                actions["created"]["oauth2_providers"].append(provider.name)
            elif changed:
                actions["updated"]["oauth2_providers"].append(provider.name)

            credentials[target["result_client_id_key"]] = provider.client_id
            credentials[target["result_client_secret_key"]] = provider.client_secret

    return actions, credentials


snapshot = snapshot_state()
plan = plan_cleanup(snapshot)
status = current_status(snapshot)

if ACTION in {"snapshot", "status"}:
    payload = {
        "mode": ACTION,
        "snapshot": snapshot,
        "plan": plan,
        "status": status,
    }
elif ACTION == "dry-run":
    payload = {
        "mode": ACTION,
        "snapshot": snapshot,
        "plan": plan,
        "status": status,
        "would_create": {
            "proxy_providers": sorted(provider_name_for_host(h) for h in PHASE1_HOSTS),
            "applications": sorted(app_slug_for_host(h) for h in PHASE1_HOSTS),
            "oauth2_providers": sorted(t["provider_name"] for t in NATIVE_OAUTH_TARGETS),
            "policies": [POLICY_ALLOWLIST_NAME, POLICY_ADMIN_BYPASS_NAME],
        },
    }
elif ACTION == "apply":
    actions, credentials = apply_changes()
    final_snapshot = snapshot_state()
    payload = {
        "mode": ACTION,
        "snapshot_before": snapshot,
        "snapshot_after": final_snapshot,
        "plan": plan,
        "actions": actions,
        "credentials": credentials,
        "status_after": current_status(final_snapshot),
    }
else:
    raise RuntimeError(f"Unsupported action: {ACTION}")

print("AK_JSON_START")
print(json.dumps(payload, indent=2, sort_keys=True))
print("AK_JSON_END")
PY
    } 2>&1)"

    payload="$(extract_json_payload "$raw_output")"
    if [ -z "$payload" ]; then
        echo "Failed to parse Authentik response. Raw output:" >&2
        printf '%s\n' "$raw_output" >&2
        return 1
    fi

    printf '%s\n' "$payload"
}

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            MODE="dry-run"
            ;;
        --status)
            MODE="status"
            ;;
        --rotate-secrets)
            ROTATE_SECRETS="true"
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            usage
            exit 1
            ;;
    esac
done

if [ "$MODE" = "dry-run" ] && [ "$ROTATE_SECRETS" = "true" ]; then
    echo "--rotate-secrets cannot be used with --dry-run" >&2
    exit 1
fi

require_command docker
require_command jq

mkdir -p "$LOG_DIR"

if [ ! -f "$ENV_FILE" ]; then
    echo "Missing ${ENV_FILE}" >&2
    exit 1
fi

if ! docker inspect authentik-server >/dev/null 2>&1; then
    echo "authentik-server container is not available" >&2
    exit 1
fi
if [ "$(docker inspect -f '{{.State.Status}}' authentik-server 2>/dev/null || true)" != "running" ]; then
    echo "authentik-server container is not running" >&2
    exit 1
fi

DOMAIN="$(env_value DOMAIN)"
if [ -z "$DOMAIN" ]; then
    DOMAIN="luk-homeserver.com.br"
fi

AUTHENTIK_ALLOWED_EMAIL="$(env_value AUTHENTIK_ALLOWED_EMAIL)"
AUTHENTIK_ALLOWED_GITHUB_USERNAME="$(env_value AUTHENTIK_ALLOWED_GITHUB_USERNAME)"
AUTHENTIK_GRAFANA_CLIENT_ID="$(env_value AUTHENTIK_GRAFANA_CLIENT_ID)"
AUTHENTIK_GRAFANA_CLIENT_SECRET="$(env_value AUTHENTIK_GRAFANA_CLIENT_SECRET)"
AUTHENTIK_PORTAINER_CLIENT_ID="$(env_value AUTHENTIK_PORTAINER_CLIENT_ID)"
AUTHENTIK_PORTAINER_CLIENT_SECRET="$(env_value AUTHENTIK_PORTAINER_CLIENT_SECRET)"

if [ "$MODE" != "status" ]; then
    if [ -z "$AUTHENTIK_ALLOWED_EMAIL" ]; then
        echo "AUTHENTIK_ALLOWED_EMAIL must be set in .env" >&2
        exit 1
    fi
    if [ -z "$AUTHENTIK_ALLOWED_GITHUB_USERNAME" ]; then
        echo "AUTHENTIK_ALLOWED_GITHUB_USERNAME must be set in .env" >&2
        exit 1
    fi
fi

timestamp="$(date '+%Y%m%d-%H%M%S')"
snapshot_file="${LOG_DIR}/snapshot-${timestamp}.json"

log "Capturing pre-change Authentik snapshot"
snapshot_payload="$(run_authentik_python snapshot)"
printf '%s\n' "$snapshot_payload" > "$snapshot_file"
log "Snapshot written to ${snapshot_file}"

if [ "$MODE" = "status" ]; then
    log "Current registration status"
    printf '%s\n' "$snapshot_payload" | jq -r '
        .status as $s |
        "Applications: \($s.application_count)",
        "OAuth2 Providers: \($s.oauth2_provider_count)",
        "Proxy Providers: \($s.proxy_provider_count)",
        "Embedded Outpost Providers: \($s.embedded_outpost_provider_count)",
        "Missing Phase-1 Proxy Hosts: \(($s.phase1_missing_proxy_hosts | join(", ")) // "none")",
        "Embedded Outpost Contains Phase-1 Set: \($s.embedded_outpost_has_phase1_proxy_set)",
        "Allowlist Policy Present: \($s.allowlist_policy_exists)",
        "Admin Bypass Policy Present: \($s.admin_bypass_policy_exists)"
    '
    exit 0
fi

if [ "$MODE" = "dry-run" ]; then
    log "Running Authentik registration dry-run"
    dry_payload="$(run_authentik_python dry-run)"
    printf '%s\n' "$dry_payload" | jq -r '
        "Planned deletions:",
        "  Applications: \(.plan.applications | length)",
        "  OAuth2 Providers: \(.plan.oauth2_providers | length)",
        "  Proxy Providers: \(.plan.proxy_providers | length)",
        "  Embedded Outpost Bindings: \(.plan.embedded_outpost_provider_bindings | length)",
        "Planned creations:",
        "  Applications: \(.would_create.applications | length)",
        "  OAuth2 Providers: \(.would_create.oauth2_providers | length)",
        "  Proxy Providers: \(.would_create.proxy_providers | length)",
        "  Policies: \(.would_create.policies | length)"
    '
    exit 0
fi

log "Applying Authentik registration rebuild"
apply_payload="$(run_authentik_python apply)"

new_grafana_client_id="$(printf '%s\n' "$apply_payload" | jq -r '.credentials.AUTHENTIK_GRAFANA_CLIENT_ID // empty')"
new_grafana_client_secret="$(printf '%s\n' "$apply_payload" | jq -r '.credentials.AUTHENTIK_GRAFANA_CLIENT_SECRET // empty')"
new_portainer_client_id="$(printf '%s\n' "$apply_payload" | jq -r '.credentials.AUTHENTIK_PORTAINER_CLIENT_ID // empty')"
new_portainer_client_secret="$(printf '%s\n' "$apply_payload" | jq -r '.credentials.AUTHENTIK_PORTAINER_CLIENT_SECRET // empty')"

if [ -z "$new_grafana_client_id" ] || [ -z "$new_grafana_client_secret" ] || [ -z "$new_portainer_client_id" ] || [ -z "$new_portainer_client_secret" ]; then
    echo "Missing OAuth credentials in Authentik apply output" >&2
    exit 1
fi

upsert_env_key "AUTHENTIK_GRAFANA_CLIENT_ID" "$new_grafana_client_id" "$ENV_FILE"
upsert_env_key "AUTHENTIK_GRAFANA_CLIENT_SECRET" "$new_grafana_client_secret" "$ENV_FILE"
upsert_env_key "AUTHENTIK_PORTAINER_CLIENT_ID" "$new_portainer_client_id" "$ENV_FILE"
upsert_env_key "AUTHENTIK_PORTAINER_CLIENT_SECRET" "$new_portainer_client_secret" "$ENV_FILE"

log "Updated OAuth client credentials in ${ENV_FILE}"

printf '%s\n' "$apply_payload" | jq -r '
    "Applied changes:",
    "  Deleted applications: \(.actions.deleted.applications | length)",
    "  Deleted OAuth2 providers: \(.actions.deleted.oauth2_providers | length)",
    "  Deleted proxy providers: \(.actions.deleted.proxy_providers | length)",
    "  Created applications: \(.actions.created.applications | length)",
    "  Created OAuth2 providers: \(.actions.created.oauth2_providers | length)",
    "  Created proxy providers: \(.actions.created.proxy_providers | length)",
    "  Updated applications: \(.actions.updated.applications | length)",
    "  Updated OAuth2 providers: \(.actions.updated.oauth2_providers | length)",
    "  Updated proxy providers: \(.actions.updated.proxy_providers | length)",
    "Post-apply status:",
    "  Applications: \(.status_after.application_count)",
    "  OAuth2 providers: \(.status_after.oauth2_provider_count)",
    "  Proxy providers: \(.status_after.proxy_provider_count)",
    "  Missing phase-1 proxy hosts: \((.status_after.phase1_missing_proxy_hosts | join(", ")) // "none")",
    "  Embedded outpost has phase-1 set: \(.status_after.embedded_outpost_has_phase1_proxy_set)"
'

exit 0
