# Contributing to Amorce

Thank you for your interest in contributing to Amorce! We welcome contributions from the community.

---

## Code of Conduct

Be respectful, inclusive, and professional. We're building software for the AI agent economy together.

---

## Ways to Contribute

- 🐛 Report bugs
- 💡 Suggest features
- 📖 Improve documentation
- 🔧 Submit code fixes
- 🧪 Add tests
- 🌐 Create new adapters

---

## Getting Started

### 1. Fork the Repository

Click "Fork" on GitHub to create your own copy.

### 2. Clone Your Fork

```bash
git clone https://github.com/YOUR_USERNAME/amorce.git
cd amorce
```

### 3. Create a Branch

```bash
git checkout -b feature/my-new-feature
```

### 4. Set Up Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install in editable mode
pip install -e .
```

---

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_orchestrator.py

# Run with coverage
pytest --cov=./ --cov-report=html
```

### Code Style

We use:
- **Black** for formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking

```bash
# Format code
black .

# Sort imports
isort .

# Lint
flake8 .

# Type check
mypy .
```

### Pre-commit Hooks

Set up pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

---

## Pull Request Process

### 1. Make Your Changes

- Write clear, concise code
- Add tests for new features
- Update documentation
- Follow existing code style

### 2. Commit Your Changes

Use conventional commit messages:

```bash
# Features
git commit -m "feat: add support for custom registries"

# Bug fixes
git commit -m "fix: resolve signature verification race condition"

# Documentation
git commit -m "docs: update deployment guide for AWS"

# Tests
git commit -m "test: add integration tests for HITL flow"

# Chores
git commit -m "chore: update dependencies"
```

### 3. Push to Your Fork

```bash
git push origin feature/my-new-feature
```

### 4. Open a Pull Request

- Go to the original repository
- Click "New Pull Request"
- Select your branch
- Fill in the PR template
- Link any related issues

### 5. Code Review

- Respond to feedback
- Make requested changes
- Push updates to your branch

---

## Contribution Guidelines

### Code Quality

✅ **Do:**
- Write clear, self-documenting code
- Add docstrings to functions and classes
- Include type hints
- Write comprehensive tests
- Keep functions small and focused

❌ **Don't:**
- Submit code without tests
- Ignore linting errors
- Break existing functionality
- Add unnecessary dependencies

### Tests

- **Unit Tests**: Test individual functions
- **Integration Tests**: Test component interaction
- **E2E Tests**: Test complete workflows

Example test structure:

```python
def test_signature_verification():
    """Test that signature verification works correctly"""
    # Arrange
    identity = IdentityManager.generate()
    payload = {"test": "data"}
    
    # Act
    signature = identity.sign(json.dumps(payload))
    
    # Assert
    assert identity.verify(signature, json.dumps(payload))
```

### Documentation

Update docs when you:
- Add new features
- Change APIs
- Fix bugs (if behavior changes)
- Add configuration options

---

## Project Structure

```
amorce/
├── core/               # Core protocol logic
│   ├── interfaces.py   # Abstract interfaces
│   ├── types.py        # Type definitions
│   └── security.py     # Signature verification
├── adapters/           # Pluggable adapters
│   ├── registry/       # Agent registry adapters
│   ├── storage/        # Storage adapters
│   └── rate_limit/     # Rate limiting adapters
├── orchestrator.py     # Main orchestrator
├── tests/              # Test files
├── docs/               # Documentation
└── requirements.txt    # Dependencies
```

---

## Adding a New Adapter

Example: Adding a new registry adapter

### 1. Create the Adapter

```python
# adapters/registry/my_registry.py
from core.interfaces import IAgentRegistry
from typing import Optional, Dict

class MyCustomRegistry(IAgentRegistry):
    def __init__(self, config: Dict):
        self.config = config
        # Initialize your registry
    
    def find_agent(self, agent_id: str) -> Optional[Dict]:
        """Fetch agent from your registry"""
        # Implementation
        pass
    
    def list_agents(self) -> List[Dict]:
        """List all agents"""
        # Implementation
        pass
```

### 2. Add Tests

```python
# tests/test_my_registry.py
def test_find_agent():
    registry = MyCustomRegistry({})
    agent = registry.find_agent("agent-001")
    assert agent is not None
```

### 3. Update Documentation

Add your adapter to `README.md`:

```markdown
### Supported Registries
- File-based (standalone mode)
- Amorce Trust Directory (cloud mode)
- My Custom Registry (configure in .env)
```

---

## Release Process

(For maintainers only)

1. Update version in `__version__.py`
2. Update CHANGELOG.md
3. Create Git tag
4. Push to GitHub
5. GitHub Actions will build and publish

---

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Security**: Email security@amorce.io
- **Chat**: Join our Discord

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Recognition

Contributors are recognized in:
- README.md (Contributors section)
- Release notes
- Project homepage

---

## Thank You!

Every contribution, no matter how small, makes Amorce better. We appreciate your help in building the foundation of the AI agent economy.

**Built with ❤️ by the Amorce community**
