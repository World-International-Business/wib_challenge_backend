# Contributing to WIB Challenge

Thank you for your interest in contributing to the WIB Challenge platform! This document provides guidelines and information on how to contribute to this project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment (see [Development Setup](#development-setup))
4. Create a topic branch for your changes
5. Make your changes
6. Test your changes
7. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.11+
- MySQL 8.0+ or compatible database
- Redis (for caching and sessions)
- Git

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/wib_challenge.git
   cd wib_challenge
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env file with your local settings
   ```

5. **Setup database:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py create_default_settings
   ```

6. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

### Docker Development Setup

Alternatively, you can use Docker:

```bash
docker-compose up -d
```

## How to Contribute

### Reporting Bugs

- Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.yml)
- Include as much detail as possible
- Provide steps to reproduce the issue
- Include relevant logs and error messages

### Suggesting Features

- Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.yml)
- Clearly describe the feature and its benefits
- Consider if this fits with the project's goals

### Asking Questions

- Use the [Question template](.github/ISSUE_TEMPLATE/question.yml)
- Check existing issues and documentation first
- Be specific about what you're trying to accomplish

## Pull Request Process

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes:**
   - Follow the coding standards
   - Write tests for new functionality
   - Update documentation as needed

3. **Test your changes:**
   ```bash
   python manage.py test
   flake8 .
   black --check .
   isort --check-only .
   ```

4. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request:**
   - Use the [Pull Request template](.github/PULL_REQUEST_TEMPLATE/pull_request_template.md)
   - Reference any related issues
   - Provide a clear description of the changes

### Commit Message Convention

We follow conventional commit format:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

Example: `feat: add user authentication endpoint`

## Coding Standards

### Python Style

- Follow PEP 8
- Use Black for code formatting
- Use isort for import sorting
- Maximum line length: 127 characters
- Use type hints where possible

### Django Specific

- Follow Django coding style guidelines
- Use Django's built-in features when possible
- Keep views thin, models fat
- Use Django REST Framework for API endpoints
- Write docstrings for models, views, and complex functions

### Database

- Always create migrations for model changes
- Use descriptive migration names
- Never edit existing migrations that have been merged
- Use database constraints and validations

## Testing

### Writing Tests

- Write tests for all new functionality
- Use Django's TestCase class
- Follow the AAA pattern (Arrange, Act, Assert)
- Test both success and failure scenarios
- Aim for good test coverage

### Running Tests

```bash
# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test accounts

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

### Test Structure

```python
class TestUserModel(TestCase):
    def setUp(self):
        """Set up test data"""
        pass
    
    def test_user_creation(self):
        """Test user can be created successfully"""
        # Arrange
        user_data = {...}
        
        # Act
        user = User.objects.create(**user_data)
        
        # Assert
        self.assertEqual(user.email, user_data['email'])
```

## Documentation

### Code Documentation

- Write clear docstrings for all public methods
- Use Google-style docstrings
- Document complex algorithms and business logic
- Keep comments up to date with code changes

### API Documentation

- Use drf-spectacular for API documentation
- Document all endpoints with appropriate decorators
- Include example requests and responses
- Document error responses

### README Updates

When making significant changes:
- Update installation instructions if needed
- Update usage examples
- Add new features to the feature list

## Project Structure

```
wib_challenge/
├── accounts/          # User authentication and management
├── candidates/        # Candidate profiles and management
├── core/             # Core functionality and utilities
├── evaluations/      # Assessment and evaluation system
├── jobs/             # Job posting and management
├── learning/         # Learning platform and courses
├── organizations/    # Organization management
├── questions/        # Question bank and management
├── templates/        # HTML templates
├── wib_challenge/    # Django project settings
└── manage.py
```

## Getting Help

- Check the [documentation](README.md)
- Search existing [issues](https://github.com/World-International-Business/wib_challenge/issues)
- Ask questions using the [Question template](.github/ISSUE_TEMPLATE/question.yml)
- Join our community discussions

## Recognition

Contributors will be recognized in our README and release notes. We appreciate all contributions, big and small!

Thank you for contributing to WIB Challenge! 🚀