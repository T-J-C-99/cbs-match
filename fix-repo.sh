#!/bin/bash
# CBS Match Repository Fix Script
# Run from: cd /Users/thomascline/Desktop/cbs-match && bash fix-repo.sh

set -e

echo "=== 1) INSPECT CURRENT STATE ==="
echo "Remote:"
git remote -v
echo "Branch:"
git branch --show-current
echo "Toplevel:"
git rev-parse --show-toplevel
echo ""
echo "HEAD tree:"
git ls-tree --name-only HEAD
echo ""
echo "Status:"
git status --porcelain
echo ""
echo "Recent commits:"
git log --oneline -5

echo ""
echo "=== 2) FIX .gitignore ==="
cat > .gitignore <<'EOF'
# Dependencies
node_modules/
**/node_modules/

# Dev runtime files
.dev/
*.pid

# Build outputs
.next/
**/.next/
dist/
**/dist/
build/
**/build/
web/.next/
web/dist/
mobile/.expo/
mobile/ios/build/
mobile/android/app/build/
coverage/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
env/
*.pyc
.pytest_cache/
.mypy_cache/

# Database (dev)
*.db
*.sqlite
*.sqlite3

# Uploads
api/uploads/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# OS files
.DS_Store
Thumbs.db

# Logs
*.log
npm-debug.log*

# Test coverage
.coverage
htmlcov/

# TypeScript build cache
*.tsbuildinfo

# Env files
.env
.env.*
!.env.example

# Patches (artifacts)
*.patch
EOF
echo "Updated .gitignore"

echo ""
echo "=== 3) REMOVE TRACKED JUNK FROM INDEX ==="
echo "Checking for tracked node_modules..."
TRACKED_NM=$(git ls-files | grep -E '(^|/)node_modules/' || true)
if [ -n "$TRACKED_NM" ]; then
  echo "Found tracked node_modules, removing from index..."
  git rm -r --cached node_modules 2>/dev/null || true
  git rm -r --cached --ignore-unmatch web/node_modules 2>/dev/null || true
  git rm -r --cached --ignore-unmatch mobile/node_modules 2>/dev/null || true
  git rm -r --cached --ignore-unmatch packages/shared/node_modules 2>/dev/null || true
else
  echo "No tracked node_modules found."
fi

echo ""
echo "Checking for patch files..."
PATCH_FILES=$(git ls-files | grep -E '\.patch$' || true)
if [ -n "$PATCH_FILES" ]; then
  echo "Found patch files, removing from index..."
  echo "$PATCH_FILES" | xargs -r git rm --cached
else
  echo "No patch files tracked."
fi

echo ""
echo "Checking for large files (>50MB)..."
git ls-files | while read f; do
  if [ -f "$f" ]; then
    SIZE=$(stat -f%z "$f" 2>/dev/null || echo 0)
    if [ "$SIZE" -gt 52428800 ]; then
      echo "LARGE: $SIZE bytes - $f"
    fi
  fi
done | head -20

echo ""
echo "=== 4) CHECK IF SOURCE DIRS ARE IGNORED ==="
git check-ignore -v api web packages mobile || echo "Source dirs NOT ignored (good)"

echo ""
echo "=== 5) CHECK FOR NESTED .git DIRS ==="
find api web packages mobile -maxdepth 2 -name .git -print 2>/dev/null || true

echo ""
echo "=== 6) ADD SOURCE DIRECTORIES ==="
git add api web packages mobile .gitignore
echo "Staged content:"
git status

echo ""
echo "=== 7) VERIFY STAGED CONTENT ==="
echo "Checking for node_modules in staging..."
STAGED_NM=$(git diff --cached --name-only | grep node_modules || true)
if [ -n "$STAGED_NM" ]; then
  echo "ERROR: node_modules is staged! Aborting."
  exit 1
else
  echo "OK: No node_modules staged."
fi

echo ""
echo "Diff stat:"
git diff --cached --stat | tail -20

echo ""
echo "=== 8) COMMIT ==="
git commit -m "chore: add full repo content and enforce git hygiene"

echo ""
echo "=== 9) PUSH ==="
git push -u origin main

echo ""
echo "=== 10) VERIFICATION ==="
echo "HEAD tree:"
git ls-tree --name-only HEAD
echo ""
echo "Checking for tracked node_modules:"
FINAL_CHECK=$(git ls-files | grep node_modules || true)
if [ -z "$FINAL_CHECK" ]; then
  echo "SUCCESS: No node_modules tracked"
else
  echo "WARNING: Some node_modules still tracked:"
  echo "$FINAL_CHECK"
fi

echo ""
echo "=== COMPLETE ==="
echo "New HEAD: $(git rev-parse HEAD)"
echo "Branch: $(git branch --show-current)"