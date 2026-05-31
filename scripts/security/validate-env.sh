#!/bin/bash
# NOTE: no `-e` — this is a collect-all-then-report validator. Under `set -e`,
# the first warning (`((warnings++))` returns 1 on 0->1) or a missing var
# (`value=$(grep ...)` returns 1) would abort before the summary.
set -uo pipefail
# Environment Variable Validation Script
# Validates that all required environment variables are set in .env file
#
# Usage: ./scripts/security/validate-env.sh
#        ./scripts/security/validate-env.sh --strict  # Exit with error if optional vars missing

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# Paths (overridable for tests).
ENV_FILE="${HOMELAB_ENV_FILE:-$PROJECT_ROOT/.env}"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"
COMPOSE_DIR="${HOMELAB_COMPOSE_DIR:-$PROJECT_ROOT/compose}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Required environment variables (must be set and non-empty)
REQUIRED_VARS=(
    "TAILSCALE_IP"
    "DOMAIN"
    "PUID"
    "PGID"
    "TIMEZONE"
)

# Important but optional variables (should be set for full functionality)
OPTIONAL_VARS=(
    "HOMEASSISTANT_KEY"
    "GRAFANA_PASSWORD"
    "PIHOLE_WEB_PASSWORD"
    "VAULTWARDEN_ADMIN_TOKEN"
    "N8N_USER"
    "N8N_PASSWORD"
    "NEXTCLOUD_DB_ROOT_PASSWORD"
    "NEXTCLOUD_DB_PASSWORD"
    "AUTHENTIK_SECRET_KEY"
    "AUTHENTIK_DB_PASSWORD"
    "PAPERLESS_SECRET_KEY"
    "PAPERLESS_DB_PASSWORD"
    "PAPERLESS_ADMIN_PASSWORD"
)

# Compose-referenced vars that may legitimately be blank (optional integrations:
# OAuth providers, outbound notifications). Everything else referenced in
# compose/*.yml WITHOUT a ":-default" is treated as required. Move a var here to
# allow it to be empty.
COMPOSE_OPTIONAL_VARS=(
    "ALERTMANAGER_DISCORD_WEBHOOK"
    "AUTHENTIK_GRAFANA_CLIENT_ID"
    "AUTHENTIK_GRAFANA_CLIENT_SECRET"
    "GITHUB_CLIENT_ID"
    "GITHUB_CLIENT_SECRET"
    "GOOGLE_CLIENT_ID"
    "GOOGLE_CLIENT_SECRET"
    "WUD_DISCORD_WEBHOOK_URL"
    "WUD_SMTP_HOST"
    "WUD_SMTP_PASS"
    "WUD_SMTP_PORT"
    "WUD_SMTP_USER"
)

# Variables that should NOT contain placeholder values
PLACEHOLDER_PATTERNS=(
    "YOUR_"
    "your_"
    "CHANGE_ME"
    "changeme"
    "your-"
    "example"
)

errors=0
warnings=0
strict_mode=false

# Parse arguments
if [[ "${1:-}" == "--strict" ]]; then
    strict_mode=true
fi

echo "🔐 Homelab Environment Validation"
echo "=================================="
echo ""

# Check if .env file exists
if [[ ! -f "$ENV_FILE" ]]; then
    echo -e "${RED}❌ Error: .env file not found at $ENV_FILE${NC}"
    echo "   Please copy .env.example to .env and configure it:"
    echo "   cp $ENV_EXAMPLE $ENV_FILE"
    exit 1
fi

# Function to get value from .env file safely
get_env_value() {
    local var_name="$1"
    # Use grep to find the variable and cut to extract the value
    # Handle both VAR=value and VAR="value" formats
    local value
    value=$(grep -E "^${var_name}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2- | sed 's/^["'"'"']//;s/["'"'"']$//')
    echo "$value"
}

# Function to check if value contains placeholder
is_placeholder() {
    local value="$1"
    for pattern in "${PLACEHOLDER_PATTERNS[@]}"; do
        if [[ "$value" == *"$pattern"* ]]; then
            return 0  # true
        fi
    done
    return 1  # false
}

echo "📋 Checking required variables..."
echo ""

# Check required variables
for var in "${REQUIRED_VARS[@]}"; do
    value=$(get_env_value "$var")

    if [[ -z "$value" ]]; then
        echo -e "${RED}❌ REQUIRED: $var is not set${NC}"
        ((errors++))
        continue
    fi

    if is_placeholder "$value"; then
        echo -e "${RED}❌ REQUIRED: $var contains a placeholder value${NC}"
        ((errors++))
    else
        echo -e "${GREEN}✅ $var is set${NC}"
    fi
done

echo ""
echo "📋 Checking optional variables..."
echo ""

# Check optional variables
for var in "${OPTIONAL_VARS[@]}"; do
    value=$(get_env_value "$var")

    if [[ -z "$value" ]]; then
        echo -e "${YELLOW}⚠️  OPTIONAL: $var is not set${NC}"
        ((warnings++))
        continue
    fi

    if is_placeholder "$value"; then
        echo -e "${YELLOW}⚠️  OPTIONAL: $var contains a placeholder value${NC}"
        ((warnings++))
    else
        echo -e "${GREEN}✅ $var is set${NC}"
    fi
done

echo ""
echo "📋 Checking compose-referenced variables (auto-derived from compose/)..."
echo ""

# Membership test: is $1 present among the remaining args?
in_list() {
    local needle="$1"; shift
    local item
    for item in "$@"; do
        [[ "$item" == "$needle" ]] && return 0
    done
    return 1
}

if [[ -d "$COMPOSE_DIR" ]]; then
    # Every ${VAR} referenced WITHOUT a ":-default" in compose/*.yml must be set
    # in .env — compose interpolates a missing one to empty, which is silent
    # breakage (exactly how the kopia backup ran credential-less for days). This
    # check is self-maintaining: add a service, its required vars are validated
    # automatically — no hand-edited list to drift out of sync.
    # Strip comments first — a ${VAR} inside a YAML comment is not a real
    # reference (e.g. the BIND_IP note in backup.yml). Match "#" at line start
    # or after whitespace so values containing "#" are not truncated.
    compose_vars=$(grep -rhE '\$\{[A-Za-z_][A-Za-z0-9_]*\}' "$COMPOSE_DIR" 2>/dev/null \
        | sed -E 's/(^|[[:space:]])#.*$//' \
        | grep -oE '\$\{[A-Za-z_][A-Za-z0-9_]*\}' \
        | sed -E 's/\$\{([A-Za-z_][A-Za-z0-9_]*)\}/\1/' | sort -u)
    for var in $compose_vars; do
        # Already covered by the curated loops above — skip to avoid double-report.
        in_list "$var" "${REQUIRED_VARS[@]}" && continue
        in_list "$var" "${OPTIONAL_VARS[@]}" && continue
        value=$(get_env_value "$var")
        if in_list "$var" "${COMPOSE_OPTIONAL_VARS[@]}"; then
            if [[ -z "$value" ]]; then
                echo -e "${YELLOW}⚠️  OPTIONAL (compose): $var unset${NC}"
                ((warnings++))
            else
                echo -e "${GREEN}✅ $var is set${NC}"
            fi
        elif [[ -z "$value" ]]; then
            echo -e "${RED}❌ COMPOSE-REQUIRED: $var is referenced in compose/ (no default) but missing from .env${NC}"
            ((errors++))
        elif is_placeholder "$value"; then
            echo -e "${RED}❌ COMPOSE-REQUIRED: $var contains a placeholder value${NC}"
            ((errors++))
        else
            echo -e "${GREEN}✅ $var is set${NC}"
        fi
    done
else
    echo -e "${YELLOW}⚠️  compose dir not found at $COMPOSE_DIR — skipping completeness check${NC}"
    ((warnings++))
fi

echo ""
echo "=================================="
echo ""

# Summary
if [[ $errors -gt 0 ]]; then
    echo -e "${RED}❌ Validation FAILED: $errors required variable(s) missing or invalid${NC}"
    echo -e "${YELLOW}⚠️  $warnings optional variable(s) not configured${NC}"
    exit 1
elif [[ $warnings -gt 0 ]]; then
    echo -e "${GREEN}✅ All required variables are set${NC}"
    echo -e "${YELLOW}⚠️  $warnings optional variable(s) not configured${NC}"
    if $strict_mode; then
        echo ""
        echo -e "${RED}❌ Strict mode: Failing due to missing optional variables${NC}"
        exit 1
    fi
    exit 0
else
    echo -e "${GREEN}✅ All environment variables are properly configured!${NC}"
    exit 0
fi
