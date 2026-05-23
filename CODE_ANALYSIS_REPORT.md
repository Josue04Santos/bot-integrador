# Bot-Integrador: Comprehensive Code Analysis Report

**Date**: May 22, 2026  
**Scope**: `src/` directory (53 Python files)  
**Analysis Type**: Static code quality, duplication, bugs, dead code

---

## Executive Summary

| Category | Count | Status |
|----------|-------|--------|
| Total Python Files | 53 | ✓ Active |
| Orphan Backup Files | 17 | 🔴 To Remove |
| Critical Issues | 2 | 🔴 High Risk |
| High Priority Issues | 12 | 🟡 Must Fix |
| Medium Priority Issues | 8 | 🟢 Should Fix |
| Low Priority Issues | 5 | 🔵 Nice to Have |

---

## 🔴 CRITICAL ISSUES (Bugs that break code)

### 1. DUPLICATE MODEL DEFINITIONS - PosteData & Coordenadas

**Severity**: CRITICAL  
**Impact**: Type mismatches, data inconsistency, refactoring errors

#### Issue 1a: PosteData Class Defined Twice

| Location | Type | Usage | Fields |
|----------|------|-------|--------|
| [src/models/schemas.py](src/models/schemas.py#L62) | @dataclass | API responses, database | `codigo`, `estruturas_mt`, `estruturas_bt`, `alimentador`, `cabos`, `coordenadas`, `raw_response` |
| [src/exporters/parser.py](src/exporters/parser.py#L45) | @dataclass | Local parsing | `code`, `lat`, `lng`, `alimentadores`, `cabos_mt`, `cabos_bt`, `estruturas_mt`, `estruturas_bt` |

**Problem**:
- Different field names (`codigo` vs `code`, `lat` vs separate coordenadas)
- Different structure and semantics
- Incomplete refactoring - both are used in different parts of codebase
- Field mapping needed when converting between them

**Suggested Fix**:
```python
# 1. Use src/models/schemas.py as canonical
# 2. Refactor src/exporters/parser.py to create models.PosteData
# 3. Update all imports to use models.schemas

# Replace in src/exporters/parser.py:
@dataclass
class PosteData:
    """Temporary parsing object - converts to models.schemas.PosteData"""
    code: str
    lat: float | None = None
    lng: float | None = None
    # ... other fields ...
    
    def to_model(self) -> models.PosteData:
        """Convert internal parser format to canonical model."""
        return models.PosteData(
            codigo=self.code,
            estruturas_mt=self.estruturas_mt,
            estruturas_bt=self.estruturas_bt,
            alimentador=self.alimentadores[0] if self.alimentadores else None,
            cabos=self.cabos_mt + self.cabos_bt,
            coordenadas=models.Coordenadas(
                latitude=self.lat,
                longitude=self.lng
            ) if self.lat and self.lng else None
        )
```

**Risk if Changed**: Medium (requires comprehensive testing of data flow)  
**Risk if Unchanged**: High (causes silent bugs in data transformations)

---

#### Issue 1b: Coordenadas Class Defined Twice

| Location | Type | Purpose |
|----------|------|---------|
| [src/models/schemas.py](src/models/schemas.py#L28) | @dataclass | Internal data model with methods |
| [src/api/main.py](src/api/main.py#L32) | Pydantic BaseModel | API response schema |

**Problem**:
- Dataclass vs Pydantic BaseModel creates impedance mismatch
- API layer duplicates model definition instead of importing
- Difficult to keep in sync during refactoring

**Suggested Fix**:
```python
# Option A: Use Pydantic everywhere (recommended for APIs)
# In src/models/schemas.py:
from pydantic import BaseModel

class Coordenadas(BaseModel):
    latitude: float
    longitude: float
    
    @property
    def google_maps_url(self) -> str:
        return f"https://www.google.com.br/maps/place/{self.latitude},{self.longitude}"
    
    @property
    def dms(self) -> str:
        # ... DMS conversion logic

# Then in src/api/main.py:
from src.models.schemas import Coordenadas  # Import instead of redefine

# Option B: Keep dataclass, add conversion
# If dataclass is preferred, add to Coordenadas:
def to_pydantic(self) -> 'CoordenadasPydantic':
    return CoordenadasPydantic(
        latitude=self.latitude,
        longitude=self.longitude
    )
```

**Risk if Changed**: Low-Medium (clean, well-defined change)  
**Risk if Unchanged**: Medium (API inconsistencies during evolution)

---

### 2. PARSER DUPLICATION - Two Different Parsing Implementations

**Severity**: CRITICAL  
**Impact**: Maintenance burden, potential sync issues, conflicting logic

#### Issue Details

| File | Lines | Responsibility | Key Classes |
|------|-------|-----------------|--------------|
| [src/services/parser.py](src/services/parser.py) | 284 | Main response parsing | ResponseParser (1 class, 8 methods) |
| [src/exporters/parser.py](src/exporters/parser.py) | 107 | Export-specific parsing | PosteData, parse functions |

**Analysis**:

`services/parser.py` contains `ResponseParser` class that:
- Parses Telegram bot responses
- Extracts coordinates, estruturas, cables
- Returns typed models (PosteData, InstalacaoData)

`exporters/parser.py` contains:
- Alternative parsing implementation
- Local PosteData definition (see Issue 1a)
- Different regex patterns and logic

**Problem**:
- Same input (bot responses), two different interpretations
- Unclear which should be used when
- Changes to parsing logic must be synchronized
- Regex patterns not shared (DRY violation)

**Suggested Fix**:
```python
# 1. Consolidate into src/services/parser.py
# 2. Keep exporters/parser.py ONLY for export format conversion

# src/services/parser.py should have:
class ResponseParser:
    """Parse raw Telegram bot responses into typed models."""
    # Existing implementation

class ExportFormatter:
    """Convert typed models to export-specific formats."""
    @staticmethod
    def format_for_kml(poste: PosteData) -> dict:
        # Format for KML export
        
    @staticmethod
    def format_for_csv(poste: PosteData) -> dict:
        # Format for CSV export

# src/exporters/parser.py becomes:
from src.services.parser import ResponseParser, ExportFormatter
# Re-export for backward compatibility
__all__ = ['ResponseParser', 'ExportFormatter']
```

**Risk if Changed**: Medium-High (widespread impact on parsing pipeline)  
**Risk if Unchanged**: High (sync bugs, maintenance nightmare)

---

## 🟡 HIGH PRIORITY ISSUES (Code quality, must consolidate)

### 3. ORPHAN BACKUP FILES (17 files - ~90 KB dead code)

**Severity**: HIGH  
**Impact**: Code confusion, bloated repository, deployment issues

#### Files to Remove

```
src/bot/handlers/admin.py.bak                      (3.9 KB)
src/bot/handlers/export.py.bak                     (6.5 KB)
src/bot/handlers/query.py.bak_code                 (8.0 KB)
src/bot/handlers/query.py.old                      (8.1 KB)
src/dispatcher/queue.py.old                        (1.6 KB)
src/exporters/__init__.py.bak                      (4.6 KB)
src/exporters/__init__.py.bak_osrm                 (4.6 KB)
src/exporters/gpx_builder.py.bak                   (8.0 KB)
src/exporters/gpx_builder.py.bak_osrm              (2.6 KB)
src/exporters/kml_builder.py.bak                   (5.3 KB)
src/exporters/kml_builder.py.bak_osrm              (8.1 KB)
src/services/route_models.py.bak                   (1.6 KB)
src/services/route_models.py.bak2                  (1.6 KB)
src/services/route_optimizer.py.bak                (7.1 KB)
src/services/route_optimizer.py.bak3               (4.8 KB)
src/services/route_optimizer.py.old                (4.8 KB)
src/userbot/worker.py.old                          (6.9 KB)
```

**Suggested Fix**:
```bash
# Safe removal - these are not imported anywhere
find src -type f \( -name "*.bak*" -o -name "*.old" \) -exec rm {} \;

# Or individually:
rm -f src/bot/handlers/*.bak src/bot/handlers/*.old
rm -f src/dispatcher/*.old
rm -f src/exporters/*.bak src/exporters/*.bak_osrm
rm -f src/services/*.bak src/services/*.old
rm -f src/userbot/*.old
```

**Risk if Changed**: Very Low (these are backup files, not used)  
**Risk if Unchanged**: Low-Medium (code clutter, confusion)

**Verification Before Removal**:
```bash
# Ensure none are imported
grep -r "\.bak\|\.old" src/ --include="*.py"  # Should return nothing
```

---

### 4. BROAD EXCEPTION HANDLERS (Missing Error Context)

**Severity**: HIGH  
**Impact**: Silent failures, difficult debugging, hidden bugs

#### Issue Locations

| File | Line | Pattern | Risk |
|------|------|---------|------|
| [src/bot/handlers/export.py](src/bot/handlers/export.py#L132) | 132 | `except Exception:` without logging | Silent failure |
| [src/bot/handlers/export.py](src/bot/handlers/export.py#L193) | 193 | `except Exception:` without logging | Silent failure |
| [src/bot/handlers/query.py](src/bot/handlers/query.py#L125) | 125 | `except Exception:` without logging | Silent failure |
| [src/bot/handlers/start.py](src/bot/handlers/start.py#L77) | 77 | `except Exception:` without logging | Silent failure |
| [src/bot/handlers/start.py](src/bot/handlers/start.py#L85) | 85 | `except Exception:` without logging | Silent failure |

**Code Examples**:

```python
# ❌ CURRENT - Silent failure
async def cb_csv_download(query: CallbackQuery) -> None:
    try:
        await query.answer("⏳ Gerando CSV...")
        batch_id = query.data.split(":", 1)[1]
        await _send_bundle(query.message, batch_id)
    except Exception:
        pass  # 🔴 WHAT FAILED? NO LOGGING!

# ✓ FIXED - With logging
async def cb_csv_download(query: CallbackQuery) -> None:
    try:
        await query.answer("⏳ Gerando CSV...")
        batch_id = query.data.split(":", 1)[1]
        await _send_bundle(query.message, batch_id)
    except ValueError as e:
        logger.error("Invalid batch_id format", batch_id=query.data, error=e)
        await query.answer("❌ ID inválido", show_alert=True)
    except Exception as e:
        logger.exception("Unexpected error generating CSV", batch_id=query.data)
        await query.answer("❌ Erro ao gerar CSV", show_alert=True)
```

**Suggested Fix**:
1. Replace `except Exception:` with specific exception types
2. Log all exceptions with context
3. Return meaningful error messages to user

```python
# Pattern to follow:
try:
    # ... operation ...
except ValueError as e:
    logger.warning("Invalid input", input=data, error=str(e))
    await send_error_to_user(chat_id, "Dados inválidos")
except TimeoutError as e:
    logger.warning("Operation timeout", operation="query_export", error=str(e))
    await send_error_to_user(chat_id, "Operação expirou")
except Exception as e:
    logger.exception("Unexpected error", operation="query_export")
    await send_error_to_user(chat_id, "Erro inesperado - contate suporte")
```

**Risk if Changed**: Very Low (improves observability)  
**Risk if Unchanged**: High (bugs go unnoticed)

---

### 5. HTTP CALLS WITHOUT TIMEOUT (16 instances)

**Severity**: HIGH  
**Impact**: Indefinite hangs, resource exhaustion, service denial

#### Affected Areas

| File | Issue | Risk |
|------|-------|------|
| Multiple API endpoints | Missing timeout on external HTTP calls | Indefinite blocking |
| OSRM client | Route queries may hang forever | Service degradation |
| Database queries | Some async operations lack timeout | Connection pool exhaustion |

**Examples**:
```python
# ❌ RISKY - Could hang indefinitely
response = await userbot.query_poste(codigo)
result = await session.get(QueryBatch, batch_id)
osrm_response = await fetch_route(points)

# ✓ SAFE - With timeout protection
async with asyncio.timeout(30):  # Python 3.11+
    response = await userbot.query_poste(codigo)

# Or use contextlib.asynccontextmanager
async def with_timeout(coro, timeout_seconds=30):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error("Operation timed out after", seconds=timeout_seconds)
        raise
```

**Suggested Fixes**:
```python
# In src/services/osrm_client.py
async def fetch_route(points, timeout=60):
    try:
        async with asyncio.timeout(timeout):
            response = await httpx_client.post(OSRM_URL, json=data)
            return response.json()
    except asyncio.TimeoutError:
        logger.error("OSRM request timed out", timeout=timeout)
        raise

# In src/userbot/worker.py
async def _process_one(item, bot, timeout=45):
    async with asyncio.timeout(timeout):
        if item.query_type == "instalacao":
            response = await userbot.query_equipamento(item.code)
        else:
            response = await userbot.query_poste(item.code)
```

**Risk if Changed**: Very Low (defensive programming)  
**Risk if Unchanged**: Medium-High (possible service hangs)

---

### 6. UNUSED IMPORTS IN __init__.py FILES (40 instances)

**Severity**: HIGH (Code Clarity)  
**Impact**: Confusion about API surface, cluttered namespace

#### Affected Files

| File | Unused Imports | Count |
|------|-----------------|-------|
| [src/database/__init__.py](src/database/__init__.py) | `Meter`, `Base`, `KmlExport`, etc. | 10+ |
| [src/bot/__init__.py](src/bot/__init__.py) | `create_bot`, `create_dispatcher`, `on_startup`, `on_shutdown` | 4+ |
| [src/models/__init__.py](src/models/__init__.py) | `InstalacaoData`, `ChaveMontante`, `Coordenadas`, etc. | 7+ |
| [src/services/__init__.py](src/services/__init__.py) | `ResponseParser` | 1 |
| [src/dispatcher/__init__.py](src/dispatcher/__init__.py) | `query_queue`, `QueueItem` | 2 |

**Issue**: Re-exports defined but never used locally in __init__.py

**Suggested Fix**:
```python
# ❌ src/database/__init__.py BEFORE
from .connection import DatabaseManager, get_session, db
from .models import (
    Base,
    AuthorizedUser,
    NetworkQuery,
    QueryBatch,
    KmlExport,
    AgentRun,
    Meter,
)
from .types import uuid, uuid7, uuid7_timestamp

# ✓ AFTER - Clean re-exports with __all__
from .connection import DatabaseManager, get_session, db
from .models import (
    Base,
    AuthorizedUser,
    NetworkQuery,
    QueryBatch,
    KmlExport,
    AgentRun,
    Meter,
)
from .types import uuid, uuid7, uuid7_timestamp

# Define what's meant to be exported
__all__ = [
    'DatabaseManager',
    'get_session',
    'db',
    'Base',
    'AuthorizedUser',
    'NetworkQuery',
    'QueryBatch',
]

# Remove unused imports or add to __all__ if intentional
```

**Risk if Changed**: Low (may break if external code imports from these __init__ files)  
**Risk if Unchanged**: Low (mostly code clarity issue)

---

### 7. MISSING SPECIFIC EXCEPTION TYPES

**Severity**: HIGH  
**Impact**: Poor error diagnostics, difficult testing

**Example**:
```python
# ❌ VAGUE
except Exception:
    logger.error("Failed to get session")

# ✓ SPECIFIC  
except (sqlalchemy.exc.SQLAlchemyError, asyncio.TimeoutError) as e:
    logger.error("Database session failed", error=type(e).__name__, details=str(e))
    raise SessionError(f"Failed to establish session: {e}") from e
```

---

## 🟢 MEDIUM PRIORITY ISSUES (Orphan files, dead code, consistency)

### 8. FUNCTION NAME CONFLICTS (Same name, different purposes)

**Severity**: MEDIUM  
**Impact**: Confusing API, maintenance errors

| Function | Location 1 | Location 2 | Issue |
|----------|-----------|-----------|-------|
| `cb_kml_download` | [src/bot/keyboards/export.py](src/bot/keyboards/export.py#L11) | [src/bot/handlers/export.py](src/bot/handlers/export.py#L181) | Different signatures, different purposes |
| `get_session` | [src/database/connection.py](src/database/connection.py#L117) | [src/userbot/session_manager.py](src/userbot/session_manager.py#L74) | Different signatures, different purposes |

**Current Code**:
```python
# src/bot/keyboards/export.py (line 11)
def cb_kml_download(batch_id: str) -> str:
    """Monta callback_data para download de KML."""
    return f"{CB_KML_PREFIX}:{batch_id}"

# src/bot/handlers/export.py (line 181)
async def cb_kml_download(query: CallbackQuery) -> None:
    """Trata clique no botão de download."""
    await query.answer("⏳ Gerando arquivos...")
```

**Suggested Fix**:
```python
# RENAME in src/bot/keyboards/export.py
def kb_kml_download_data(batch_id: str) -> str:
    """Generates callback data for KML download button."""
    return f"{CB_KML_PREFIX}:{batch_id}"

# Or more clearly:
def kml_download_callback_data(batch_id: str) -> str:
    """Returns callback_data string for KML download button click."""
    return f"{CB_KML_PREFIX}:{batch_id}"

# Update usage in kml_download_kb():
def kml_download_kb(batch_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="📍 Baixar KML + CSV",
        callback_data=kml_download_callback_data(batch_id),  # Updated
    )
    return kb.as_markup()
```

**Risk if Changed**: Low-Medium (API changes, good for clarity)  
**Risk if Unchanged**: Low (works, but confusing)

---

### 9. LARGE MONOLITHIC FILES

**Severity**: MEDIUM  
**Impact**: Difficult testing, hard to maintain

| File | Lines | Classes | Functions | Concern |
|------|-------|---------|-----------|---------|
| [src/exporters/__init__.py](src/exporters/__init__.py) | 196 | 2 | 1 | Aggregate logic mixing different concerns |
| [src/services/parser.py](src/services/parser.py) | 284 | 1 | 8 | Parsing complex (but focused) |

**Analysis**:
- `exporters/__init__.py` contains export orchestration mixed with builder logic
- Could be separated into:
  - `orchestrator.py` - batch processing
  - `__init__.py` - clean re-exports

**Suggested Refactoring** (Optional - Lower priority):
```python
# NEW: src/exporters/orchestrator.py
async def export_batch(batch_id: str, output_dir: Path):
    """Orchestrate KML/GPX/CSV generation for a batch."""
    # All the complex logic from __init__.py

# NEW: src/exporters/__init__.py (Clean re-exports)
from .orchestrator import export_batch
from .kml_builder import build_kml
from .gpx_builder import build_gpx
from .csv_builder import build_csv

__all__ = ['export_batch', 'build_kml', 'build_gpx', 'build_csv']
```

**Risk if Changed**: Low (internal refactoring)  
**Risk if Unchanged**: Very Low (works fine, just harder to test)

---

### 10. HARDCODED VALUES (14 instances, mostly acceptable)

**Severity**: MEDIUM (Low-risk instances)  
**Impact**: Configuration management, testing difficulty

#### Analysis by Risk Level

**Low Risk (XML Namespaces)** - No change needed:
```python
OSMAND_NS = "https://osmand.net"  # Standard namespace
GPXX_NS = "http://www.garmin.com/xmlschemas/GpxExtensions/v3"  # Standard
```

**Medium Risk (URLs)** - Should be configurable:
```python
# src/exporters/maps_link.py - Line 33
urls.append(f"https://www.google.com/maps/dir/{coords}")  # ❌ Hardcoded

# ✓ Better:
maps_url_base = settings.GOOGLE_MAPS_BASE_URL or "https://www.google.com/maps"
urls.append(f"{maps_url_base}/dir/{coords}")
```

**Suggested Fix** (Optional):
```python
# src/config.py - Add
GOOGLE_MAPS_BASE_URL: str = Field(default="https://www.google.com/maps")
WAZE_BASE_URL: str = Field(default="https://waze.com")

# Usage in exporters:
from src.config import settings

def build_maps_links(poste):
    urls = [f"{settings.GOOGLE_MAPS_BASE_URL}/dir/..."]
    return urls
```

**Risk if Changed**: Very Low (improves configurability)  
**Risk if Unchanged**: Very Low (URLs are unlikely to change)

---

## 🔵 LOW PRIORITY ISSUES (Minor inconsistencies)

### 11. TYPE HINTS COVERAGE

**Severity**: LOW  
**Impact**: IDE support, code clarity

**Suggestion**: Add return type hints to:
- [src/services/parser.py](src/services/parser.py) - `parse_*` functions
- [src/exporters/adapter.py](src/exporters/adapter.py) - conversion functions

```python
# ❌ Before
def parse_poste_response(raw: str):
    # ...
    return PosteData(...)

# ✓ After
def parse_poste_response(raw: str) -> PosteData:
    # ...
    return PosteData(...)
```

---

### 12. DOCUMENTATION

**Severity**: LOW  
**Impact**: Onboarding, maintenance

**Suggestion**: Add docstrings to:
- Parser regex patterns (explain what they match)
- Export orchestration functions
- Configuration options

---

### 13. TECHNICAL DEBT MARKER

**Severity**: LOW  
**Status**: 1 comment found (not critical)

| File | Line | Comment |
|------|------|---------|
| [src/bot/handlers/export.py](src/bot/handlers/export.py#L155) | 155 | `<i>O ID aparece como #xxxxxxxx na mensagem 'Lote enfileirado'.</i>` |

This is documentation, not a debt marker. No action needed.

---

## Summary of Issues by Risk

### Critical (Fix Immediately - ~2 days)
1. ✅ **PosteData duplication** - Different structures in 2 places
2. ✅ **Coordenadas duplication** - Dataclass vs Pydantic mismatch  
3. ✅ **Parser duplication** - Two parsing implementations

### High Priority (Fix This Sprint - ~3-4 days)
4. ✅ **17 orphan backup files** - Clean repository
5. ✅ **Broad exception handlers** - Add logging
6. ✅ **Missing HTTP timeouts** - Prevent hangs
7. ✅ **Unused imports** - Clean __init__.py files

### Medium Priority (Next Sprint - ~2-3 days)
8. ✅ **Rename conflicting functions** - Improve clarity
9. ✅ **Refactor large files** - Improve testability
10. ✅ **Configure hardcoded values** - Improve flexibility

### Low Priority (Technical Debt - ~1 day)
11. ✅ **Add type hints** - Improve IDE support
12. ✅ **Improve documentation** - Improve onboarding

---

## Recommended Action Plan

### Phase 1: Cleanup (Day 1 - ~30 minutes)
```bash
# Remove all orphan files
find src -type f \( -name "*.bak*" -o -name "*.old" \) -delete
git commit -m "chore: remove backup files"
```

### Phase 2: Critical Refactoring (Days 2-3 - ~4-6 hours)
1. Consolidate PosteData classes
2. Consolidate Coordenadas classes  
3. Run full test suite
4. Update imports across codebase

### Phase 3: Error Handling & Robustness (Days 4-5 - ~3-4 hours)
1. Add specific exception types to all handlers
2. Add logging to all exception handlers
3. Add HTTP timeouts to all async calls
4. Consolidate parser logic

### Phase 4: Code Quality (Sprint 2 - ~2-3 hours)
1. Remove unused imports from __init__.py
2. Rename conflicting functions
3. Optionally refactor large files
4. Add comprehensive type hints

---

## Files to Modify (Priority Order)

| Priority | File | Change Type | Effort |
|----------|------|-------------|--------|
| 1 | src/models/schemas.py | Consolidate models | 2h |
| 2 | src/api/main.py | Use imported models | 1h |
| 3 | src/exporters/parser.py | Use models, add converter | 2h |
| 4 | src/services/parser.py | Consolidate logic | 1h |
| 5 | src/bot/handlers/export.py | Add error handling | 1h |
| 6 | src/bot/handlers/query.py | Add error handling | 1h |
| 7 | src/bot/handlers/start.py | Add error handling | 1h |
| 8 | src/database/__init__.py | Clean up exports | 0.5h |
| 9 | src/bot/keyboards/export.py | Rename functions | 0.5h |
| 10 | src/**/*.py | Add HTTP timeouts | 1h |

**Total Estimated Effort**: ~12-15 hours (~2-3 days of focused work)

---

## Testing Strategy

### Before Changes
```bash
pytest tests/ -v --cov=src
```

### After Each Phase
```bash
# Phase 1: Delete files - verify no imports
grep -r "\.bak\|\.old" src/ --include="*.py"  # Should return nothing

# Phase 2: Model consolidation - type checking
mypy src/ --ignore-missing-imports

# Phase 3: Error handling - test exception paths
pytest tests/ -v -k "exception or error"

# Phase 4: Code quality - linting
pylint src/ --disable=C0111  # Ignore missing docstring warnings
```

### Integration Test
```bash
# Test full export pipeline
pytest tests/test_export_pipeline.py -v

# Test parser consistency
pytest tests/test_parser_consolidation.py -v
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Breaking API during refactoring | Run full test suite after each change |
| Lost backup information | Check git history if backups needed |
| Parser behavior changes | Add parser unit tests before refactoring |
| Exception handler changes cause silence | Add assertion that exceptions are logged |

---

## Sign-Off Checklist

- [ ] All 17 backup files removed
- [ ] PosteData classes consolidated
- [ ] Coordenadas classes consolidated
- [ ] All broad exception handlers updated with logging
- [ ] HTTP timeouts added to all async calls
- [ ] Unused imports removed from __init__.py
- [ ] Conflicting function names fixed
- [ ] Full test suite passes with 100% coverage
- [ ] Code review completed
- [ ] Changes deployed to development environment

---

**Report Generated**: 2026-05-22  
**Next Review**: After Phase 1 completion
