#!/usr/bin/env bash

echo "Setting up Git hooks..."
cd "$(dirname "$0")"
cd ..

# Create symlinks
ln -sf ../../.githooks/pre-commit .git/hooks/pre-commit
ln -sf ../../.githooks/pre-push .git/hooks/pre-push

chmod +x .git/hooks/*
echo "Git hooks installed successfully!"
