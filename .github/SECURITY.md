# Security Policy

## 🔒 Security Model

This homelab infrastructure follows a **defense-in-depth** approach with multiple security layers:

### Network Security
- **Tailscale-only Access**: All services restricted to Tailscale network (100.0.0.0/8)
- **No Public Exposure**: Services are NOT accessible from the public internet
- **Network Segmentation**: Services organized into isolated network tiers (frontend, backend, monitoring, database)
- **IP Whitelisting**: Nginx reverse proxy enforces Tailscale IP restrictions on all endpoints

### Secrets Management
- **No Hardcoded Secrets**: All credentials stored in `.env` file (gitignored)
- **Environment Variables Only**: Services use `${VARIABLE}` syntax for sensitive data
- **Secret Generation**: Strong passwords generated via `openssl rand -base64 50`
- **Service Isolation**: Each service has unique credentials (no shared passwords)

### Container Security
- **Resource Limits**: All containers have CPU and memory limits defined
- **Health Checks**: Automated health monitoring for all critical services
- **Non-Root Users**: Services run as unprivileged users where possible (PUID/PGID)
- **Read-Only Volumes**: Configuration mounted as read-only where feasible
- **Security Scanning**: Trivy container scanning in CI/CD pipeline

### Authentication & Authorization
- **HTTP Basic Auth**: What's Up Docker protected with htpasswd
- **SSO Available**: Authentik identity provider for centralized authentication
- **Service-Specific Credentials**: Each service has independent authentication

## 🛡️ Security Best Practices

### For Deployment

1. **Strong Credentials**:
   ```bash
   # Generate secure secrets
   openssl rand -base64 50  # For secret keys
   openssl rand -base64 32  # For passwords
   ```

2. **Tailscale Configuration**:
   - Use ACLs to restrict access between services
   - Enable MagicDNS for DNS-based service discovery
   - Regularly rotate Tailscale auth keys

3. **Container Updates**:
   - Use What's Up Docker for update notifications
   - Review changelogs before updating
   - Test updates in non-production first

4. **Backup Security**:
   - Encrypt backups at rest
   - Store backups off-site
   - Test restoration procedures regularly

### For Development

1. **Never Commit Secrets**:
   - `.env` is gitignored - NEVER force-add it
   - Use `.env.example` for documentation only
   - Review `git diff` before commits

2. **Code Scanning**:
   - Pre-commit hooks run security checks locally
   - CI pipeline includes Bandit (Python security), Trivy (container scanning)
   - Dependabot monitors dependency vulnerabilities

3. **Pull Request Review**:
   - All changes require review before merge
   - Security-sensitive changes require extra scrutiny
   - Check for accidental secret exposure in diffs

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

### Reporting Process

1. **DO NOT** open a public GitHub issue for security vulnerabilities
2. Email security details to: **LucasSantana-Dev@users.noreply.github.com**
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

### What to Expect

- **Acknowledgment**: Within 48 hours of your report
- **Status Update**: Within 7 days with our assessment
- **Fix Timeline**: Critical issues patched within 30 days
- **Credit**: Security researchers credited in CHANGELOG (if desired)

### Severity Guidelines

| Severity | Description | Response Time |
|----------|-------------|---------------|
| **Critical** | Remote code execution, data breach, complete system compromise | 24 hours |
| **High** | Authentication bypass, privilege escalation, SQL injection | 7 days |
| **Medium** | Information disclosure, denial of service, CSRF | 30 days |
| **Low** | Security misconfigurations, minor information leaks | 90 days |

## 🔍 Security Auditing

### Regular Security Tasks

**Weekly**:
- Review container update notifications
- Check Uptime Kuma for service anomalies
- Review Grafana dashboards for unusual metrics

**Monthly**:
- Rotate service credentials
- Review Nginx access logs for suspicious activity
- Update all container images
- Backup integrity verification

**Quarterly**:
- Full security audit of exposed endpoints
- Review and update firewall rules
- Penetration testing (if applicable)
- Disaster recovery drill

### Security Monitoring

The homelab includes built-in security monitoring:

- **Prometheus + Alertmanager**: Anomaly detection and alerting
- **Loki + Promtail**: Centralized log analysis
- **Uptime Kuma**: Service availability monitoring
- **Blackbox Exporter**: Endpoint health checks
- **Netdata**: Real-time system intrusion detection

## 📚 Security Resources

### Hardening Guides
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Nginx Security Hardening](https://www.nginx.com/blog/mitigating-ddos-attacks-with-nginx-and-nginx-plus/)
- [Tailscale Security Model](https://tailscale.com/security/)

### Compliance
- This is a **personal homelab** project
- No compliance certifications (SOC2, ISO27001, etc.)
- Not recommended for production business use without additional hardening

## 🔐 Supported Versions

| Version | Supported | Security Updates |
|---------|-----------|------------------|
| 3.x.x   | ✅ Yes    | Active development |
| 2.x.x   | ⚠️ Limited | Critical fixes only |
| 1.x.x   | ❌ No     | End of life |

## 📝 Security Changelog

All security-related changes are documented in [CHANGELOG.md](../CHANGELOG.md) with the `### Security` section.

Recent security improvements:
- **v3.0.0**: Network segmentation design, Authentik SSO, WUD HTTP Basic Auth
- **v2.3.0**: Sentry token environment variable, comprehensive secret removal from git history
- **v2.2.0**: Alertmanager integration, enhanced log parsing, dependency security fixes

## ⚖️ Responsible Disclosure

We believe in responsible disclosure and will work with security researchers to:
- Verify and reproduce reported vulnerabilities
- Develop and test patches
- Coordinate disclosure timing
- Provide credit for discoveries (if desired)

Thank you for helping keep this project secure! 🙏

