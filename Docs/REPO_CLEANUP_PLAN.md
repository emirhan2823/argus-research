# ARGUS Repository Cleanup Plan

**One-Time Cleanup Before Phase 20**

| Field | Value |
|-------|-------|
| Date | 2026-02-07 |
| Status | PENDING |
| Owner | Lead Platform Engineer |

---

## 1. What Must Be Removed

### 1.1 Patch Leftovers (.rej files)

These indicate failed patches and MUST be deleted:

```bash
# Find all .rej files
find . -name "*.rej" -type f

# Delete them
find . -name "*.rej" -type f -delete
```

**Known locations:**
- `Scripts/paper_daemon.py.rej`
- `Scripts/phase19_dashboard.py.rej`
- `Scripts/phase19_readers.py.rej`
- `Scripts/phase19_supervisor.py.rej`
- `Scripts/phase19ctl.sh.rej`

### 1.2 Python Cache

```bash
# Find pycache directories
find . -type d -name "__pycache__" | wc -l

# Delete all pycache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Delete .pyc files
find . -name "*.pyc" -delete
```

### 1.3 Merge Leftovers

```bash
# Find .orig files
find . -name "*.orig" -type f

# Delete them
find . -name "*.orig" -type f -delete
```

### 1.4 Build Logs (if not needed)

```bash
# These are large and not useful long-term
rm -f build_log_*.txt
rm -f build_output*.txt
rm -f phase*_daemon.log
```

---

## 2. What Must Be Untracked

### 2.1 Check Currently Tracked Artifacts

```bash
# Check for tracked CSVs
git ls-files "*.csv"

# Check for tracked logs
git ls-files "*.log"

# Check for tracked runs
git ls-files "runs/*"
```

### 2.2 Untrack If Found

```bash
# Untrack CSVs (keep file, remove from git)
git rm --cached "*.csv" 2>/dev/null || true

# Untrack large artifacts
git rm --cached runs/ 2>/dev/null || true
git rm --cached logs/ 2>/dev/null || true
```

---

## 3. What Must Be Archived

### 3.1 Old Run Directories

Move runs older than 30 days to archive:

```bash
# Create archive directory (outside repo)
mkdir -p ~/argus_archives/runs_$(date +%Y%m%d)

# Move old runs (keeping last 30 days)
find runs/ -maxdepth 1 -type d -mtime +30 -name "2026*" \
    -exec mv {} ~/argus_archives/runs_$(date +%Y%m%d)/ \;
```

### 3.2 Research Archive

The `research_archive/` directory (2748 files) should be evaluated:

```bash
# Check size
du -sh research_archive/

# If not needed for Phase 20, archive it
tar -czvf ~/argus_archives/research_archive_$(date +%Y%m%d).tar.gz research_archive/
rm -rf research_archive/
```

### 3.3 Legacy Swift/Xcode Builds

```bash
# If not actively developing iOS
rm -rf .build-xcode/
rm -rf build/
rm -rf DerivedData/
rm -f ArgusRunner.zip
rm -f ArgusRunnerCLI2
rm -f ArgusRunnerBinary
```

---

## 4. What Must Be Regenerated

After cleanup, these should be regenerated:

| Item | Command | When |
|------|---------|------|
| Python cache | Happens automatically on import | First run |
| Test fixtures | `pytest --fixtures` | If tests fail |
| Data cache | `python3 -c "from argus_py.data import ..."` | First backtest |

---

## 5. One-Time Cleanup Commands

Run these IN ORDER:

```bash
#!/bin/bash
# ARGUS One-Time Cleanup Script
# Run from repo root

set -e

echo "=== ARGUS Cleanup Starting ==="
echo "Date: $(date)"
echo ""

# 1. Remove .rej files
echo "1. Removing .rej files..."
find . -name "*.rej" -type f -delete
echo "   Done"

# 2. Remove .orig files
echo "2. Removing .orig files..."
find . -name "*.orig" -type f -delete
echo "   Done"

# 3. Remove __pycache__
echo "3. Removing __pycache__ directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "   Done"

# 4. Remove .pyc files
echo "4. Removing .pyc files..."
find . -name "*.pyc" -delete 2>/dev/null || true
echo "   Done"

# 5. Remove build logs (optional, uncomment if desired)
# echo "5. Removing build logs..."
# rm -f build_log_*.txt build_output*.txt
# echo "   Done"

# 6. Verify cleanup
echo ""
echo "=== Verification ==="
echo "Remaining .rej files: $(find . -name '*.rej' | wc -l | tr -d ' ')"
echo "Remaining .orig files: $(find . -name '*.orig' | wc -l | tr -d ' ')"
echo "Remaining __pycache__: $(find . -type d -name '__pycache__' | wc -l | tr -d ' ')"

# 7. Run sanity check
echo ""
echo "=== Running Sanity Check ==="
./Scripts/repo_sanity_check.sh

echo ""
echo "=== Cleanup Complete ==="
```

Save as `Scripts/cleanup_once.sh` and run:

```bash
chmod +x Scripts/cleanup_once.sh
./Scripts/cleanup_once.sh
```

---

## 6. Post-Cleanup Commit

After cleanup:

```bash
# Stage .gitignore changes
git add .gitignore

# Stage removed files (if untracked)
git add -A

# Commit cleanup
git commit -m "chore: repo cleanup for Phase 20

- Remove .rej files (5)
- Remove __pycache__ directories
- Update .gitignore with comprehensive rules
- Add repo_sanity_check.sh
- Add REPO_GOVERNANCE.md
- Add REPO_CLEANUP_PLAN.md

Ready for multi-agent development."
```

---

## 7. Verification

After cleanup, this MUST pass:

```bash
./Scripts/repo_sanity_check.sh
```

**Expected output:**
```
==============================================
ARGUS Repo Sanity Check
==============================================
✅ No .rej files found
✅ No .orig files found
✅ No __pycache__ directories found
✅ No .pyc files found
✅ No large tracked files found
✅ No forbidden tracked CSV files
✅ No tracked runtime directories
✅ No obvious secrets in tracked files
✅ No .env files found
✅ Working tree is clean
==============================================
SUMMARY
==============================================
✅ ALL CHECKS PASSED
Repo is ready for Phase 20
```

---

## 8. Ongoing Maintenance

After Phase 20 starts:

| Task | Frequency | Command |
|------|-----------|---------|
| Sanity check | Before each commit | `./Scripts/repo_sanity_check.sh` |
| Clean pycache | Weekly | `find . -type d -name '__pycache__' -exec rm -rf {} +` |
| Archive old runs | Monthly | Move >30 day runs to archive |
| Review .gitignore | Per phase | Update if new patterns emerge |

---

**Document Status:** PENDING EXECUTION  
**Next Step:** Run cleanup commands
