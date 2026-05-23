# Bot-Integrador: Action Items & Issue Tracker

## Issue Registry

### [CRITICAL-001] PosteData Class Duplication

| Attribute | Value |
|-----------|-------|
| **Severity** | CRITICAL |
| **Status** | OPEN |
| **Assignee** | _TBD_ |
| **Effort** | 2 hours |
| **Sprint** | Current |

**Description**:
Two incompatible PosteData definitions:
- `src/models/schemas.py`: `codigo`, `estruturas_mt`, `estruturas_bt`, `alimentador`, `coordenadas`
- `src/exporters/parser.py`: `code`, `lat`, `lng`, `alimentadores`, `cabos_mt`, `cabos_bt`

**Root Cause**: Incomplete refactoring during parser consolidation

**Impact**:
- Type mismatches when converting between formats
- Silent data loss during transformations
- Difficult to trace bugs

**Solution**:
1. Keep `src/models/schemas.py` as canonical
2. Update `src/exporters/parser.py` to use `models.PosteData`
3. Add conversion method: `ExportPosteData.to_model() -> models.PosteData`
4. Update all imports

**Acceptance Criteria**:
- [ ] Only one PosteData class definition in codebase
- [ ] All tests pass
- [ ] No type errors in conversion
- [ ] Old class removed

**Related Issues**: CRITICAL-002, CRITICAL-003

---

### [CRITICAL-002] Coordenadas Class Duplication

| Attribute | Value |
|-----------|-------|
| **Severity** | CRITICAL |
| **Status** | OPEN |
| **Assignee** | _TBD_ |
| **Effort** | 1 hour |
| **Sprint** | Current |

**Description**:
Two incompatible Coordenadas definitions:
- `src/models/schemas.py`: Dataclass with properties
- `src/api/main.py`: Pydantic BaseModel

**Root Cause**: API module created local models instead of importing

**Impact**:
- Impedance mismatch between API and internal models
- Difficult to keep in sync
- Type conversion issues

**Solution**:
1. Convert `models.Coordenadas` to Pydantic BaseModel (if not already)
2. Remove definition from `api/main.py`
3. Import from `models.schemas`

**Acceptance Criteria**:
- [ ] Only one Coordenadas class definition
- [ ] API uses models.Coordenadas
- [ ] All tests pass
- [ ] Old definition removed

**Related Issues**: CRITICAL-001

---

### [CRITICAL-003] Parser Logic Duplication

| Attribute | Value |
|-----------|-------|
| **Severity** | CRITICAL |
| **Status** | OPEN |
| **Assignee** | _TBD_ |
| **Effort** | 2 hours |
| **Sprint** | Current |

**Description**:
Two separate parser implementations for same input:
- `src/services/parser.py` (284 lines): ResponseParser class
- `src/exporters/parser.py` (107 lines): Local parser with PosteData

**Root Cause**: Copy-paste development, lack of refactoring

**Impact**:
- Parsing bugs must be fixed in multiple places
- Different behavior between code paths
- Maintenance nightmare
- Security issues in one are missed in other

**Solution**:
1. Consolidate regex patterns into `src/services/parser.py`
2. Remove duplicate parsing logic from `src/exporters/parser.py`
3. Keep only export-specific formatting in exporters
4. Add unit tests for parser consistency

**Acceptance Criteria**:
- [ ] All parsing logic in one place
- [ ] Export-specific formatting separated
- [ ] Parser behavior identical
- [ ] All tests pass
- [ ] Code coverage maintained

**Related Issues**: CRITICAL-001, HIGH-001

---

### [HIGH-001] Orphan Backup Files

| Attribute | Value |
|-----------|-------|
| **Severity** | HIGH |
| **Status** | READY |
| **Assignee** | _Anyone_ |
| **Effort** | 30 minutes |
| **Sprint** | Current |

**Description**:
17 backup files cluttering repository:
```
src/bot/handlers/admin.py.bak
src/bot/handlers/export.py.bak
src/bot/handlers/query.py.bak_code
src/bot/handlers/query.py.old
src/dispatcher/queue.py.old
src/exporters/__init__.py.bak
src/exporters/__init__.py.bak_osrm
src/exporters/gpx_builder.py.bak
src/exporters/gpx_builder.py.bak_osrm
src/exporters/kml_builder.py.bak
src/exporters/kml_builder.py.bak_osrm
src/services/route_models.py.bak
src/services/route_models.py.bak2
src/services/route_optimizer.py.bak
src/services/route_optimizer.py.bak3
src/services/route_optimizer.py.old
src/userbot/worker.py.old
```

**Solution**:
```bash
find src -type f \( -name "*.bak*" -o -name "*.old" \) -delete
git add -A && git commit -m "chore: remove backup files"
```

**Verification**:
```bash
grep -r "\.bak\|\.old" src/ --include="*.py"  # Should output nothing
```

**Acceptance Criteria**:
- [ ] All backup files deleted
- [ ] No import errors
- [ ] Tests pass
- [ ] Git history preserved

---

### [HIGH-002] Broad Exception Handlers Missing Logging

| Attribute | Value |
|-----------|-------|
| **Severity** | HIGH |
| **Status** | OPEN |
| **Assignee** | _TBD_ |
| **Effort** | 1 hour |
| **Sprint** | Current |

**Description**:
Bare `except Exception:` clauses with `pass` cause silent failures:
- `src/bot/handlers/export.py:132` - CSV download failure
- `src/bot/handlers/export.py:193` - KML download failure
- `src/bot/handlers/query.py:125` - Query handler
- `src/bot/handlers/start.py:77` - Startup
- `src/bot/handlers/start.py:85` - Startup

**Impact**:
- No visibility into failures
- Difficult to debug
- Hidden bugs go unnoticed
- Poor user experience (no error feedback)

**Solution**:
Replace pattern:
```python
# ❌ Before
try:
    await some_operation()
except Exception:
    pass

# ✓ After
try:
    await some_operation()
except SpecificError as e:
    logger.warning("Specific error occurred", context=data)
except Exception as e:
    logger.exception("Unexpected error", context=data)
    # Optionally notify user
```

**Files to Fix**:
| File | Lines | Type |
|------|-------|------|
| export.py | 132, 193 | CSV/KML download |
| query.py | 125 | Query handling |
| start.py | 77, 85 | Initialization |

**Acceptance Criteria**:
- [ ] All bare excepts replaced with specific types
- [ ] Logging added to all exception paths
- [ ] User feedback provided for errors
- [ ] Tests verify error handling

---

### [HIGH-003] HTTP Calls Without Timeout

| Attribute | Value |
|-----------|-------|
| **Severity** | HIGH |
| **Status** | OPEN |
| **Assignee** | _TBD_ |
| **Effort** | 1 hour |
| **Sprint** | Current |

**Description**:
16 async operations lack timeout protection:
- OSRM route requests
- UserBot queries
- Database operations
- HTTP client calls

**Impact**:
- Service can hang indefinitely
- Resource exhaustion
- Connection pool blocked
- DoS vulnerability

**Solution**:
Add `asyncio.timeout()` wrapper:
```python
async def query_with_timeout(code: str, timeout=30):
    try:
        async with asyncio.timeout(timeout):
            return await userbot.query_poste(code)
    except asyncio.TimeoutError:
        logger.error("Query timeout", code=code, timeout=timeout)
        raise
```

**Recommended Timeouts**:
- External APIs (OSRM): 60 seconds
- UserBot queries: 45 seconds
- Database operations: 30 seconds
- HTTP requests: 30 seconds

**Acceptance Criteria**:
- [ ] All async operations have timeout
- [ ] Timeout errors logged
- [ ] User feedback on timeout
- [ ] Tests verify timeout behavior

---

### [HIGH-004] Unused Imports in __init__.py

| Attribute | Value |
|-----------|-------|
| **Severity** | HIGH (Code Clarity) |
| **Status** | OPEN |
| **Assignee** | _TBD_ |
| **Effort** | 1 hour |
| **Sprint** | Next |

**Description**:
40 imports in `__init__.py` files never used locally:
- `src/database/__init__.py`: 10+ unused
- `src/bot/__init__.py`: 4+ unused
- `src/models/__init__.py`: 7+ unused

**Solution**:
Add explicit `__all__` declarations:
```python
from .models import PosteData, InstalacaoData, Coordenadas

__all__ = [
    'PosteData',
    'InstalacaoData', 
    'Coordenadas',
]
# Remove imports not in __all__ or move to separate section
```

**Acceptance Criteria**:
- [ ] `__all__` defined in each `__init__.py`
- [ ] Only intentional exports listed
- [ ] No unused imports
- [ ] Tests verify imports work

---

### [MEDIUM-001] Function Name Conflicts

| Attribute | Value |
|-----------|-------|
| **Severity** | MEDIUM |
| **Status** | OPEN |
| **Assignee** | _TBD_ |
| **Effort** | 30 minutes |
| **Sprint** | Next |

**Description**:
Same function name used for different purposes:
- `cb_kml_download()` in keyboards (creates callback string) vs handlers (processes callback)
- `get_session()` in database (DB session) vs userbot (Telegram session)

**Solution**:
Rename keyboard function for clarity:
```python
# OLD: src/bot/keyboards/export.py
def cb_kml_download(batch_id: str) -> str:

# NEW: src/bot/keyboards/export.py
def kml_download_callback_data(batch_id: str) -> str:

# Update references
# OLD: kb.button(..., callback_data=cb_kml_download(batch_id))
# NEW: kb.button(..., callback_data=kml_download_callback_data(batch_id))
```

**Acceptance Criteria**:
- [ ] Keyboard function renamed
- [ ] All references updated
- [ ] Tests pass
- [ ] Code review approved

---

### [MEDIUM-002] Large Monolithic Files

| Attribute | Value |
|-----------|-------|
| **Severity** | MEDIUM |
| **Status** | OPEN |
| **Assignee** | _TBD_ |
| **Effort** | 2 hours |
| **Sprint** | Next |

**Description**:
`src/exporters/__init__.py` (196 lines) mixes concerns:
- Batch orchestration logic
- Builder imports and re-exports
- Optimization statistics

**Solution** (Optional, low priority):
Separate into:
- `src/exporters/orchestrator.py` - batch processing
- `src/exporters/__init__.py` - clean re-exports

**Acceptance Criteria**:
- [ ] Orchestration logic separated
- [ ] Tests remain green
- [ ] Code coverage maintained
- [ ] Imports still work

---

### [LOW-001] Missing Type Hints

| Attribute | Value |
|-----------|-------|
| **Severity** | LOW |
| **Status** | OPEN |
| **Assignee** | _TBD_ |
| **Effort** | 1 hour |
| **Sprint** | Next |

**Description**:
Parser and adapter functions lack return type hints

**Solution**:
Add `-> ReturnType` to:
- `parse_poste_response() -> PosteData`
- `parse_instalacao_response() -> InstalacaoData`
- `postes_to_routepoints() -> list[RoutePoint]`

**Acceptance Criteria**:
- [ ] Return types added
- [ ] mypy passes
- [ ] Tests pass

---

## Priority Matrix

```
              LOW EFFORT    HIGH EFFORT
HIGH IMPACT    ⭐⭐⭐         ⭐⭐
              Clean up     Model
              backup       consolidation
              files

LOW IMPACT    ⭐           ⭐
             Type hints    Refactor
             Docs         large files
```

### Immediate (This Sprint)
1. HIGH-001: Delete backup files ⭐⭐⭐
2. CRITICAL-001: PosteData consolidation ⭐⭐
3. CRITICAL-002: Coordenadas consolidation ⭐⭐
4. CRITICAL-003: Parser consolidation ⭐⭐
5. HIGH-002: Add error logging ⭐⭐⭐
6. HIGH-003: Add HTTP timeouts ⭐⭐⭐

### Next Sprint
7. HIGH-004: Clean imports ⭐⭐
8. MEDIUM-001: Fix naming conflicts ⭐⭐⭐
9. MEDIUM-002: Refactor large files ⭐ (optional)
10. LOW-001: Add type hints ⭐⭐⭐

---

## Completion Checklist

### Pre-Implementation
- [ ] Code analysis reviewed
- [ ] Issues prioritized
- [ ] Team agrees on fixes
- [ ] Testing strategy defined

### Implementation Phase 1: Cleanup
- [ ] Delete 17 backup files
- [ ] Verify no errors
- [ ] Run tests
- [ ] Commit to git

### Implementation Phase 2: Critical Fixes
- [ ] Consolidate PosteData
- [ ] Consolidate Coordenadas
- [ ] Consolidate parser logic
- [ ] Update all imports
- [ ] Full test suite passes
- [ ] Code review complete
- [ ] Merge to main

### Implementation Phase 3: Robustness
- [ ] Add error logging
- [ ] Add HTTP timeouts
- [ ] Test failure paths
- [ ] Monitor in staging

### Implementation Phase 4: Cleanup (Next Sprint)
- [ ] Remove unused imports
- [ ] Rename functions
- [ ] Add type hints
- [ ] Update documentation

### Post-Implementation
- [ ] Performance monitoring
- [ ] Error rate tracking
- [ ] User feedback collection
- [ ] Retrospective meeting

---

## Metrics to Track

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| File count | 70 (53 + 17 orphans) | 53 | 53 |
| Critical issues | 3 | 0 | 0 |
| Duplicated classes | 2 | 0 | 0 |
| Exception handlers w/ logging | 0% | 100% | 100% |
| HTTP ops with timeout | 0% | 100% | 100% |
| Code coverage | TBD | Maintain | 85%+ |

---

**Last Updated**: May 22, 2026  
**Next Review**: After Phase 1 completion  
**Owner**: _TBD_
