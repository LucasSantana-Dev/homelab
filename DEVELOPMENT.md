# Development Guide

This document provides comprehensive guidance for developing and maintaining the Homelab Manager Python automation system.

## 🛠️ Development Environment Setup

### Prerequisites

- Python 3.10 or higher
- Docker and Docker Compose
- Git

### Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd homelab

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install development dependencies
make install-dev

# Install pre-commit hooks
make install-hooks
```

### Development Commands

```bash
# Setup development environment
make setup

# Run tests
make test
make test-unit
make test-cov

# Code quality
make format
make lint
make type-check
make security

# Development workflow
make dev          # Quick development check
make ci           # Full CI/CD simulation
make clean        # Clean up generated files
```

## 🧪 Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── test_automation.py
│   ├── test_config.py
│   ├── test_health.py
│   └── test_simple.py
└── integration/            # Integration tests
    └── (future tests)
```

### Writing Tests

#### Unit Tests

Unit tests focus on testing individual functions and methods in isolation:

```python
def test_automation_init(self, temp_homelab_dir, mock_docker_client):
    """Test HomelabAutomation initialization"""
    with patch('homelab_manager.automation.docker.from_env', return_value=mock_docker_client):
        automation = HomelabAutomation(str(temp_homelab_dir))

        assert automation.homelab_dir == temp_homelab_dir
        assert automation.backup_dir == temp_homelab_dir / "backups"
```

#### Test Fixtures

Use the provided fixtures for consistent test setup:

- `temp_homelab_dir`: Temporary homelab directory for testing
- `mock_docker_client`: Mock Docker client for container operations
- `mock_requests`: Mock HTTP requests for service health checks
- `mock_subprocess`: Mock subprocess calls for command execution
- `mock_psutil`: Mock system resource monitoring

#### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/test_automation.py -v

# Run with coverage
make test-cov

# Run specific test
pytest tests/unit/test_automation.py::TestHomelabAutomation::test_init -v
```

## 🔍 Code Quality

### Formatting

We use **Black** for code formatting with 88-character line length:

```bash
make format
```

### Linting

Multiple linting tools ensure code quality:

- **flake8**: Style guide enforcement
- **pylint**: Advanced code analysis
- **mypy**: Static type checking

```bash
make lint
```

### Type Checking

We use **mypy** for static type checking:

```bash
make type-check
```

Add type annotations to all functions:

```python
def backup(self) -> Optional[str]:
    """Create backup of homelab data"""
    # Implementation
```

### Security

**bandit** scans for security vulnerabilities:

```bash
make security
```

## 🚀 CI/CD Pipeline

### GitHub Actions

The project includes a comprehensive CI/CD pipeline:

- **Multi-Python Testing**: Python 3.10, 3.11, 3.12
- **Code Quality**: Linting, formatting, type checking
- **Security Scanning**: Bandit, Safety, Trivy
- **Docker Validation**: Compose syntax checking
- **Pre-commit Hooks**: Automated quality gates

### Pre-commit Hooks

Automated quality checks run before each commit:

- Code formatting (Black, isort)
- Linting (flake8, pylint)
- Type checking (mypy)
- Security scanning (bandit)
- YAML validation
- Markdown linting

## 📝 Documentation

### Code Documentation

- **Docstrings**: All functions and classes have docstrings
- **Type Hints**: Comprehensive type annotations
- **Comments**: Complex logic is documented

### Project Documentation

- **README.md**: Project overview and quick start
- **CHANGELOG.md**: Version history and changes
- **DEVELOPMENT.md**: This development guide
- **API Documentation**: Auto-generated from docstrings

### Writing Documentation

```python
def backup(self) -> Optional[str]:
    """
    Create backup of homelab data.

    Returns:
        Optional[str]: Path to backup directory if successful, None if failed

    Raises:
        Exception: If backup creation fails
    """
```

## 🔧 Development Workflow

### 1. Feature Development

```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes
# Run tests
make test

# Format code
make format

# Check quality
make lint

# Commit changes
git add .
git commit -m "feat: add new feature"
```

### 2. Bug Fixes

```bash
# Create bugfix branch
git checkout -b fix/bug-description

# Fix the bug
# Add tests
make test

# Commit fix
git commit -m "fix: resolve bug description"
```

### 3. Code Review

- All changes require code review
- CI/CD must pass before merge
- Security scan must pass
- Test coverage must be maintained

## 🐛 Debugging

### Common Issues

#### Test Failures

```bash
# Run specific test with verbose output
pytest tests/unit/test_automation.py::TestHomelabAutomation::test_init -v -s

# Run with debugging
pytest --pdb tests/unit/test_automation.py
```

#### Type Checking Issues

```bash
# Run mypy on specific file
mypy scripts/homelab_manager/automation.py

# Install missing type stubs
pip install types-requests types-docker types-psutil
```

#### Security Issues

```bash
# Run bandit on specific file
bandit -r scripts/homelab_manager/automation.py

# Check specific security issue
bandit -r scripts/homelab_manager/ -f json -o bandit-report.json
```

### Debugging Tools

- **pdb**: Python debugger
- **pytest --pdb**: Drop into debugger on test failure
- **logging**: Comprehensive logging throughout the application

## 📦 Dependencies

### Production Dependencies

```txt
docker>=6.0.0
rich>=13.0.0
click>=8.0.0
requests>=2.28.0
pyyaml>=6.0
psutil>=5.9.0
```

### Development Dependencies

```txt
pytest>=7.4.0
pytest-cov>=4.1.0
black>=23.7.0
isort>=5.12.0
flake8>=6.0.0
mypy>=1.5.0
pylint>=2.17.0
pre-commit>=3.3.0
bandit>=1.7.0
safety>=2.3.0
```

## 🏗️ Architecture

### Module Structure

```
scripts/homelab_manager/
├── __init__.py              # Package initialization
├── cli.py                   # Command-line interface
├── automation.py            # Main automation logic
├── health.py                # Health monitoring
├── updates.py               # Update management
├── config.py                # Configuration management
└── container_manager.py     # Container operations
```

### Design Patterns

- **Single Responsibility**: Each module has a specific purpose
- **Dependency Injection**: Dependencies are injected via constructors
- **Factory Pattern**: Object creation is centralized
- **Observer Pattern**: Event-driven architecture for monitoring

## 🔒 Security Best Practices

### Code Security

- **Input Validation**: All inputs are validated
- **Subprocess Security**: Use `subprocess.run()` instead of `os.system()`
- **Path Security**: Use `pathlib.Path` for path operations
- **Environment Variables**: Never hardcode secrets

### Security Scanning

- **Bandit**: Static security analysis
- **Safety**: Dependency vulnerability scanning
- **Trivy**: Container security scanning

## 📊 Performance

### Monitoring

- **Resource Usage**: CPU, memory, disk monitoring
- **Response Times**: Service health check timing
- **Error Rates**: Failure tracking and alerting

### Optimization

- **Async Operations**: Use async/await for I/O operations
- **Caching**: Cache frequently accessed data
- **Resource Limits**: Set appropriate resource limits

## 🚀 Deployment

### Production Deployment

```bash
# Install production dependencies
pip install -r scripts/requirements.txt

# Run health check
./homelab check

# Deploy services
./homelab deploy
```

### Development Deployment

```bash
# Install development dependencies
make install-dev

# Run tests
make test

# Deploy with monitoring
./homelab deploy
./homelab monitor
```

## 🤝 Contributing

### Code Standards

- Follow PEP 8 style guide
- Use type hints for all functions
- Write comprehensive tests
- Document all public APIs

### Pull Request Process

1. Create feature branch
2. Make changes with tests
3. Run quality checks
4. Submit pull request
5. Address review feedback
6. Merge after approval

### Commit Messages

Use conventional commits:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Maintenance tasks

## 📚 Resources

### Documentation

- [Python Documentation](https://docs.python.org/3/)
- [pytest Documentation](https://docs.pytest.org/)
- [Black Documentation](https://black.readthedocs.io/)
- [mypy Documentation](https://mypy.readthedocs.io/)

### Tools

- [Docker Documentation](https://docs.docker.com/)
- [Rich Documentation](https://rich.readthedocs.io/)
- [Click Documentation](https://click.palletsprojects.com/)

### Best Practices

- [Python Best Practices](https://docs.python-guide.org/)
- [Testing Best Practices](https://docs.pytest.org/en/latest/goodpractices.html)
- [Security Best Practices](https://bandit.readthedocs.io/)

---

**Happy Coding! 🚀**
