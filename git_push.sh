#!/bin/bash
# FreqtradePro Git Push Script
# Usage: ./git_push.sh "commit message"

GITHUB_USER="baterhiro"
GITHUB_TOKEN="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"
REPO="FreqtradePro"
REMOTE_URL="https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO}.git"

cd "$(dirname "$0")" || exit 1

# Set remote URL with token
git remote set-url origin "$REMOTE_URL"

# Commit message: use argument or default
MSG="${1:-FreqtradePro update $(date '+%Y-%m-%d %H:%M:%S')}"

# Add all changes
git add -A

# Commit
git commit -m "$MSG"

# Push
git push origin main

echo ""
echo "=== Push completed ==="
echo "Repo: https://github.com/${GITHUB_USER}/${REPO}"
