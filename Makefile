# Makefile for Homelab Manager Development

.PHONY: help install install-dev test test-unit test-integration lint format type-check security clean setup pre-commit install-hooks

# Default target
help:
	@echo "Homelab Manager Development Commands"
	@echo "===================================="
	@echo ""
	@echo "Setup:"
	@echo "  make setup          - Setup development environment"
	@echo "  make install        - Install production dependencies"
	@echo "  make install-dev    - Install development dependencies"
	@echo "  make install-hooks  - Install pre-commit hooks"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run all tests"
	@echo "  make test-unit      - Run unit tests"
	@echo "  make test-integration - Run integration tests"
	@echo "  make test-cov       - Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           - Run all linting tools"
	@echo "  make format         - Format code with black and isort"
	@echo "  make type-check     - Run type checking with mypy"
	@echo "  make security       - Run security checks"
	@echo ""
	@echo "Development:"
	@echo "  make pre-commit     - Run pre-commit on all files"
	@echo "  make clean          - Clean up generated files"
	@echo ""

# Setup development environment
setup: install-dev install-hooks
	@echo "✅ Development environment setup complete!"

# Install production dependencies
install:
	@echo "📦 Installing production dependencies..."
	pip install -r scripts/requirements.txt

# Install development dependencies
install-dev:
	@echo "📦 Installing development dependencies..."
	pip install -r scripts/requirements-dev.txt

# Install pre-commit hooks
install-hooks:
	@echo "🔧 Installing pre-commit hooks..."
	pre-commit install
	pre-commit install --hook-type commit-msg

# Run all tests
test:
	@echo "🧪 Running all tests..."
	pytest tests/ -v

# Run unit tests
test-unit:
	@echo "🧪 Running unit tests..."
	pytest tests/unit/ -v

# Run integration tests
test-integration:
	@echo "🧪 Running integration tests..."
	pytest tests/integration/ -v

# Run tests with coverage
test-cov:
	@echo "🧪 Running tests with coverage..."
	pytest tests/ --cov=homelab_manager --cov-report=html --cov-report=term-missing

# Run all linting tools
lint: format type-check
	@echo "🔍 Running flake8..."
	flake8 scripts/homelab_manager/ tests/
	@echo "🔍 Running pylint..."
	pylint scripts/homelab_manager/ tests/

# Format code
format:
	@echo "🎨 Formatting code with black..."
	black scripts/homelab_manager/ tests/
	@echo "🎨 Sorting imports with isort..."
	isort scripts/homelab_manager/ tests/

# Type checking
type-check:
	@echo "🔍 Running type checking with mypy..."
	mypy scripts/homelab_manager/

# Security checks
security:
	@echo "🔒 Running security checks with bandit..."
	bandit -r scripts/homelab_manager/ -f json -o bandit-report.json
	@echo "🔒 Running safety check..."
	safety check

# Run pre-commit on all files
pre-commit:
	@echo "🔧 Running pre-commit on all files..."
	pre-commit run --all-files

# Clean up generated files
clean:
	@echo "🧹 Cleaning up generated files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name "bandit-report.json" -delete
	find . -type f -name ".coverage" -delete
	find . -type f -name "coverage.xml" -delete

# Development workflow
dev: format lint test
	@echo "✅ Development checks complete!"

# CI/CD pipeline simulation
ci: clean install-dev lint test security
	@echo "✅ CI/CD pipeline simulation complete!"

# Quick development check
quick: format test-unit
	@echo "✅ Quick development check complete!"
