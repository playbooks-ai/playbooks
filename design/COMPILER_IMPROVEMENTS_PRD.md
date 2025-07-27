# Playbooks Compiler Improvements PRD

## Executive Summary

This document outlines a phased approach to improve the Playbooks compilation system, addressing current limitations with large programs, mixed file types, and multi-agent compilation reliability. The improvements will enable better scalability, faster iteration cycles, and more reliable compilation outcomes.

## Problem Statement

The current compilation system has several critical limitations:

1. **Scalability Issues**: Large programs with multiple agents exceed LLM context limits as all files are concatenated and sent in a single request
2. **Compilation Failures**: The LLM struggles with multiple agents, often failing to generate required `public.json` sections for each agent
3. **Mixed File Handling**: When any `.pbasm` (compiled) file is present, the entire compilation is skipped, preventing `.pb` files from being compiled
4. **Performance**: No caching mechanism exists, requiring full recompilation on every run
5. **Token Inefficiency**: Sending entire programs for compilation wastes tokens and increases latency

## Proposed Solution

A three-phase improvement plan that progressively enhances the compilation system:

### Phase 1: Independent File Compilation
Process each file independently rather than concatenating all files before compilation.

### Phase 2: Compilation Caching
Implement timestamp-based caching following Python's pyc model to avoid recompiling unchanged files.

### Phase 3: Agent-Level Compilation
Compile individual agents within files for better LLM accuracy and parallelization potential.

## Detailed Design

### Phase 1: Independent File Compilation

#### Current State
```python
# Current flow
1. Loader.read_program() → concatenates all files
2. Compiler.process() → sends entire content to LLM
3. Program extracts public.json sections
```

#### Proposed Changes

##### 1.1 Loader Modifications
```python
class Loader:
    @staticmethod
    def read_program_files(program_paths: List[str]) -> List[Tuple[str, str, bool]]:
        """
        Load program files individually.
        
        Returns:
            List of (file_path, content, is_compiled) tuples
        """
        all_files = []
        
        for path in paths:
            if "*" in str(path) or "?" in str(path):
                all_files.extend(glob(path, recursive=True))
            else:
                all_files.append(path)
        
        files_data = []
        for file in all_files:
            file_path = Path(file)
            if file_path.exists():
                content = file_path.read_text()
                is_compiled = file_path.suffix == '.pbasm'
                files_data.append((str(file_path), content, is_compiled))
        
        return files_data
```

##### 1.2 Compiler Modifications
```python
class Compiler:
    def process_files(self, files: List[Tuple[str, str, bool]]) -> str:
        """Process files individually and combine results."""
        compiled_parts = []
        
        for file_path, content, is_compiled in files:
            if is_compiled:
                # Already compiled, use as-is
                compiled_parts.append(content)
            else:
                # Compile individual file
                compiled = self.process_single_file(file_path, content)
                compiled_parts.append(compiled)
        
        # Join compiled parts directly - no boundary markers needed
        return "\n\n".join(compiled_parts)
    
    def process_single_file(self, file_path: str, content: str) -> str:
        """Compile a single .pb file."""
        preprocessed = self.preprocess_program(content)
        
        # Use existing compilation logic (includes validation)
        return self._compile_content(preprocessed)
```

##### 1.3 Integration Updates
```python
class Playbooks:
    def __init__(self, program_paths: List[str], ...):
        # Load files individually
        self.program_files = Loader.read_program_files(program_paths)
        
        # Extract and apply frontmatter from first file if present
        self.program_metadata = {}
        if self.program_files:
            first_file_path, first_file_content, _ = self.program_files[0]
            fm_data = frontmatter.loads(first_file_content)
            if fm_data.metadata:
                self.program_metadata = fm_data.metadata
                # Update first file content to remove frontmatter
                self.program_files[0] = (first_file_path, fm_data.content, self.program_files[0][2])
        
        # Compile files individually (without frontmatter)
        compiler = Compiler(self.llm_config)
        self.compiled_program_content = compiler.process_files(self.program_files)
        
        # Apply program metadata
        self._apply_program_metadata()
        
        # Rest of initialization...
    
    def _apply_program_metadata(self):
        """Apply program-level metadata from frontmatter."""
        for key, value in self.program_metadata.items():
            if hasattr(self, key):
                setattr(self, key, value)
```

#### Benefits
- Handles mixed .pb/.pbasm files correctly
- Enables parallel compilation in future
- Better error isolation per file
- Foundation for caching

### Phase 2: Compilation Caching

#### Design Goals
- Timestamp-based cache invalidation (following Python's pyc model)
- Version-aware cache naming
- Minimal overhead for cache hits
- Persistent cache across sessions

#### Implementation

##### 2.1 Cache Strategy
Following Python's pyc model:
- Cache files named like: `customer_support.playbooks-0.4.2.pbasm`
- Store in `.playbooks` directory in the same folder as source files
- Use timestamp comparison for staleness check
- Invalidate if compiler prompt changes

**Cache Location Rationale**: Using `.playbooks` in the same directory as source files (like Python) provides:
- Easy project-specific cache management
- Natural cleanup when deleting projects
- Familiar pattern for Python developers
- Simple .gitignore rules (`.playbooks/`)

##### 2.2 Compiler Integration
```python
class Compiler:
    def __init__(self, llm_config: LLMConfig, use_cache: bool = True):
        self.llm_config = llm_config
        self.use_cache = use_cache
        self.playbooks_version = self._get_playbooks_version()
        self.prompt_path = os.path.join(
            os.path.dirname(__file__), "prompts/preprocess_playbooks.txt"
        )
    
    def _get_cache_path(self, file_path: str) -> Path:
        """Get cache file path following Python's model."""
        source_path = Path(file_path)
        cache_dir = source_path.parent / ".pbasm_cache"
        cache_name = f"{source_path.stem}.playbooks-{self.playbooks_version}.pbasm"
        return cache_dir / cache_name
    
    def _is_cache_valid(self, source_path: Path, cache_path: Path) -> bool:
        """Check if cache is still valid based on timestamps."""
        if not cache_path.exists():
            return False
        
        # Check source file timestamp
        source_mtime = source_path.stat().st_mtime
        cache_mtime = cache_path.stat().st_mtime
        
        if source_mtime > cache_mtime:
            return False
        
        # Check compiler prompt timestamp
        prompt_mtime = Path(self.prompt_path).stat().st_mtime
        if prompt_mtime > cache_mtime:
            return False
        
        return True
    
    def process_single_file(self, file_path: str, content: str) -> str:
        """Compile a single file with caching."""
        source_path = Path(file_path)
        
        # Check cache first
        if self.use_cache:
            cache_path = self._get_cache_path(file_path)
            
            if self._is_cache_valid(source_path, cache_path):
                console.print(f"[dim green]Using cached compilation for {file_path}[/dim green]")
                return cache_path.read_text()
        
        # Compile if not cached
        console.print(f"[dim pink]Compiling {file_path}[/dim pink]")
        compiled = self._compile_content(content)
        
        # Store in cache
        if self.use_cache:
            cache_path = self._get_cache_path(file_path)
            cache_path.parent.mkdir(exist_ok=True)
            cache_path.write_text(compiled)
        
        return compiled
```


#### Benefits
- 80-90% faster incremental compilation
- Reduced LLM API costs
- Better development iteration speed
- Persistent across sessions

### Phase 3: Agent-Level Compilation

#### Design Goals
- Compile each agent independently
- Better LLM accuracy with focused context
- Proper public.json generation per agent
- Support for large multi-agent programs

#### Implementation

##### 3.1 Agent Extraction in Compiler
```python
class Compiler:
    def _extract_agents(self, content: str) -> List[Dict]:
        """Extract individual agents from markdown content."""
        # Parse markdown AST (content should already have frontmatter removed)
        ast = parse_markdown_to_dict(content)
        
        agents = []
        current_h1 = None
        
        for child in ast.get("children", []):
            if child["type"] == "h1":
                # Start new agent
                current_h1 = {
                    "name": child.get("text", "").strip(),
                    "content": "",
                    "start_line": child.get("line", 0)
                }
                agents.append(current_h1)
            
            if current_h1:
                # Accumulate content for current agent
                current_h1["content"] += child.get("markdown", "") + "\n"
        
        return agents

    def process_single_file(self, file_path: str, content: str) -> str:
        """Process file with agent-level compilation."""
        source_path = Path(file_path)
        
        # Check cache first (file-level, not agent-level)
        if self.use_cache:
            cache_path = self._get_cache_path(file_path)
            if self._is_cache_valid(source_path, cache_path):
                console.print(f"[dim green]Using cached compilation for {file_path}[/dim green]")
                return cache_path.read_text()
        
        # Extract agents (content should already have frontmatter removed)
        agents = self._extract_agents(content)
        
        if len(agents) == 0:
            raise ProgramLoadError(f"No agents found in {file_path}")
        
        if len(agents) == 1:
            # Single agent - compile just the agent
            console.print(f"[dim pink]Compiling {file_path}[/dim pink]")
            compiled = self._compile_agent(agents[0]["content"])
        else:
            # Multiple agents - compile each independently
            console.print(f"[dim pink]Compiling {file_path} ({len(agents)} agents)[/dim pink]")
            compiled_agents = []
            
            for i, agent_info in enumerate(agents):
                agent_name = agent_info["name"]
                agent_content = agent_info["content"]
                
                # Compile individual agent
                console.print(f"  [dim pink]Agent: {agent_name}[/dim pink]")
                compiled_agent = self._compile_agent(agent_content)
                compiled_agents.append(compiled_agent)
            
            # Combine all agents
            compiled = "\n\n".join(compiled_agents)
        
        # Cache the result
        if self.use_cache:
            cache_path.parent.mkdir(exist_ok=True)
            cache_path.write_text(compiled)
        
        return compiled
    
    def _compile_agent(self, agent_content: str) -> str:
        """Compile a single agent."""
        # Use existing prompt with agent content only (no frontmatter)
        prompt_path = os.path.join(
            os.path.dirname(__file__), "prompts/preprocess_playbooks.txt"
        )
        with open(prompt_path, "r") as f:
            prompt = f.read()
        
        # Replace the playbooks placeholder
        prompt = prompt.replace("{{PLAYBOOKS}}", agent_content)
        
        # Get LLM response
        messages = get_messages_for_prompt(prompt)
        response = get_completion(
            llm_config=self.llm_config,
            messages=messages,
            stream=False
        )
        
        return next(response)
```

#### Design Notes
- **Frontmatter Handling**: Frontmatter is extracted and applied to the Program class before compilation begins. All compilation happens on clean content without frontmatter, ensuring the LLM prompt works correctly.
- **Agent Content**: Each agent is compiled independently without any program-level metadata.
- **Error Handling**: Missing agents (len == 0) throws an exception to catch malformed files early.

#### Benefits
- Handles programs with 10+ agents reliably
- Accurate public.json generation per agent
- Better error isolation
- Enables future parallelization


## Implementation Timeline

### Week 1: Phase 1 - Independent File Compilation
- **Day 1-2**: Implement Loader.read_program_files()
- **Day 3**: Implement Compiler.process_files()
- **Day 4**: Update integration points
- **Day 5**: Testing and validation

### Week 2: Phase 2 - Caching
- **Day 1-2**: Implement CompilationCache
- **Day 3**: Integrate with Compiler
- **Day 4**: Add cache management commands
- **Day 5**: Performance testing

### Week 3: Phase 3 - Agent-Level Compilation
- **Day 1-2**: Implement AgentExtractor
- **Day 3**: Update Compiler for agents
- **Day 4**: Create single-agent prompt
- **Day 5**: End-to-end testing

### Week 4: Stabilization
- **Day 1-2**: Bug fixes from testing
- **Day 3**: Performance optimization
- **Day 4**: Documentation updates
- **Day 5**: Release preparation

## Success Metrics

### Performance Metrics
- **Compilation Speed**: 80% faster for incremental changes (Phase 2)
- **Success Rate**: 95%+ successful compilations for multi-agent programs (Phase 3)
- **Token Usage**: 60% reduction in LLM tokens used (Phase 1+3)
- **Cache Hit Rate**: 70%+ cache hits during development (Phase 2)

### Quality Metrics
- **Error Rate**: <5% compilation failures
- **public.json Accuracy**: 100% correct generation
- **Backward Compatibility**: 100% existing programs compile correctly

### Developer Experience
- **Iteration Speed**: <2 seconds for cached compilation
- **Error Messages**: Clear, actionable compilation errors
- **Debugging**: Better error isolation per file/agent

## Risk Analysis

### Technical Risks
1. **LLM Variability**: Different responses for same input
   - *Mitigation*: Structured prompts, validation, retry logic

2. **Cache Corruption**: Invalid cached data
   - *Mitigation*: Hash verification, automatic cleanup

3. **Breaking Changes**: Incompatible with existing code
   - *Mitigation*: Feature flags, gradual rollout

### Operational Risks
1. **Performance Regression**: Slower than current system
   - *Mitigation*: Benchmarking, profiling, optimization

2. **Increased Complexity**: Harder to maintain
   - *Mitigation*: Clear architecture, comprehensive tests

## Testing Strategy

### Unit Tests
```python
# test_compiler_cache.py
def test_cache_hit():
    compiler = Compiler(llm_config)
    # Create a test file
    test_file = Path("test.pb")
    test_file.write_text("# TestAgent\ncontent")
    
    # First compilation
    result1 = compiler.process_single_file("test.pb", "# TestAgent\ncontent")
    
    # Second compilation should use cache
    result2 = compiler.process_single_file("test.pb", "# TestAgent\ncontent")
    assert result1 == result2

def test_cache_invalidation_on_change():
    compiler = Compiler(llm_config)
    test_file = Path("test.pb")
    
    # First version
    test_file.write_text("# TestAgent\nversion1")
    result1 = compiler.process_single_file("test.pb", "# TestAgent\nversion1")
    
    # Modified version
    time.sleep(0.1)  # Ensure different timestamp
    test_file.write_text("# TestAgent\nversion2")
    result2 = compiler.process_single_file("test.pb", "# TestAgent\nversion2")
    
    assert result1 != result2

# test_agent_extraction.py
def test_extract_multiple_agents():
    compiler = Compiler(llm_config)
    content = "# Agent1\n...\n# Agent2\n..."
    agents, _ = compiler._extract_agents(content)
    assert len(agents) == 2
    assert agents[0]["name"] == "Agent1"
```

### Integration Tests
```python
# test_file_compilation.py
def test_mixed_pb_pbasm():
    files = [
        ("a.pb", "# Agent A", False),
        ("b.pbasm", "# Compiled B", True),
        ("c.pb", "# Agent C", False)
    ]
    result = compiler.process_files(files)
    assert "# Agent A" in result
    assert "# Compiled B" in result
    assert "# Agent C" in result
```

### End-to-End Tests
- Large multi-agent programs
- Mixed file types
- Cache persistence
- Error scenarios

## Rollout Plan

### Phase 1 Rollout
1. Feature flag: `--use-file-compilation`
2. Beta testing with selected users
3. Monitor compilation success rates
4. Full rollout after 1 week stable

### Phase 2 Rollout
1. Cache enabled by default
2. Add `--no-cache` flag for debugging
3. Monitor cache hit rates
4. Cache management CLI commands

### Phase 3 Rollout
1. Agent compilation for files with 3+ agents
2. Gradual threshold reduction
3. Monitor public.json generation
4. Full rollout when stable

## Future Enhancements

### Near Term
1. Parallel compilation for multiple files
2. Incremental compilation (only changed agents)
3. Compilation progress indicators
4. Better error recovery

### Long Term
1. AI-assisted error correction
2. Compilation optimization suggestions
3. Cross-agent dependency analysis
4. Visual compilation debugging

## Conclusion

This phased approach addresses all identified compilation issues while maintaining backward compatibility and system stability. Each phase provides independent value and builds toward a more sophisticated compilation system that can handle increasingly complex Playbooks programs.

The implementation prioritizes developer experience with faster iteration cycles, better error messages, and more reliable outcomes. The caching system alone will provide significant improvements for daily development workflows.

By compiling at the agent level, we align the compilation process with the natural boundaries of Playbooks programs, leading to more accurate and scalable compilation that can grow with the framework's adoption.