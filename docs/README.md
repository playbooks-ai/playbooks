# Playbooks AI Documentation

This directory contains the source files for the Playbooks AI documentation.

## Setup

The documentation is built using [Sphinx](https://www.sphinx-doc.org/), a powerful documentation generator that converts reStructuredText files into HTML websites and other formats.

To set up the documentation environment, you need to install the required dependencies:

```bash
poetry install
```

This will install Sphinx and other required packages specified in the `pyproject.toml` file.

## Building the Documentation

To build the documentation locally, run:

```bash
cd docs
make html
```

This will generate HTML files in the `build/html` directory.

## Documentation Hosting

The documentation is hosted on GitHub Pages, providing a dedicated documentation site that is automatically updated when changes are pushed to the repository.

### GitHub Pages URL

Once deployed, the documentation will be available at:
```
https://playbooks-ai.github.io/playbooks/
```

You can also set up a custom domain for your documentation if desired.

## Automated Documentation Updates

The documentation is automatically updated through GitHub Actions workflows:

### GitHub Pages Deployment

When changes are pushed to the `main` branch that affect the documentation or source code, the `docs-gh-pages.yml` workflow will:
1. Build the documentation
2. Deploy it to GitHub Pages
3. Make it available at the GitHub Pages URL

### Manual Updates

You can also manually trigger the documentation update workflow from the GitHub Actions tab.

## Documentation Structure

- `source/`: Contains the source files for the documentation
  - `index.rst`: The main index file
  - `api/`: API reference documentation
  - Other content files

## Adding New Documentation

To add new documentation:

1. Create a new `.rst` or `.md` file in the appropriate directory
2. Add the file to the table of contents in `index.rst` or another parent file
3. Build the documentation to see the changes

## Updating API Documentation

The API documentation is automatically generated from docstrings in the Python code. To update the API documentation:

1. Ensure your Python code has proper docstrings
2. Rebuild the documentation

## Viewing the Documentation

After building locally, you can view the documentation by opening `build/html/index.html` in your browser.

When deployed, the documentation will be available at the GitHub Pages URL. 