# Bot-Integrador: Quick Reference Guide

## 🔴 CRITICAL - Must Fix Immediately

### 1. Duplicate PosteData Classes
**Problem**: Two different PosteData classes with different fields  
**Where**: `src/models/schemas.py` vs `src/exporters/parser.py`  
**Fix**: Use `src/models/schemas.py` as canonical  
**Command**: Add method to parser: `def to_model(self) -> models.PosteData:`

### 2. Duplicate Coordenadas Classes
**Problem**: Dataclass in `schemas.py` vs Pydantic in `api/main.py`  
**Fix**: Consolidate into single Pydantic model in `schemas.py`  
**Command**: Update `src/api/main.py` to import from `schemas`

### 3. Parser Duplication
**Problem**: `services/parser.py` vs `exporters/parser.py` parsing same input  
**Fix**: Keep only `services/parser.py`, refactor `exporters/parser.py`  
**Command**: Consolidate regex patterns and parsing logic

---

## 🟡 HIGH PRIORITY - This Sprint

### Remove Orphan Files
```bash
find src -type f \( -name "*.bak*" -o -name "*.old" \) -delete
# Removes 17 backup files (~90 KB)
```

### Add Error Handling
**Files**: `export.py`, `query.py`, `start.py` (lines shown below)

| File | Lines | Fix |
|------|-------|-----|
| export.py | 132, 193 | Add logging to `except Exception:` |
| query.py | 125 | Add logging to `except Exception:` |
| start.py | 77, 85 | Add logging to `except Exception:` |

**Pattern**:
```python
# ❌ Remove silent catches
except Exception:
    pass

# ✓ Replace with
except Exception as e:
    logger.exception("Operation failed", context=locals())
```

### Add HTTP Timeouts
**Issue**: 16 async operations without timeout  
**Pattern**:
```python
# ✓ Use asyncio.timeout
async with asyncio.timeout(30):
    response = await some_async_operation()
```

---

## 🟢 MEDIUM PRIORITY - Next Sprint

### Clean Unused Imports
**Files**:
- `src/database/__init__.py` - Remove or add to `__all__`
- `src/bot/__init__.py` - Clean up exports
- `src/models/__init__.py` - Define clear API surface
- `src/services/__init__.py` - Only export used items

### Rename Conflicting Functions
| Old Name | New Name | Location |
|----------|----------|----------|
| `cb_kml_download(batch_id)` | `kml_download_callback_data(batch_id)` | keyboards/export.py |

### Configure Hardcoded URLs
**Files**: `maps_link.py` - Move URLs to `src/config.py`

---

## 🔵 LOW PRIORITY - Technical Debt

### Add Type Hints
- `src/services/parser.py` - Add return types
- `src/exporters/adapter.py` - Add return types

### Improve Documentation
- Add docstrings to regex patterns
- Document parser behavior
- Add config variable descriptions

---

## Testing Checklist

After each change:
```bash
# 1. Run tests
pytest tests/ -v

# 2. Type check (if installed)
mypy src/

# 3. Lint
pylint src/

# 4. Coverage
pytest tests/ --cov=src

# 5. Import check (after deletions)
python -c "import src; print('✓ All imports work')"
```

---

## File Change Summary

### Delete (17 files)
```
.bak, .old, .bak_code, .bak_osrm, .bak2, .bak3 files
```

### Modify (High Priority)
```
src/models/schemas.py           # Consolidate models
src/api/main.py                 # Use imported models
src/exporters/parser.py         # Use models, add converter
src/services/parser.py          # Consolidate logic
src/bot/handlers/export.py      # Add error handling
src/bot/handlers/query.py       # Add error handling
src/bot/handlers/start.py       # Add error handling
```

### Modify (Medium Priority)
```
src/database/__init__.py        # Clean exports
src/bot/__init__.py             # Clean exports
src/bot/keyboards/export.py     # Rename functions
src/exporters/maps_link.py      # Move to config
```

---

## Estimated Timeline

| Phase | Items | Time | Priority |
|-------|-------|------|----------|
| 1 | Delete backups | 30 min | NOW |
| 2 | Model consolidation | 4-6h | This Sprint |
| 3 | Error handling + timeouts | 3-4h | This Sprint |
| 4 | Code cleanup | 2-3h | Next Sprint |
| **Total** | | **~12-15h** | |

---

## Key Metrics

**Before**: 53 files + 17 orphans, 2 critical bugs, 12 high-priority issues  
**After**: 53 files, 0 critical bugs, 0 duplicated models, clean error handling

---

## Questions?

1. **Why fix PosteData duplication?**
   - Prevents type mismatches and silent bugs
   - Simplifies data flow
   - Easier maintenance

2. **Why remove backup files?**
   - Git already has history
   - Backup files are never used
   - Reduce code confusion

3. **Why add timeouts everywhere?**
   - Prevent service hangs
   - Better resource management
   - Improved observability

---

**Last Updated**: May 22, 2026  
**Status**: Analysis Complete, Ready for Implementation
