# Product Requirements Document: Import Feature for Playbooks

## Executive Summary

This PRD defines the implementation of an import directive feature for Playbooks that allows code injection from external files into Playbooks programs. The feature enables modular composition, code reuse, and separation of concerns while maintaining the natural language programming paradigm.

## 1. Problem Statement

### Current Limitations
- **Code Duplication**: Common patterns, utilities, and configurations must be duplicated across playbook files
- **Maintainability**: Updates to shared logic require manual changes in multiple locations
- **Modularity**: No mechanism for breaking large playbooks into smaller, manageable components
- **Reusability**: Cannot share playbook fragments, prompts, or configurations across projects
- **Scalability**: Large playbooks become unwieldy without modularization capabilities

### User Needs
- Software engineers need to apply DRY (Don't Repeat Yourself) principles to playbook development
- Teams need to share common playbook components across projects
- Developers need to organize complex playbooks into logical modules
- Organizations need to maintain libraries of reusable playbook patterns

## 2. Solution Overview

### Core Concept
Introduce an `!import` directive that injects external file contents at the specified location during the compilation phase, with automatic indentation preservation and recursive import support.

### Key Benefits
- **Modularity**: Break complex playbooks into manageable, focused modules
- **Reusability**: Share common patterns, utilities, and configurations
- **Maintainability**: Single source of truth for shared components
- **Flexibility**: Support various file types and content formats
- **Safety**: Built-in recursion detection and error handling

## 3. Functional Requirements

### 3.1 Import Directive Syntax

#### Basic Syntax
```markdown
!import <file_path>
```

#### Examples
```markdown
# Agent Configuration
!import config/agent_settings.pb

!import shared_playbooks.pb

## Main Workflow
!import workflow_description.txt
### Steps
- Welcome the user
- If user is ready
  !import workflows/main_steps.pb
!import workflows/end_program.pb

!import agents/auth_agent.pb
```

### 3.2 File Path Resolution

#### Supported Path Types
1. **Relative Paths**: Resolved relative to the importing file's directory
   ```markdown
   !import ./helpers/utils.pb
   !import ../shared/config.yml
   ```

2. **Absolute Paths**: Full system paths
   ```markdown
   !import /opt/playbooks/library/standard.pb
   ```

3. **URL Paths**: URL-based imports
   ```markdown
   !import https://company.com/patterns/retry.pb
   !import file:///opt/playbooks/library/standard.pb
   ```

### 3.3 Content Processing

#### Indentation Preservation
- The directive's indentation level is applied to every line of imported content
- Maintains structural integrity in nested contexts

```markdown
## Steps
  !import steps/validation.md
```

If `steps/validation.md` contains:
```markdown
- Validate input parameters
- Check data integrity
```

Result after import:
```markdown
## Steps
  - Validate input parameters
  - Check data integrity
```

#### File Type Support
Any text file of any extension can be imported.

### 3.4 Nested Imports

#### Recursive Import Support
- Imported files may contain their own `!import` directives
- Maximum nesting depth: 10 levels (configurable)
- Processed depth-first during compilation

```markdown
# main.pb
!import modules/workflow.pb

# modules/workflow.pb
## Workflow Steps
!import ../shared/common_steps.md
!import ../utils/helpers.py
```

### 3.5 Recursion Detection

#### Circular Dependency Prevention
- Track import chain during compilation
- Detect and report circular dependencies
- Provide clear error messages with import chain

```
Error: Circular dependency detected:
  main.pb → modules/a.pb → modules/b.pb → modules/a.pb
```

#### Implementation Strategy
```python
class ImportTracker:
    def __init__(self):
        self.import_stack = []  # Current import chain
        self.processed_files = {}  # Cache of processed content
    
    def check_recursion(self, file_path):
        canonical_path = Path(file_path).resolve()
        if canonical_path in self.import_stack:
            raise CircularImportError(self.import_stack + [canonical_path])
```

## 4. Technical Architecture

### 4.1 Integration Points

#### Compilation Pipeline Integration

1. **Pre-Loader Phase** (New)
   - Process imports before main loader
   - Resolve all file paths
   - Build dependency graph

2. **Loader Enhancement**
   - Modify `Loader.read_program_files()` to handle imports
   - Maintain file dependency tracking
   - Cache processed imports

3. **Compiler Integration**
   - Process expanded content post-import
   - Maintain source mapping for debugging
   - Preserve line number accuracy

### 4.2 Implementation Components

```python
# New module: src/playbooks/import_processor.py
class ImportProcessor:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.import_tracker = ImportTracker()
        self.source_map = SourceMap()
    
    def process_imports(self, content: str, file_path: Path) -> str:
        """Process all !import directives in content."""
        lines = content.split('\n')
        result = []
        
        for line_num, line in enumerate(lines, 1):
            if self._is_import_directive(line):
                imported_content = self._process_import(line, file_path)
                result.extend(imported_content)
                self.source_map.add_mapping(line_num, imported_file, imported_lines)
            else:
                result.append(line)
        
        return '\n'.join(result)
```

### 4.3 Source Mapping

#### Debugging Support
- Maintain mapping between compiled lines and original sources
- Enable accurate error reporting
- Support VSCode extension debugging

```python
class SourceMap:
    def __init__(self):
        self.mappings = []  # [(compiled_line, source_file, source_line)]
    
    def add_mapping(self, compiled_line: int, source_file: Path, source_line: int):
        self.mappings.append((compiled_line, source_file, source_line))
    
    def get_original_location(self, compiled_line: int) -> Tuple[Path, int]:
        """Get original file and line number for a compiled line."""
        for mapping in self.mappings:
            if mapping[0] == compiled_line:
                return (mapping[1], mapping[2])
```

## 5. Error Handling

### 5.1 Error Types

1. **FileNotFoundError**
   ```
   Error: Cannot import 'utils/helper.pb' - file not found
   Location: main.pb, line 15
   ```

2. **CircularImportError**
   ```
   Error: Circular import detected in import chain:
   main.pb:10 → modules/a.pb:5 → modules/b.pb:8 → modules/a.pb
   ```

3. **MaxNestingDepthError**
   ```
   Error: Maximum import nesting depth (10) exceeded
   Import chain: [detailed chain]
   ```

4. **InvalidPathError**
   ```
   Error: Invalid import path '../../../etc/passwd' - path traversal not allowed
   ```

### 5.2 Error Recovery
- Continue compilation with warnings for non-critical imports
- Provide fallback behavior for missing optional imports
- Clear error messages with actionable fixes

## 6. Security Considerations

### 6.1 Path Traversal Prevention
- Validate paths don't escape project boundaries
- Restrict access to system files
- Configurable allowed import directories

### 6.2 File Access Control
- Respect file system permissions
- Optional sandboxing for untrusted playbooks
- Audit logging for import operations

### 6.3 Content Validation
- Size limits for imported files (default: 1MB)
- File type validation
- Optional content scanning for malicious patterns

## 7. Performance Optimization

### 7.1 Caching Strategy
- Cache processed imports during compilation
- Invalidate cache on file modification
- Share cache across compilation runs

### 7.2 Lazy Loading
- Only process imports when needed
- Parallel import processing for independent files
- Progressive compilation for large import trees

## 8. Configuration

### 8.1 Environment Variables
```bash
PLAYBOOKS_IMPORT_MAX_DEPTH=10        # Maximum nesting depth
PLAYBOOKS_IMPORT_MAX_FILE_SIZE=1MB   # Maximum imported file size
PLAYBOOKS_IMPORT_ALLOWED_DIRS=.      # Allowed import directories
PLAYBOOKS_IMPORT_CACHE_ENABLED=true  # Enable import caching
```

### 8.2 Configuration File
```yaml
# playbooks.config.yml
import:
  max_depth: 10
  max_file_size: 1048576
  allowed_directories:
    - .
    - ./lib
    - ./shared
  cache:
    enabled: true
    ttl: 3600
  security:
    sandbox: false
    audit_log: true
```

## 9. Testing Strategy

### 9.1 Unit Tests
- Import directive parsing
- Path resolution logic
- Recursion detection
- Indentation preservation
- Source mapping accuracy

### 9.2 Integration Tests
- Full compilation pipeline with imports
- Multi-file import scenarios
- Nested import chains
- Error handling flows
- Cache behavior

### 9.3 Test Cases

```python
# test_import_basic.py
def test_simple_import():
    """Test basic import functionality."""
    content = "!import helper.txt"
    result = process_imports(content, Path("main.pb"))
    assert "imported content" in result

def test_circular_import_detection():
    """Test circular dependency detection."""
    with pytest.raises(CircularImportError):
        process_imports("!import self.pb", Path("self.pb"))

def test_indentation_preservation():
    """Test that indentation is preserved."""
    content = "  !import indented.txt"
    result = process_imports(content, Path("main.pb"))
    assert all(line.startswith("  ") for line in result.split("\n"))
```

## 10. Migration Path

### 10.1 Backward Compatibility
- Existing playbooks work without modification
- Import directive is opt-in
- No breaking changes to current API

### 10.2 Adoption Strategy
1. **Phase 1**: Basic import support (MVP)
2. **Phase 2**: Advanced features (caching, source maps)
3. **Phase 3**: Package system integration
4. **Phase 4**: IDE support and tooling

## 11. Future Enhancements

### 11.1 Conditional Imports
```markdown
!import[if:DEBUG] debug/verbose_logging.pb
!import[if:PRODUCTION] config/prod_settings.yml
```

### 11.2 Parameterized Imports
Import a specific agent from a playbooks file
```markdown
!import templates/agent.pb::AccountantAgent
```

Import a specific playbook from a playbooks file
```markdown
!import templates/agent.pb::AccountantAgent::GetTaxRate
```

## 12. Success Metrics

### 12.1 Adoption Metrics
- Number of playbooks using imports
- Average imports per playbook
- Reduction in code duplication

### 12.2 Performance Metrics
- Compilation time with imports
- Cache hit ratio
- Memory usage during import processing

### 12.3 Quality Metrics
- Error rate during import processing
- Time to resolve import-related issues
- User satisfaction scores

## 13. Implementation Status

### ✅ Completed Features (MVP - Phase 1)

#### Core Implementation
- **ImportProcessor Class** (`src/playbooks/import_processor.py`)
  - Regex-based import directive detection: `^(\s*)!import\s+(.+?)(?:\s*#.*)?$`
  - Recursive import processing with depth tracking
  - File caching to avoid redundant reads
  - Source mapping foundation for debugging support

#### Integration Points
- **Loader Integration** (`src/playbooks/loader.py`)
  - Modified `_read_program_files()` to process imports
  - Import processing occurs before compilation
  - Only processes imports in non-compiled files (.pb, .md, .txt)
  - Maintains backward compatibility

#### Error Handling
- **Custom Exception Classes**:
  - `CircularImportError`: Detects and reports circular dependencies
  - `ImportDepthError`: Enforces maximum nesting depth (default: 10)
  - `ImportNotFoundError`: Clear error messages with file location

#### Features Implemented
- ✅ Basic import directive parsing
- ✅ File content injection at import location
- ✅ Relative and absolute path resolution
- ✅ Indentation preservation for all imported lines
- ✅ Nested import support (recursive processing)
- ✅ Circular dependency detection
- ✅ Maximum depth limit enforcement
- ✅ File size validation (1MB default)
- ✅ Import caching for performance
- ✅ Comment support after import directive

#### Test Coverage
- **Unit Tests** (`tests/unit/playbooks/test_import_processor.py`)
  - 16 comprehensive test cases covering all features
  - Tests for error conditions and edge cases
  - All tests passing

- **Integration Tests** (`tests/unit/playbooks/test_import_integration.py`)
  - 8 integration test cases
  - End-to-end testing with Loader and Compiler
  - Multiple file import scenarios
  - All tests passing

### 🚧 In Progress Features

#### Source Mapping Enhancement
- Basic structure implemented in `SourceMapping` class
- Needs refinement for accurate line number tracking
- Required for VSCode debugging support

### 📋 Pending Features (Future Phases)

#### Phase 2: Advanced Features
- [ ] Enhanced source mapping with full debugging support
- [ ] URL-based imports (HTTP/HTTPS)
- [ ] Configuration file support (playbooks.config.yml)
- [ ] Environment variable configuration
- [ ] Audit logging for import operations

#### Phase 3: Package System
- [ ] Package-based imports (@playbooks/stdlib)
- [ ] Import aliases (!import ... as ...)
- [ ] Selective imports (sections, functions)
- [ ] Remote repository imports (git)

#### Phase 4: Tooling
- [ ] VSCode extension integration
- [ ] Import graph visualization
- [ ] Performance profiling tools
- [ ] Migration utilities

### Timeline Update

#### Completed
- **Week 1**: ✅ MVP implementation complete
- **Week 1**: ✅ Full test coverage achieved
- **Week 1**: ✅ Integration with existing pipeline

#### Revised Timeline
- **Week 2**: Source mapping refinement, documentation
- **Week 3-4**: URL imports, configuration system
- **Week 5-6**: Package system, selective imports
- **Week 7-8**: VSCode integration, tooling

## 14. Implementation Examples

### Example 1: Simple Import
```python
# File: main.pb
# Test Agent
!import helper.txt
## Steps
- Process data

# File: helper.txt
Configuration loaded

# Result after processing:
# Test Agent
Configuration loaded
## Steps
- Process data
```

### Example 2: Indented Import
```python
# File: main.pb
## Steps
  !import steps.md
  
# File: steps.md
- Step 1
- Step 2
  - Sub-step

# Result after processing:
## Steps
  - Step 1
  - Step 2
    - Sub-step
```

### Example 3: Nested Imports
```python
# File: main.pb
!import level1.txt

# File: level1.txt
Level 1
!import level2.txt

# File: level2.txt
Level 2

# Result after processing:
Level 1
Level 2
```

## 15. Open Questions

1. Should imports be processed at compile-time or runtime?
   - **Recommendation**: Compile-time for performance and validation

2. How should we handle imports of compiled (.pbasm) files?
   - **Recommendation**: Support both .pb and .pbasm imports

3. Should we support dynamic imports based on runtime conditions?
   - **Recommendation**: Start with static imports, consider dynamic in future

4. What should be the default maximum nesting depth?
   - **Recommendation**: 10 levels with configuration option

5. How should we handle imports in the VSCode extension?
   - **Recommendation**: Show imported content inline with visual indicators

## 15. Appendix

### A. Example Use Cases

#### A.1 Shared Agent Configuration
```markdown
# config/base_agent.pb
---
model: gpt-4
temperature: 0.7
max_tokens: 2000
---

# main.pb
!import config/base_agent.pb

# Customer Service Agent
Uses the imported configuration
```

#### A.2 Modular Workflow
```markdown
# workflows/validation.pb
## Validation Steps
- Check input format
- Validate business rules
- Ensure data consistency

# main.pb
# Data Processing Agent

## Process Data
### Steps
!import workflows/validation.pb
- Transform data
- Save results
```

#### A.3 Utility Library
```markdown
# utils/retry.pb
### Retry Logic
- If operation fails, wait 1 second
- Retry up to 3 times
- Log each attempt

# main.pb
## API Call
### Steps
- Make API request
!import utils/retry.pb
```

### B. Alternative Syntax Considered

1. **Include directive**: `#include <file>`
2. **Python-style**: `from file import content`
3. **Markdown reference**: `[import](file.pb)`
4. **YAML-style**: `$ref: file.pb`

**Decision**: `!import` chosen for clarity and consistency with Markdown conventions.