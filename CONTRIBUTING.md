# Contributing to lit_law411-agent

Thank you for your interest in contributing to the Legal Knowledge Base Agent! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct:

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on constructive criticism
- Accept feedback gracefully
- Prioritize the project's best interests

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/lit_law411-agent.git
   cd lit_law411-agent
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/softengineware/lit_law411-agent.git
   ```

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Poetry for dependency management
- Docker and Docker Compose
- Git

### Environment Setup

1. Install Poetry:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install project dependencies:
   ```bash
   poetry install
   ```

3. Install pre-commit hooks:
   ```bash
   poetry run pre-commit install
   ```

4. Copy environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Start development services:
   ```bash
   docker-compose up -d
   ```

## Making Changes

### Branch Naming

Create feature branches with descriptive names:
- `feature/add-youtube-playlist-support`
- `fix/transcription-timeout-error`
- `docs/update-api-examples`
- `refactor/optimize-embedding-pipeline`

### Development Workflow

1. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following our code standards

3. Run pre-commit checks:
   ```bash
   poetry run pre-commit run --all-files
   ```

4. Run tests:
   ```bash
   poetry run pytest
   ```

5. Commit your changes:
   ```bash
   git add .
   git commit -m "feat: add support for YouTube playlists"
   ```

### Commit Message Format

We follow the Conventional Commits specification:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Test additions or modifications
- `chore:` Maintenance tasks
- `perf:` Performance improvements

Examples:
```
feat: add YouTube playlist ingestion support
fix: resolve timeout error in transcription service
docs: update API authentication examples
refactor: optimize vector embedding generation
```

## Code Standards

### Python Style Guide

We use several tools to maintain code quality:

- **Black** for code formatting (line length: 88)
- **Ruff** for linting
- **MyPy** for type checking
- **isort** for import sorting

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit:

1. **Code Formatting**: Black, isort
2. **Linting**: Ruff, bandit (security)
3. **Type Checking**: MyPy
4. **File Checks**: trailing whitespace, file endings, large files
5. **Security**: detect private keys, check for debug statements

To run hooks manually:
```bash
poetry run pre-commit run --all-files
```

To skip hooks temporarily (not recommended):
```bash
git commit -m "message" --no-verify
```

### Code Guidelines

1. **Type Hints**: Always use type hints for function arguments and returns
   ```python
   def process_video(video_id: str, language: str = "en") -> VideoMetadata:
       """Process a YouTube video and return metadata."""
       pass
   ```

2. **Docstrings**: Use Google-style docstrings
   ```python
   def extract_entities(text: str) -> List[Entity]:
       """Extract legal entities from text.
       
       Args:
           text: The input text to process
           
       Returns:
           List of extracted entities
           
       Raises:
           ProcessingError: If text processing fails
       """
       pass
   ```

3. **Error Handling**: Use specific exceptions
   ```python
   try:
       result = await process_content(content)
   except RateLimitError:
       await backoff_and_retry()
   except ProcessingError as e:
       logger.error(f"Processing failed: {e}")
       raise
   ```

4. **Async/Await**: Use async for I/O operations
   ```python
   async def fetch_video_data(video_id: str) -> dict:
       async with aiohttp.ClientSession() as session:
           return await youtube_client.get_video(session, video_id)
   ```

## Testing

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run specific test file
poetry run pytest tests/test_youtube_scraper.py

# Run tests matching pattern
poetry run pytest -k "test_transcription"
```

### Writing Tests

1. Place tests in the appropriate directory:
   - `tests/unit/` for unit tests
   - `tests/integration/` for integration tests
   - `tests/e2e/` for end-to-end tests

2. Follow the test naming convention:
   ```python
   def test_should_extract_video_metadata_successfully():
       pass
       
   def test_should_raise_error_when_video_not_found():
       pass
   ```

3. Use fixtures for common test data:
   ```python
   @pytest.fixture
   def sample_video_data():
       return {"id": "abc123", "title": "Legal Analysis"}
   ```

## Submitting Changes

### Pull Request Process

1. Update your branch with latest upstream changes:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. Push your branch:
   ```bash
   git push origin feature/your-feature-name
   ```

3. Create a Pull Request on GitHub with:
   - Clear title following commit message format
   - Description of changes
   - Reference to related issues
   - Screenshots for UI changes
   - Test results

4. Ensure all checks pass:
   - CI/CD pipeline
   - Code coverage maintained or improved
   - No merge conflicts

### PR Review Process

- At least one maintainer review required
- Address all feedback comments
- Keep PR focused and reasonably sized
- Update documentation if needed

## Need Help?

- Check existing issues and discussions
- Join our Discord server (link in README)
- Email the maintainers at support@law411.com

Thank you for contributing to lit_law411-agent!