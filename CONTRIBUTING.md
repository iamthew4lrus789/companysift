# Contributing to CompanySift

Thank you for your interest in contributing to CompanySift! This document provides guidelines for contributing to the project.

## How to Contribute

### Reporting Issues

If you find a bug or have a feature request:

1. Check existing [issues](../../issues) to avoid duplicates
2. Create a new issue with a clear title and description
3. Include steps to reproduce (for bugs)
4. Add relevant labels if possible

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature-name`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest tests/ -v`)
6. Commit with clear messages
7. Push to your fork
8. Open a pull request

### Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Keep functions focused and well-documented
- Write docstrings for public functions and classes

### Testing

- Write tests for new functionality
- Maintain or improve test coverage
- Run the full test suite before submitting:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Commit Messages

- Use clear, descriptive commit messages
- Start with a verb (Add, Fix, Update, Remove, etc.)
- Reference issues when relevant (`Fixes #123`)

Example:
```
Add fuzzy matching for company name variants

- Implement Levenshtein distance comparison
- Add unit tests for edge cases
- Update confidence scoring weights

Fixes #45
```

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/companysift.git
cd companysift

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests to verify setup
pytest tests/ -v
```

## Questions?

Feel free to open an issue for questions or discussions about the project.
