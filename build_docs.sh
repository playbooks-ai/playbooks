#!/bin/bash

# Exit on error
set -e

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Define paths
DOCS_DIR="$SCRIPT_DIR/docs"
WEBSITE_DIR="$SCRIPT_DIR/../website"
WEBSITE_DOCS_DIR="$WEBSITE_DIR/public/docs"

# Ensure the website docs directory exists
mkdir -p "$WEBSITE_DOCS_DIR"

# Build the documentation
cd "$DOCS_DIR"
make html

# Copy the built documentation to the website
cp -r "$DOCS_DIR/build/html/"* "$WEBSITE_DOCS_DIR/"

echo "Documentation built and copied to $WEBSITE_DOCS_DIR" 