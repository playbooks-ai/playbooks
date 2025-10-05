# Contributing to Playbooks

Thank you for being interested in contributing to Playbooks!

## General guidelines

Here are some things to keep in mind for all types of contributions:

- Follow the ["fork and pull request"](https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project) workflow.
- Fill out the checked-in pull request template when opening pull requests. Note related issues and tag relevant maintainers.
- Ensure your PR passes formatting, linting, and testing checks before requesting a review.
  - If you would like comments or feedback, please tag a maintainer.
- Backwards compatibility is key. Your changes must not be breaking, except in case of critical bug and security fixes.
- Look for duplicate PRs or issues that have already been opened before opening a new one.
- Keep scope as isolated as possible.

### Bugfixes

For bug fixes, please open up an issue before proposing a fix to ensure the proposal properly addresses the underlying problem. In general, bug fixes should all have an accompanying unit test that fails before the fix.

### New features

For new features, please open an issue or start a discussion where the maintainers will help with scoping out the necessary changes.

## Development Setup

### Prerequisites

- Python 3.12 or higher
- [Poetry](https://python-poetry.org/) for dependency management

### Initial Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/playbooks.git
   cd playbooks
   ```

2. Install dependencies using Poetry:
   ```bash
   poetry install
   ```

3. Activate the virtual environment:
   ```bash
   poetry shell
   ```

## Testing

Playbooks uses pytest for testing. We have both unit tests and integration tests.

### Running Tests

Run all tests:
```bash
poetry run pytest
```

Run only unit tests (faster):
```bash
poetry run pytest -m "not integration"
```

Run with coverage:
```bash
poetry run pytest --cov=src/playbooks --cov-report=html
```

### LLM Caching for Tests

**Important:** Many tests use real calls to an LLM. These calls are cached in the `.llm_cache_test` folder and committed to the repository. This ensures that when tests run in GitHub workflows, all LLM requests are served from the cache, so that running tests repeatedly doesn't incur cost every time.

**When contributing:**
- Run tests and commit any updates to `.llm_cache_test/` along with your changes.
- For significant changes (e.g., to the compiler or execution prompts), delete the `.llm_cache_test` folder and run all tests. This will build a fresh cache, which should be committed.
- This prevents the cache from growing in size unnecessarily.

Seeding new cache costs $2-3 of Claude usage. If you are unable or unwilling to spend this money, please add a note indicating that in your PR so the maintainers can seed the cache.

### Linting and Formatting

Playbooks uses [Ruff](https://github.com/astral-sh/ruff) for linting and [Black](https://github.com/psf/black) for formatting.

Run linting:
```bash
poetry run ruff check .
```

Auto-fix linting issues:
```bash
poetry run ruff check --fix .
```

Run formatting:
```bash
poetry run black .
```

Check formatting without changes:
```bash
poetry run black --check .
```

## Contribute Documentation

Documentation is a vital part of Playbooks. The main documentation is hosted at [https://playbooks-ai.github.io/playbooks-docs/](https://playbooks-ai.github.io/playbooks-docs/) in a separate repository.

We welcome:

- Updates to existing documentation
- New examples and tutorials
- Improvements to code documentation and docstrings
- Updates to this CONTRIBUTING.md or other repository documentation

### Code Documentation

Good docstrings are essential for maintainability and for generating API documentation. We generally follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for docstrings.

Here is an example of a well-documented function:

```python
def my_function(arg1: int, arg2: str) -> float:
    """This is a short description of the function. (It should be a single sentence.)

    This is a longer description of the function. It should explain what
    the function does, what the arguments are, and what the return value is.
    It should wrap at 88 characters.

    Examples:
        This is a section for examples of how to use the function.

        ```python
        my_function(1, "hello")
        ```

    Args:
        arg1: This is a description of arg1. We do not need to specify the type since
            it is already specified in the function signature.
        arg2: This is a description of arg2.

    Returns:
        This is a description of the return value.
    """
    return 3.14
```

## Pull Request Process

1. **Fork and branch**: Create a new branch from `master` for your changes.
2. **Make changes**: Implement your bug fix or feature.
3. **Test**: Run the test suite and ensure all tests pass. Add new tests for new features.
4. **Lint and format**: Run `ruff` and `black` to ensure code quality.
5. **Commit**: Make clear, concise commits with descriptive messages.
6. **Update cache**: If you've made changes that affect LLM calls, ensure `.llm_cache_test/` is updated.
7. **Push**: Push your changes to your fork.
8. **Pull request**: Open a PR against the `master` branch with a clear description of your changes.

## Code Style

- Follow PEP 8 guidelines
- Use type hints for function arguments and return values
- Write clear, self-documenting code with descriptive variable names
- Add comments for complex logic
- Keep functions focused and modular

## Questions?

If you have questions or need help:
- Open an issue on GitHub
- Check the [documentation](https://playbooks-ai.github.io/playbooks-docs/)
- Look at existing examples in the `examples/` directory

Thank you for contributing to Playbooks! 🎉