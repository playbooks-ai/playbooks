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

To build the documentation, run:

```bash
cd docs
make html
```

This will generate HTML files in the `build/html` directory.

## Building and Copying to Website

To build the documentation and copy it to the website's public directory, run:

```bash
./build_docs.sh
```

This script will:
1. Build the documentation using Sphinx
2. Create the `public/docs` directory in the website project if it doesn't exist
3. Copy the built documentation to the website's `public/docs` directory

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

After building, you can view the documentation by opening `build/html/index.html` in your browser.

When deployed to the website, the documentation will be available at `/docs/index.html`. 