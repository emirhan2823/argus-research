#!/bin/bash
# =============================================================================
# ARGUS Repo Sanity Check
# =============================================================================
# This script MUST pass before any Phase 20 work begins.
# Run: ./Scripts/repo_sanity_check.sh
# Exit: 0 = clean, non-zero = violations found
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

VIOLATIONS=0
WARNINGS=0

# Change to repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "=============================================="
echo "ARGUS Repo Sanity Check"
echo "=============================================="
echo "Repo: $REPO_ROOT"
echo "Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# 1. Check for .rej files (patch leftovers)
# -----------------------------------------------------------------------------
echo "🔍 Checking for .rej files (patch leftovers)..."
REJ_FILES=$(find . -name "*.rej" -type f 2>/dev/null | grep -v node_modules || true)
if [ -n "$REJ_FILES" ]; then
    echo -e "${RED}❌ VIOLATION: Found .rej files (incomplete patches)${NC}"
    echo "$REJ_FILES" | head -20
    ((VIOLATIONS++))
else
    echo -e "${GREEN}✅ No .rej files found${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# 2. Check for .orig files (merge leftovers)
# -----------------------------------------------------------------------------
echo "🔍 Checking for .orig files (merge leftovers)..."
ORIG_FILES=$(find . -name "*.orig" -type f 2>/dev/null | grep -v node_modules || true)
if [ -n "$ORIG_FILES" ]; then
    echo -e "${RED}❌ VIOLATION: Found .orig files (merge leftovers)${NC}"
    echo "$ORIG_FILES" | head -20
    ((VIOLATIONS++))
else
    echo -e "${GREEN}✅ No .orig files found${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# 3. Check for __pycache__ directories
# -----------------------------------------------------------------------------
echo "🔍 Checking for __pycache__ directories..."
PYCACHE_DIRS=$(find . -type d -name "__pycache__" 2>/dev/null | grep -v node_modules || true)
if [ -n "$PYCACHE_DIRS" ]; then
    PYCACHE_COUNT=$(echo "$PYCACHE_DIRS" | wc -l | tr -d ' ')
    echo -e "${YELLOW}⚠️  WARNING: Found $PYCACHE_COUNT __pycache__ directories${NC}"
    echo "$PYCACHE_DIRS" | head -10
    echo "   Run: find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null"
    ((WARNINGS++))
else
    echo -e "${GREEN}✅ No __pycache__ directories found${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# 4. Check for .pyc files
# -----------------------------------------------------------------------------
echo "🔍 Checking for .pyc files..."
PYC_FILES=$(find . -name "*.pyc" -type f 2>/dev/null | grep -v node_modules || true)
if [ -n "$PYC_FILES" ]; then
    PYC_COUNT=$(echo "$PYC_FILES" | wc -l | tr -d ' ')
    echo -e "${YELLOW}⚠️  WARNING: Found $PYC_COUNT .pyc files${NC}"
    echo "   Run: find . -name '*.pyc' -delete"
    ((WARNINGS++))
else
    echo -e "${GREEN}✅ No .pyc files found${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# 5. Check for tracked large data files
# -----------------------------------------------------------------------------
echo "🔍 Checking for large tracked files (>10MB)..."
LARGE_FILES=$(git ls-files | while read f; do
    if [ -f "$f" ]; then
        size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
        if [ "$size" -gt 10485760 ]; then
            echo "$f ($(echo "scale=2; $size/1048576" | bc)MB)"
        fi
    fi
done)
if [ -n "$LARGE_FILES" ]; then
    echo -e "${RED}❌ VIOLATION: Found large tracked files (>10MB)${NC}"
    echo "$LARGE_FILES"
    ((VIOLATIONS++))
else
    echo -e "${GREEN}✅ No large tracked files found${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# 6. Check for tracked CSV files (outside whitelist)
# -----------------------------------------------------------------------------
echo "🔍 Checking for tracked CSV files..."
TRACKED_CSVS=$(git ls-files "*.csv" 2>/dev/null | grep -v "tests/fixtures" | grep -v "Docs/benchmarks" || true)
if [ -n "$TRACKED_CSVS" ]; then
    echo -e "${RED}❌ VIOLATION: Found tracked CSV files (should be ignored)${NC}"
    echo "$TRACKED_CSVS"
    ((VIOLATIONS++))
else
    echo -e "${GREEN}✅ No forbidden tracked CSV files${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# 7. Check for runs/ or logs/ tracked
# -----------------------------------------------------------------------------
echo "🔍 Checking for tracked runtime directories..."
TRACKED_RUNS=$(git ls-files "runs/*" 2>/dev/null || true)
TRACKED_LOGS=$(git ls-files "logs/*" 2>/dev/null || true)
if [ -n "$TRACKED_RUNS" ] || [ -n "$TRACKED_LOGS" ]; then
    echo -e "${RED}❌ VIOLATION: Found tracked runtime artifacts${NC}"
    echo "$TRACKED_RUNS" | head -5
    echo "$TRACKED_LOGS" | head -5
    ((VIOLATIONS++))
else
    echo -e "${GREEN}✅ No tracked runtime directories${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# 8. Check for potential secrets
# -----------------------------------------------------------------------------
echo "🔍 Checking for potential secrets..."
SECRET_PATTERNS="api_key|apikey|api-key|secret|password|token|credential"
# Check tracked files only
SECRET_FILES=$(git grep -l -i -E "$SECRET_PATTERNS" -- "*.py" "*.sh" "*.yaml" "*.yml" "*.json" 2>/dev/null | grep -v "test" | grep -v ".gitignore" | head -10 || true)
if [ -n "$SECRET_FILES" ]; then
    echo -e "${YELLOW}⚠️  WARNING: Potential secrets detected in tracked files${NC}"
    echo "$SECRET_FILES"
    echo "   Review these files for hardcoded secrets"
    ((WARNINGS++))
else
    echo -e "${GREEN}✅ No obvious secrets in tracked files${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# 9. Check for .env files
# -----------------------------------------------------------------------------
echo "🔍 Checking for .env files..."
ENV_FILES=$(find . -name ".env*" -type f 2>/dev/null | grep -v node_modules || true)
TRACKED_ENV=$(git ls-files ".env*" 2>/dev/null || true)
if [ -n "$TRACKED_ENV" ]; then
    echo -e "${RED}❌ VIOLATION: Found tracked .env files${NC}"
    echo "$TRACKED_ENV"
    ((VIOLATIONS++))
elif [ -n "$ENV_FILES" ]; then
    echo -e "${GREEN}✅ .env files exist but are not tracked (correct)${NC}"
else
    echo -e "${GREEN}✅ No .env files found${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# 10. Check git status
# -----------------------------------------------------------------------------
echo "🔍 Checking git status..."
DIRTY_FILES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [ "$DIRTY_FILES" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNING: Working tree has $DIRTY_FILES uncommitted changes${NC}"
    git status --short | head -20
    ((WARNINGS++))
else
    echo -e "${GREEN}✅ Working tree is clean${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# SUMMARY
# -----------------------------------------------------------------------------
echo "=============================================="
echo "SUMMARY"
echo "=============================================="
if [ $VIOLATIONS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    echo "Repo is ready for Phase 20"
    exit 0
elif [ $VIOLATIONS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  PASSED WITH $WARNINGS WARNING(S)${NC}"
    echo "Consider fixing warnings before proceeding"
    exit 0
else
    echo -e "${RED}❌ FAILED: $VIOLATIONS VIOLATION(S), $WARNINGS WARNING(S)${NC}"
    echo ""
    echo "Fix violations before proceeding:"
    echo "  1. Remove .rej files: find . -name '*.rej' -delete"
    echo "  2. Remove .orig files: find . -name '*.orig' -delete"
    echo "  3. Remove __pycache__: find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
    echo "  4. Untrack large files: git rm --cached <file>"
    echo "  5. Untrack CSVs: git rm --cached '*.csv'"
    exit 1
fi
