# Changelog

All notable changes to Luk's Homelab will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2025-01-09

### 🔧 Bug Fixes and Improvements

#### Fixed
- **Security Issue**: Replaced `os.system()` with `subprocess.run()` for better security
- **Test Issues**: Fixed hardcoded paths in test classes to use test directories
- **Type Annotations**: Added missing type annotations for better type checking
- **Test Mocking**: Improved test fixtures and mocking for more reliable tests

#### Added
- **Development Documentation**: Comprehensive development guide with best practices
- **Fixed Test Files**: Separate test files with proper test directory handling
- **Security Improvements**: Better subprocess handling and input validation

#### Changed
- **Test Architecture**: Tests now properly use temporary directories
- **Security Scanning**: Enhanced security checks with better subprocess handling
- **Development Workflow**: Improved development commands and documentation

## [2.0.0] - 2025-01-09

### 🎉 Major Release: Python-Based Automation System

#### Added
- **Python Automation System** - Complete rewrite in Python for better maintainability
- **Rich CLI Interface** - Beautiful, colored command-line interface
- **Comprehensive Health Monitoring** - Service health checks with system resource monitoring
- **Advanced Update Management** - Automated update checking and deployment
- **Configuration Validation** - Environment variable validation with security checks
- **Automated Backup System** - Docker volume backups with retention policies
- **Cron Integration** - Automated task scheduling for maintenance
- **Service Version Tracking** - Current version monitoring for all services

#### Changed
- **Converted from Shell to Python** - All automation scripts now use Python
- **Simplified Architecture** - Removed overkill components (Terraform, Ansible, complex monitoring)
- **Enhanced Error Handling** - Comprehensive exception handling and user feedback
- **Improved Logging** - Structured logging with file and console output
- **Better Documentation** - Comprehensive README with examples and architecture

#### Removed
- **Terraform Infrastructure** - Too complex for homelab use case
- **Ansible Playbooks** - Overkill for single-server deployment
- **Complex Monitoring Stack** - ELK stack, Alertmanager, complex Prometheus alerts
- **GitHub Actions CI/CD** - Not needed for personal homelab
- **Shell Scripts** - Converted to Python equivalents
- **DevOps Analysis Documentation** - Analysis complete, no longer needed

#### Fixed
- **Environment Variable Loading** - Safer parsing with special character support
- **Docker Container Management** - Better error handling and status reporting
- **Backup System** - Improved reliability and error handling
- **Service Health Checks** - More robust HTTP endpoint checking

#### Security
- **Environment Variable Validation** - Comprehensive validation with security checks
- **Secure Configuration Templates** - `.env.example` with placeholder values
- **Improved Secret Management** - All sensitive data in environment variables
- **Docker Security** - Non-root execution and network isolation
- **Zero Hardcoded Secrets** - All sensitive data properly externalized
- **Password Strength Validation** - Automatic password complexity checks
- **Token Format Validation** - Ensures proper API token formats
- **Secure Subprocess Handling** - Uses `subprocess.run()` instead of `os.system()`

## [1.0.0] - 2025-01-09

### 🏠 Initial Release: Home Assistant Dashboard Setup

#### Added
- **Home Assistant Dashboard** - Custom dashboard with HACS components
- **HACS Integration** - Home Assistant Community Store setup
- **Mushroom Cards** - Modern card collection for Lovelace
- **Button Card** - Highly customizable button card
- **Mini Graph Card** - Minimalistic graph card for sensor data
- **UI Lovelace Minimalist** - Clean theme and card collection
- **Docker Compose Setup** - Container orchestration for homelab services
- **Environment Configuration** - Secure environment variable management
- **Basic Automation** - Shell scripts for container management

#### Services
- **Home Assistant** - Home automation hub
- **Grafana** - Monitoring and dashboards
- **Portainer** - Container management
- **Pi-hole** - Network-wide ad blocking
- **Uptime Kuma** - Uptime monitoring
- **Prometheus** - Metrics collection
- **What's Up Docker** - Container update monitoring

#### Features
- **Dashboard Configuration** - YAML-based dashboard setup
- **Theme Integration** - Brazilian theme for Home Assistant
- **Service Health Monitoring** - Basic health checks
- **Backup System** - Manual backup functionality
- **Update Management** - Container update checking

---

## Version History

- **v2.0.0** - Python-based automation system with comprehensive features
- **v1.0.0** - Initial Home Assistant dashboard setup with basic automation

## Migration Guide

### From v1.0.0 to v2.0.0

1. **Environment Variables** - No changes needed, all existing variables are compatible
2. **Docker Compose** - No changes needed, same configuration
3. **Application Data** - No changes needed, all data preserved
4. **New Commands** - Use `./homelab` instead of individual scripts
5. **Python Dependencies** - Run `pip install -r scripts/requirements.txt` in virtual environment

### Breaking Changes

- **Shell Scripts Removed** - All shell automation scripts converted to Python
- **Terraform/Ansible Removed** - Infrastructure as Code components removed
- **Complex Monitoring Removed** - ELK stack and complex monitoring removed

### New Features

- **Rich CLI** - Beautiful command-line interface
- **Automated Tasks** - Cron job integration
- **Configuration Validation** - Environment variable validation
- **Service Version Tracking** - Current version monitoring
- **Enhanced Health Monitoring** - Comprehensive service health checks

## Future Roadmap

### Planned Features
- **Web Dashboard** - Web-based management interface
- **Mobile App** - Mobile management application
- **Advanced Monitoring** - Custom Grafana dashboards
- **Backup Encryption** - Encrypted backup storage
- **Service Dependencies** - Dependency-aware updates
- **Health Alerts** - Email/Discord notifications
- **Performance Metrics** - Detailed performance monitoring

### Potential Improvements
- **Kubernetes Support** - Optional Kubernetes deployment
- **Multi-Node Support** - Distributed homelab setup
- **Advanced Security** - Security scanning and hardening
- **Backup Verification** - Automated backup testing
- **Service Discovery** - Automatic service detection
- **Plugin System** - Extensible automation system

---

*This changelog follows [Keep a Changelog](https://keepachangelog.com/) format and [Semantic Versioning](https://semver.org/) principles.*
