#!/bin/bash

# Exit on error
set -e

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Define paths
DOCS_DIR="$SCRIPT_DIR/docs"

# Build the documentation
cd "$DOCS_DIR"
make html

echo "Documentation built successfully in $DOCS_DIR/build/html"
echo "To view the documentation, open $DOCS_DIR/build/html/index.html in your browser"
echo "To deploy to GitHub Pages, push your changes to the main branch" 