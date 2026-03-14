# Homelab Management Makefile
# Provides convenient targets for homelab operations

.PHONY: help install deploy status logs health backup restore security-scan monitor clean test \
        update update-safe update-timer-install update-timer-status update-timer-enable update-timer-disable \
        image-lock-status image-lock-refresh image-lock-refresh-dry-run \
        watchdog-install watchdog-status watchdog-run-now watchdog-disable automation-reconcile \
        host-stabilize-prep host-swap-recover server-mode-plan server-mode-apply post-reboot-validate \
        concurrency-guard pressure-watch pressure-capture-checkpoint pressure-checkpoint-gate pressure-gates-status \
        schedule-pressure-gate-checkpoints \
        baseline-bundle \
        post-t24-terraform-apply schedule-post-t24-terraform-apply \
        ssl-renew ssl-status sso-register-apps sso-register-dry-run sso-register-status \
        serena-mcp-setup migration-toolchain migration-preflight k3s-bootstrap migration-budget \
        wave-a-deploy wave-a-gate wave-b-deploy wave-rollback \
        secret-gate secret-gate-history public-safety-gate public-release-checkpoint rewrite-history \
        forge-space-up forge-space-down forge-space-logs forge-space-status forge-space-mcp-setup

# Default target
help: ## Show this help message
	@echo "Homelab Management Commands"
	@echo "=========================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation and setup
install: ## Install homelab manager and dependencies
	@echo "Installing homelab manager..."
	python3 -m pip install --user -e .
	@echo "✅ Installation complete"

# Container management
deploy: ## Deploy all homelab services
	@echo "🚀 Deploying homelab services..."
	docker compose up -d
	@echo "✅ Deployment complete"

forge-space-up: ## Deploy Forge Space MCP Gateway profile
	@echo "🧠 Starting Forge Space MCP Gateway..."
	@docker compose --profile forge-space up -d forge-mcp-gateway
	@echo "✅ Forge MCP Gateway started"

forge-space-down: ## Stop Forge Space MCP Gateway profile
	@echo "🛑 Stopping Forge Space MCP Gateway..."
	@docker compose --profile forge-space stop forge-mcp-gateway
	@echo "✅ Forge MCP Gateway stopped"

forge-space-logs: ## Tail Forge Space MCP Gateway logs
	@docker compose --profile forge-space logs -f --tail=100 forge-mcp-gateway

forge-space-status: ## Show Forge Space MCP Gateway status
	@docker compose --profile forge-space ps forge-mcp-gateway

forge-space-mcp-setup: ## Register Forge Space MCP client in Codex (requires FORGE_MCP_SERVER_URL and FORGE_MCP_JWT)
	@./scripts/deployment/setup-forge-space-mcp.sh

status: ## Show status of all services
	@echo "📊 Homelab Status"
	@echo "================="
	docker compose ps

logs: ## Show logs for all services
	@echo "📋 Service Logs"
	@echo "==============="
	docker compose logs --tail=50

logs-service: ## Show logs for specific service (usage: make logs-service SERVICE=nginx)
	@if [ -z "$(SERVICE)" ]; then \
		echo "❌ Please specify SERVICE=service_name"; \
		echo "Available services:"; \
		docker compose ps --services; \
		exit 1; \
	fi
	@echo "📋 Logs for $(SERVICE)"
	@echo "======================"
	docker compose logs --tail=100 $(SERVICE)

# Health and monitoring
health: ## Check health of all services
	@echo "🏥 Health Check"
	@echo "==============="
	@if command -v python3 >/dev/null 2>&1 && python3 -c "import homelab_manager" 2>/dev/null; then \
		python3 -m homelab_manager health; \
	else \
		echo "Checking service endpoints..."; \
		TAILSCALE_IP=$$(grep TAILSCALE_IP .env 2>/dev/null | cut -d'=' -f2 || echo ""); \
		if [ -z "$$TAILSCALE_IP" ]; then \
			echo "⚠️  TAILSCALE_IP not set in .env file"; \
		else \
			curl -s -o /dev/null -w "Homepage: %{http_code}\n" http://$$TAILSCALE_IP:3000 || echo "Homepage: ❌"; \
			curl -s -o /dev/null -w "Grafana: %{http_code}\n" http://$$TAILSCALE_IP:3002 || echo "Grafana: ❌"; \
			curl -s -o /dev/null -w "Pi-hole: %{http_code}\n" http://$$TAILSCALE_IP:8054 || echo "Pi-hole: ❌"; \
		fi; \
	fi

monitor: ## Open monitoring dashboards
	@echo "📊 Opening monitoring dashboards..."
	@echo "Available dashboards:"
	@echo "  • Grafana:     https://grafana.homelab.example.com"
	@echo "  • Prometheus:  https://prometheus.homelab.example.com"
	@echo "  • Netdata:     https://netdata.homelab.example.com"
	@echo "  • cAdvisor:    https://cadvisor.homelab.example.com"
	@echo "  • Uptime Kuma: https://uptime.homelab.example.com"
	@if command -v xdg-open >/dev/null 2>&1; then \
		xdg-open https://grafana.homelab.example.com; \
	elif command -v open >/dev/null 2>&1; then \
		open https://grafana.homelab.example.com; \
	else \
		echo "Please open the URLs manually in your browser"; \
	fi

# Backup and restore
backup: ## Create backup of homelab data
	@echo "💾 Creating backup..."
	@if [ -f "./scripts/maintenance/automated-backup.sh" ]; then \
		./scripts/maintenance/automated-backup.sh; \
	elif command -v python3 >/dev/null 2>&1 && python3 -c "import homelab_manager" 2>/dev/null; then \
		python3 -m homelab_manager backup; \
	else \
		echo "Creating manual backup..."; \
		timestamp=$$(date +%Y%m%d_%H%M%S); \
		tar -czf "backups/homelab_backup_$$timestamp.tar.gz" appdata config docker-compose.yml .env; \
		echo "✅ Backup created: homelab_backup_$$timestamp.tar.gz"; \
	fi

restore: ## Restore from backup (usage: make restore BACKUP=backup_file.tar.gz)
	@if [ -z "$(BACKUP)" ]; then \
		echo "❌ Please specify BACKUP=backup_file.tar.gz"; \
		echo "Available backups:"; \
		ls -la backups/ 2>/dev/null || echo "No backups found"; \
		exit 1; \
	fi
	@echo "🔄 Restoring from backup: $(BACKUP)"
	@if [ -f "backups/$(BACKUP)" ]; then \
		docker compose down; \
		tar -xzf "backups/$(BACKUP)"; \
		docker compose up -d; \
		echo "✅ Restore complete"; \
	else \
		echo "❌ Backup file not found: backups/$(BACKUP)"; \
		exit 1; \
	fi

# Security
security-scan: ## Run security scan on containers and images
	@echo "🔒 Running security scan..."
	@if [ -f "./scripts/security/security-scan.sh" ]; then \
		./scripts/security/security-scan.sh; \
	else \
		echo "❌ Security scan script not found"; \
		echo "Please run: make install"; \
		exit 1; \
	fi

secret-gate: ## Run gitleaks secret scan against tracked snapshot
	@./scripts/security/secret-gate.sh

secret-gate-history: ## Run gitleaks scan including full git history
	@./scripts/security/secret-gate.sh --history

public-safety-gate: ## Fail if known private identifiers are present in tracked public files
	@./scripts/security/public-safety-gate.sh

public-release-checkpoint: ## Create branch/tag/mirror backup and credential inventory before history rewrite
	@./scripts/security/pre-release-checkpoint.sh

rewrite-history: ## Rewrite history with configured scrub/remove policies (use PUSH=true to force-push)
	@if [ "$(PUSH)" = "true" ]; then \
		./scripts/security/rewrite-history.sh --push --remote origin; \
	else \
		./scripts/security/rewrite-history.sh; \
	fi

# Development and testing
test: ## Run tests
	@echo "🧪 Running tests..."
	@if [ -f "venv/bin/activate" ]; then \
		source venv/bin/activate && python -m pytest tests/ -v; \
	elif command -v python3 >/dev/null 2>&1; then \
		python3 -m pytest tests/ -v; \
	else \
		echo "❌ Python not found"; \
		exit 1; \
	fi

lint: ## Run linting checks
	@echo "🔍 Running linting checks..."
	@if [ -f "venv/bin/activate" ]; then \
		source venv/bin/activate && \
		black --check homelab_manager/ tests/ && \
		flake8 homelab_manager/ tests/ && \
		mypy homelab_manager/; \
	else \
		echo "❌ Virtual environment not found. Run 'make install' first."; \
		exit 1; \
	fi

format: ## Format code
	@echo "🎨 Formatting code..."
	@if [ -f "venv/bin/activate" ]; then \
		source venv/bin/activate && \
		black homelab_manager/ tests/ && \
		isort homelab_manager/ tests/; \
	else \
		echo "❌ Virtual environment not found. Run 'make install' first."; \
		exit 1; \
	fi

# Maintenance
clean: ## Clean up caches, temp files, and old backups
	@./scripts/maintenance/cleanup-project.sh --all

clean-quick: ## Quick cleanup (caches and temp files only)
	@./scripts/maintenance/cleanup-project.sh

clean-dry: ## Show what would be cleaned (dry run)
	@./scripts/maintenance/cleanup-project.sh --dry-run --all

docker-clean: ## Clean Docker system (prune unused images/containers)
	@echo "🐳 Cleaning Docker system..."
	@docker system prune -f
	@echo "✅ Cleanup complete"

update: ## Update all container images (fast mode)
	@echo "🔄 Updating container images..."
	docker compose pull
	docker compose up -d
	@echo "✅ Update complete"

update-safe: ## Update containers with health checks (safe rolling update)
	@echo "🔄 Running safe container update..."
	@if [ -f "./scripts/maintenance/update-containers.sh" ]; then \
		./scripts/maintenance/update-containers.sh; \
	else \
		echo "❌ Update script not found"; \
		exit 1; \
	fi

update-dry-run: ## Preview what would be updated without making changes
	@echo "🔍 Running update dry run..."
	@if [ -f "./scripts/maintenance/update-containers.sh" ]; then \
		./scripts/maintenance/update-containers.sh --dry-run; \
	else \
		echo "❌ Update script not found"; \
		exit 1; \
	fi

image-lock-status: ## Show image lock status and runtime digest alignment
	@echo "🔒 Image Lock Status"
	@echo "===================="
	@./scripts/maintenance/image-locks.sh status

image-lock-refresh-dry-run: ## Preview digest refresh for locked images
	@echo "🔍 Image Lock Refresh (Dry Run)"
	@echo "==============================="
	@./scripts/maintenance/image-locks.sh refresh --dry-run

image-lock-refresh: ## Refresh locked image digests in .env (no tag bump)
	@echo "🔄 Image Lock Refresh"
	@echo "====================="
	@./scripts/maintenance/image-locks.sh refresh --apply

update-timer-install: ## Install and enable the container update timer
	@echo "📦 Installing update timer..."
	@sudo cp ./scripts/systemd/homelab-update.service /etc/systemd/system/
	@sudo cp ./scripts/systemd/homelab-update.timer /etc/systemd/system/
	@sudo systemctl daemon-reload
	@sudo systemctl enable homelab-update.timer
	@sudo systemctl start homelab-update.timer
	@echo "✅ Update timer installed and enabled"
	@echo "Next run: $$(systemctl list-timers homelab-update.timer --no-pager | grep homelab || echo 'Check with: systemctl list-timers')"

update-timer-status: ## Show status of the container update timer
	@echo "📊 Update Timer Status"
	@echo "======================"
	@systemctl status homelab-update.timer --no-pager 2>/dev/null || echo "Timer not installed"
	@echo ""
	@echo "📅 Timer Schedule:"
	@systemctl list-timers homelab-update.timer --no-pager 2>/dev/null || echo "Timer not found"

update-timer-enable: ## Enable the container update timer
	@sudo systemctl enable homelab-update.timer
	@sudo systemctl start homelab-update.timer
	@echo "✅ Update timer enabled"

update-timer-disable: ## Disable the container update timer
	@sudo systemctl stop homelab-update.timer
	@sudo systemctl disable homelab-update.timer
	@echo "✅ Update timer disabled"

update-timer-run-now: ## Manually trigger the update timer immediately
	@echo "🚀 Triggering manual update..."
	@sudo systemctl start homelab-update.service
	@echo "✅ Update triggered. Check logs with: make update-logs"

update-logs: ## Show recent container update logs
	@echo "📋 Recent Update Logs"
	@echo "====================="
	@if [ -f "./logs/update.log" ]; then \
		tail -100 ./logs/update.log; \
	else \
		echo "No update logs found"; \
	fi
	@echo ""
	@echo "📋 Systemd Journal Logs:"
	@journalctl -u homelab-update.service --no-pager -n 50 2>/dev/null || echo "No journal logs found"

watchdog-install: ## Install and enable the homelab watchdog timer
	@echo "🛡️  Installing watchdog timer..."
	@sudo cp ./scripts/systemd/homelab-watchdog.service /etc/systemd/system/
	@sudo cp ./scripts/systemd/homelab-watchdog.timer /etc/systemd/system/
	@sudo systemctl daemon-reload
	@sudo systemctl enable homelab-watchdog.timer
	@sudo systemctl start homelab-watchdog.timer
	@echo "✅ Watchdog timer installed and enabled"
	@echo "Next run: $$(systemctl list-timers homelab-watchdog.timer --no-pager | grep homelab-watchdog || echo 'Check with: systemctl list-timers')"

watchdog-status: ## Show status of the homelab watchdog service and timer
	@echo "📊 Watchdog Status"
	@echo "=================="
	@if systemctl list-unit-files homelab-watchdog.timer --no-legend 2>/dev/null | grep -q '^homelab-watchdog.timer'; then \
		systemctl status homelab-watchdog.timer --no-pager || true; \
	else \
		echo "Timer not installed"; \
	fi
	@echo ""
	@if systemctl list-unit-files homelab-watchdog.service --no-legend 2>/dev/null | grep -q '^homelab-watchdog.service'; then \
		systemctl status homelab-watchdog.service --no-pager || true; \
	else \
		echo "Service not installed"; \
	fi
	@echo ""
	@echo "📅 Timer Schedule:"
	@systemctl list-timers homelab-watchdog.timer --no-pager 2>/dev/null || echo "Timer not found"

power-restore-check: ## Validate host readiness for AC-loss auto-boot recovery
	@echo "🔌 Power-Restore Readiness"
	@echo "========================="
	@./scripts/maintenance/power-restore-check.sh

sso-status: ## Show Cloudflare/Auth SSO runtime status and required config checks
	@echo "🔐 SSO Edge Status"
	@echo "=================="
	@./scripts/maintenance/sso-status.sh

sso-smoke-test: ## Run end-to-end unauthenticated redirect checks for protected domains
	@echo "🧪 SSO Smoke Test"
	@echo "================="
	@./scripts/maintenance/sso-smoke-test.sh

sso-register-apps: ## Rebuild Authentik app/provider registration for phase-1 SSO
	@echo "🧩 Authentik Registration Rebuild"
	@echo "================================="
	@./scripts/maintenance/authentik-register-apps.sh

sso-register-dry-run: ## Preview Authentik registration changes without applying them
	@echo "🔎 Authentik Registration Dry Run"
	@echo "================================="
	@./scripts/maintenance/authentik-register-apps.sh --dry-run

sso-register-status: ## Show Authentik registration state and phase-1 coverage
	@echo "📚 Authentik Registration Status"
	@echo "================================"
	@./scripts/maintenance/authentik-register-apps.sh --status

ssl-renew: ## Issue/renew wildcard TLS cert via Cloudflare DNS-01 and restart nginx
	@echo "🔐 Renewing Wildcard Certificate"
	@echo "================================"
	@./scripts/maintenance/renew-wildcard-cert.sh

ssl-status: ## Show currently served TLS cert details for auth domain
	@echo "🔎 TLS Certificate Status"
	@echo "========================="
	@domain="$$(grep -m1 '^DOMAIN=' .env | cut -d'=' -f2- | tr -d '\r')"; \
	if [ -z "$$domain" ]; then \
		echo "❌ DOMAIN is missing in .env"; \
		exit 1; \
	fi; \
	openssl s_client -connect auth.$$domain:443 -servername auth.$$domain </dev/null 2>/dev/null | \
		openssl x509 -noout -subject -issuer -dates -ext subjectAltName

burnin-status: ## Show 24h burn-in status summary (use SINCE='2026-03-10 12:00:00')
	@echo "🧪 Burn-in Status"
	@echo "================="
	@SINCE="$(SINCE)"; \
	if [ -z "$$SINCE" ]; then SINCE="24 hours ago"; fi; \
	./scripts/maintenance/burnin-status.sh --since "$$SINCE"

watchdog-run-now: ## Run watchdog once immediately
	@echo "🚀 Triggering watchdog now..."
	@sudo systemctl start homelab-watchdog.service
	@echo "✅ Watchdog triggered. Check logs with: journalctl -u homelab-watchdog.service -n 50"

watchdog-disable: ## Disable the homelab watchdog timer
	@sudo systemctl stop homelab-watchdog.timer
	@sudo systemctl disable homelab-watchdog.timer
	@echo "✅ Watchdog timer disabled"

automation-reconcile: ## Sync systemd units and remove stale user cron entries
	@echo "🧰 Reconciling homelab automation..."
	@if [ -f "./scripts/maintenance/reconcile-automation.sh" ]; then \
		./scripts/maintenance/reconcile-automation.sh; \
	else \
		echo "❌ reconcile-automation.sh not found"; \
		exit 1; \
	fi

host-stabilize-prep: ## Create recovery point and baseline diagnostics before host cleanup
	@echo "🧷 Preparing host stabilization recovery point"
	@./scripts/maintenance/stabilize-host-prep.sh

host-swap-recover: ## Reset swap and capture pre/post pressure diagnostics
	@echo "♻️  Recovering swap usage"
	@./scripts/maintenance/swap-recover.sh

server-mode-plan: ## Preview Desktop -> Server-mode package/service changes
	@echo "🧾 Previewing server-mode conversion"
	@./scripts/maintenance/convert-to-server-mode.sh

server-mode-apply: ## Apply Desktop -> Server-mode conversion (requires sudo, reboot after)
	@echo "🛠️  Applying server-mode conversion"
	@./scripts/maintenance/convert-to-server-mode.sh --apply

post-reboot-validate: ## Validate host + homelab state after server-mode reboot
	@echo "✅ Running post-reboot validation"
	@./scripts/maintenance/post-reboot-validate.sh

concurrency-guard: ## Snapshot/verify multi-agent git guardrails (MODE=snapshot|verify LABEL=name ALLOW_PREFIXES='path1 path2')
	@if [ -z "$(MODE)" ] || [ -z "$(LABEL)" ]; then \
		echo "❌ Usage: make concurrency-guard MODE=<snapshot|verify> LABEL=<chunk> [ALLOW_PREFIXES='path1 path2']"; \
		exit 1; \
	fi
	@args=""; \
	for prefix in $(ALLOW_PREFIXES); do \
		args="$$args --allow-prefix $$prefix"; \
	done; \
	./scripts/maintenance/concurrency-guard.sh "$(MODE)" --label "$(LABEL)" $$args

pressure-watch: ## Run pressure watch (defaults: 6 samples, 4h interval, 2.0 GiB threshold)
	@echo "📈 Running pressure watch..."
	@args="--samples $${SAMPLES:-6} --interval-seconds $${INTERVAL_SECONDS:-14400} --swap-threshold-gib $${SWAP_THRESHOLD_GIB:-2.0}"; \
	if [ "$${ESCALATE:-false}" = "true" ]; then args="$$args --escalate"; fi; \
	if [ "$${NO_SLEEP:-false}" = "true" ]; then args="$$args --no-sleep"; fi; \
	if [ -n "$${BURNIN_SINCE:-}" ]; then args="$$args --burnin-since \"$${BURNIN_SINCE}\""; fi; \
	eval ./scripts/maintenance/pressure-watch.sh $$args

pressure-capture-checkpoint: ## Capture a labeled pressure snapshot (LABEL=TPLUS6H WATCH_DIR=/tmp/... [BURNIN_SINCE='30 minutes ago'])
	@if [ -z "$(LABEL)" ]; then \
		echo "❌ Usage: make pressure-capture-checkpoint LABEL=<TPLUS6H|TPLUS24H|TNOW|...> [WATCH_DIR=/tmp/... BURNIN_SINCE='30 minutes ago']"; \
		exit 1; \
	fi
	@watch_dir="$${WATCH_DIR:-/tmp/homelab-pressure-watch-20260314_115740}"; \
	 burnin_since="$${BURNIN_SINCE:-30 minutes ago}"; \
	 "$(CURDIR)/scripts/maintenance/capture-pressure-snapshot.sh" "$(LABEL)" "$$watch_dir" --burnin-since "$$burnin_since"

pressure-checkpoint-gate: ## Evaluate one timed checkpoint (LABEL=TPLUS6H|TPLUS24H WATCH_DIR=/tmp/... [PREV_LABEL=<label>] [SWAP_THRESHOLD_GIB=2.0])
	@if [ -z "$(LABEL)" ]; then \
		echo "❌ Usage: make pressure-checkpoint-gate LABEL=<TPLUS6H|TPLUS24H|...> [WATCH_DIR=/tmp/... PREV_LABEL=<label> SWAP_THRESHOLD_GIB=2.0]"; \
		exit 1; \
	fi
	@WATCH_DIR="$${WATCH_DIR:-/tmp/homelab-pressure-watch-20260314_115740}" \
	 LABEL="$(LABEL)" \
	 PREV_LABEL="$(PREV_LABEL)" \
	 SWAP_THRESHOLD_GIB="$${SWAP_THRESHOLD_GIB:-2.0}" \
	 "$(CURDIR)/scripts/maintenance/pressure-checkpoint-gate.sh"

pressure-gates-status: ## Evaluate both timed checkpoints from watch artifacts (always prints status)
	@set +e; \
	 WATCH_DIR="$${WATCH_DIR:-/tmp/homelab-pressure-watch-20260314_115740}"; \
	 SWAP_THRESHOLD_GIB="$${SWAP_THRESHOLD_GIB:-2.0}"; \
	 echo "🔎 T+6 checkpoint"; \
	 WATCH_DIR="$$WATCH_DIR" LABEL=TPLUS6H PREV_LABEL=T0 SWAP_THRESHOLD_GIB="$$SWAP_THRESHOLD_GIB" "$(CURDIR)/scripts/maintenance/pressure-checkpoint-gate.sh"; rc6=$$?; \
	 echo; \
	 echo "🔎 T+24 checkpoint"; \
	 WATCH_DIR="$$WATCH_DIR" LABEL=TPLUS24H PREV_LABEL=TPLUS6H SWAP_THRESHOLD_GIB="$$SWAP_THRESHOLD_GIB" "$(CURDIR)/scripts/maintenance/pressure-checkpoint-gate.sh"; rc24=$$?; \
	 echo; \
	 if [ "$$rc6" -eq 2 ] || [ "$$rc24" -eq 2 ]; then \
	   echo "❌ At least one checkpoint is BLOCKED"; \
	   exit 2; \
	 fi; \
	 echo "✅ Checkpoint evaluation completed (WAITING/GREENLIGHT only)"

schedule-pressure-gate-checkpoints: ## Schedule timed gate-token snapshots (TPLUS6_GATE_ON_CALENDAR / TPLUS24_GATE_ON_CALENDAR)
	@set -e; \
	 watch_dir="$${WATCH_DIR:-/tmp/homelab-pressure-watch-20260314_115740}"; \
	 swap_threshold="$${SWAP_THRESHOLD_GIB:-2.0}"; \
	 t6_calendar="$${TPLUS6_GATE_ON_CALENDAR:-2026-03-14 18:21:10}"; \
	 t24_calendar="$${TPLUS24_GATE_ON_CALENDAR:-2026-03-15 12:21:10}"; \
	 systemctl --user stop homelab-pressure-gate-tplus6h.timer homelab-pressure-gate-tplus6h.service >/dev/null 2>&1 || true; \
	 systemctl --user stop homelab-pressure-gate-tplus24h.timer homelab-pressure-gate-tplus24h.service >/dev/null 2>&1 || true; \
	 systemctl --user reset-failed homelab-pressure-gate-tplus6h.timer homelab-pressure-gate-tplus6h.service >/dev/null 2>&1 || true; \
	 systemctl --user reset-failed homelab-pressure-gate-tplus24h.timer homelab-pressure-gate-tplus24h.service >/dev/null 2>&1 || true; \
	 echo "⏱️ Scheduling T+6 gate evaluation on: $$t6_calendar"; \
	 systemd-run --user --on-calendar="$$t6_calendar" --unit=homelab-pressure-gate-tplus6h \
	   /usr/bin/bash -lc "WATCH_DIR=$$watch_dir LABEL=TPLUS6H PREV_LABEL=T0 SWAP_THRESHOLD_GIB=$$swap_threshold '$(CURDIR)/scripts/maintenance/pressure-checkpoint-gate.sh' | tee $$watch_dir/TPLUS6H-gate.txt" \
	   >/dev/null; \
	 echo "⏱️ Scheduling T+24 gate evaluation on: $$t24_calendar"; \
	 systemd-run --user --on-calendar="$$t24_calendar" --unit=homelab-pressure-gate-tplus24h \
	   /usr/bin/bash -lc "WATCH_DIR=$$watch_dir LABEL=TPLUS24H PREV_LABEL=TPLUS6H SWAP_THRESHOLD_GIB=$$swap_threshold '$(CURDIR)/scripts/maintenance/pressure-checkpoint-gate.sh' | tee $$watch_dir/TPLUS24H-gate.txt" \
	   >/dev/null; \
	 echo "✅ Gate timers scheduled"

baseline-bundle: ## Capture baseline evidence bundle (health, burn-in, budget, preflight)
	@echo "📦 Capturing baseline bundle..."
	@./scripts/maintenance/capture-baseline-bundle.sh

post-t24-terraform-apply: ## Run gated Terraform apply using pressure-watch T+24 artifacts (WATCH_DIR=/tmp/... SWAP_THRESHOLD_GIB=2.0 EXPECTED_PLAN_ADDS=7)
	@echo "🧭 Running post-T+24 gated Terraform apply"
	@WATCH_DIR="$${WATCH_DIR:-/tmp/homelab-pressure-watch-20260314_115740}" \
	 SWAP_THRESHOLD_GIB="$${SWAP_THRESHOLD_GIB:-2.0}" \
	 EXPECTED_PLAN_ADDS="$${EXPECTED_PLAN_ADDS:-7}" \
	 "$(CURDIR)/scripts/maintenance/post-t24-terraform-apply.sh"

schedule-post-t24-terraform-apply: ## Schedule gated Terraform apply after pressure watch (default: T+24 timer + 5 min)
	@set -e; \
	 t24_next="$$(systemctl --user list-timers --all --no-legend homelab-pressure-watch-tplus24h.timer 2>/dev/null | awk '{if ($$1 != "-") print $$1" "$$2" "$$3" "$$4}')"; \
	 if [ -n "$${APPLY_ON_CALENDAR:-}" ]; then \
	   on_calendar="$${APPLY_ON_CALENDAR}"; \
	 elif [ -n "$$t24_next" ] && [ "$$t24_next" != "n/a" ]; then \
	   on_calendar="$$(date -d "$$t24_next + 5 minutes" '+%Y-%m-%d %H:%M:%S')"; \
	 else \
	   on_calendar="2026-03-15 12:05:00"; \
	 fi; \
	 watch_dir="$${WATCH_DIR:-/tmp/homelab-pressure-watch-20260314_115740}"; \
	 swap_threshold="$${SWAP_THRESHOLD_GIB:-2.0}"; \
	 if [ -n "$$t24_next" ] && [ "$$t24_next" != "n/a" ]; then \
	   on_epoch="$$(date -d "$$on_calendar" +%s)"; \
	   t24_epoch="$$(date -d "$$t24_next" +%s)"; \
	   if [ "$$on_epoch" -le "$$t24_epoch" ]; then \
	     echo "❌ Refusing schedule: apply time ($$on_calendar) must be after T+24 timer ($$t24_next)"; \
	     exit 1; \
	   fi; \
	 fi; \
	 systemctl --user stop homelab-post-t24-terraform-apply.timer >/dev/null 2>&1 || true; \
	 systemctl --user stop homelab-post-t24-terraform-apply.service >/dev/null 2>&1 || true; \
	 systemctl --user reset-failed homelab-post-t24-terraform-apply.timer >/dev/null 2>&1 || true; \
	 systemctl --user reset-failed homelab-post-t24-terraform-apply.service >/dev/null 2>&1 || true; \
	 echo "⏱️ Scheduling post-T+24 apply on: $$on_calendar"; \
	 systemd-run --user --on-calendar="$$on_calendar" --unit=homelab-post-t24-terraform-apply \
	   env WATCH_DIR="$$watch_dir" SWAP_THRESHOLD_GIB="$$swap_threshold" \
	   "$(CURDIR)/scripts/maintenance/post-t24-terraform-apply.sh" \
	   >/dev/null; \
	 echo "✅ Timer scheduled: homelab-post-t24-terraform-apply.timer (watch_dir=$$watch_dir threshold=$$swap_threshold)"

# Migration helpers (K3s + Terraform)
serena-mcp-setup: ## Build and register Serena MCP image with node+terraform dependencies
	@echo "🧠 Setting up Serena MCP..."
	@./scripts/deployment/setup-serena-mcp.sh

migration-toolchain: ## Install kubectl/helm/sops/age into ~/.local/bin
	@echo "🧰 Installing migration tooling"
	@./scripts/migration/install-tooling.sh

migration-preflight: ## Run migration preflight checks (tools, edge services, lint/validate)
	@echo "🛫 Migration preflight"
	@./scripts/migration/preflight.sh

k3s-bootstrap: ## Install k3s (if needed) and apply baseline namespaces/policies
	@echo "☸️  Bootstrapping k3s baseline"
	@./scripts/migration/bootstrap-k3s.sh

migration-budget: ## Show k3s namespace quotas and current resource pressure
	@echo "📉 Migration resource budget"
	@./scripts/migration/check-resource-budget.sh

wave-a-deploy: ## Deploy wave A services (homepage + blackbox-exporter)
	@echo "🌊 Deploying wave A"
	@helm upgrade --install homepage ./k8s/helm/homepage -n apps --create-namespace
	@helm upgrade --install blackbox-exporter ./k8s/helm/blackbox-exporter -n observability --create-namespace

wave-a-gate: ## Deploy Wave A and enforce a burn-in stability gate (BURNIN_MINUTES=30)
	@echo "🧪 Running Wave A stability gate"
	@./scripts/migration/wave-a-gate.sh --burnin-minutes "$${BURNIN_MINUTES:-30}" --interval-seconds "$${CHECK_INTERVAL_SECONDS:-60}"

wave-b-deploy: ## Deploy wave B pilot service (filebrowser)
	@echo "🌊 Deploying wave B"
	@helm upgrade --install filebrowser ./k8s/helm/filebrowser -n apps --create-namespace

wave-rollback: ## Show rollback checks for a release (usage: make wave-rollback NS=apps RELEASE=homepage REV=1)
	@if [ -z "$(NS)" ] || [ -z "$(RELEASE)" ]; then \
		echo "❌ Usage: make wave-rollback NS=<namespace> RELEASE=<release> [REV=<revision>]"; \
		exit 1; \
	fi
	@rev="$(REV)"; \
	if [ -z "$$rev" ]; then rev=1; fi; \
	./scripts/migration/rollback-checks.sh "$(NS)" "$(RELEASE)" "$$rev"

restart: ## Restart all services
	@echo "🔄 Restarting all services..."
	docker compose restart
	@echo "✅ Restart complete"

restart-service: ## Restart specific service (usage: make restart-service SERVICE=nginx)
	@if [ -z "$(SERVICE)" ]; then \
		echo "❌ Please specify SERVICE=service_name"; \
		echo "Available services:"; \
		docker compose ps --services; \
		exit 1; \
	fi
	@echo "🔄 Restarting $(SERVICE)..."
	docker compose restart $(SERVICE)
	@echo "✅ $(SERVICE) restarted"

# Information
info: ## Show homelab information
	@echo "🏠 Homelab Information"
	@echo "======================"
	@echo "Hostname: $$(hostname)"
	@echo "Tailscale IP: $$(grep TAILSCALE_IP .env | cut -d'=' -f2)"
	@echo "Domain: $$(grep DOMAIN .env | cut -d'=' -f2)"
	@echo "Services:"
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

urls: ## Show service URLs
	@echo "🔗 Service URLs"
	@echo "==============="
	@echo "Homepage:        https://homelab.example.com"
	@echo "Home Assistant:  https://homeassistant.homelab.example.com"
	@echo "Stremio:         https://stremio.homelab.example.com"
	@echo "Uptime Kuma:     https://uptime.homelab.example.com"
	@echo "Portainer:       https://portainer.homelab.example.com"
	@echo "Grafana:         https://grafana.homelab.example.com"
	@echo "Pi-hole:         https://pihole.homelab.example.com"
	@echo "FileBrowser:     https://files.homelab.example.com"
	@echo "What's Up Docker: https://docker.homelab.example.com"
	@echo ""
	@echo "🔬 Monitoring Dashboards"
	@echo "========================"
	@echo "Prometheus:      https://prometheus.homelab.example.com"
	@echo "Netdata:         https://netdata.homelab.example.com"
	@echo "cAdvisor:        https://cadvisor.homelab.example.com"
	@echo ""
	@echo "📊 Security Reports"
	@echo "==================="
	@echo "Reports:         https://files.homelab.example.com (homelab/security-reports/)"

# Quick actions
quick-deploy: ## Quick deploy with status check
	@$(MAKE) deploy
	@sleep 10
	@$(MAKE) health

quick-backup: ## Quick backup with verification
	@$(MAKE) backup
	@echo "Verifying latest backup..."
	@latest=$$(ls -t backups/homelab_backup_*.tar.gz 2>/dev/null | head -1); \
	if [ -n "$$latest" ]; then \
		./scripts/maintenance/automated-backup.sh --verify "$$latest"; \
	fi
