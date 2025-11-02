# Homelab Management Makefile
# Provides convenient targets for homelab operations

.PHONY: help install deploy status logs health backup restore security-scan monitor clean test

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
	@if [ -f "./scripts/automated-backup.sh" ]; then \
		./scripts/automated-backup.sh; \
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
	@if [ -f "./scripts/security-scan.sh" ]; then \
		./scripts/security-scan.sh; \
	else \
		echo "❌ Security scan script not found"; \
		echo "Please run: make install"; \
		exit 1; \
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
clean: ## Clean up old logs and temporary files
	@echo "🧹 Cleaning up..."
	@find logs/ -name "*.log" -mtime +7 -delete 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@docker system prune -f
	@echo "✅ Cleanup complete"

update: ## Update all container images
	@echo "🔄 Updating container images..."
	docker compose pull
	docker compose up -d
	@echo "✅ Update complete"

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
		./scripts/automated-backup.sh --verify "$$latest"; \
	fi
