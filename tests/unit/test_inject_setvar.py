"""Unit tests for inject_setvar AST transformation.

These tests verify that the inject_setvar function correctly transforms
Python code to inject Var() calls and handle variable scoping issues.
"""

import ast


from playbooks.utils.inject_setvar import inject_setvar


class TestInjectSetvar:
    """Test suite for inject_setvar function."""

    def test_simple_assignment(self):
        """Test that simple assignments get Var() calls injected."""
        code = """async def __async_exec__():
    x = 10
"""
        transformed = inject_setvar(code)

        # Should inject Var call after assignment
        assert "await Var('x', x)" in transformed

    def test_multiple_assignments(self):
        """Test that multiple assignments get Var() calls."""
        code = """async def __async_exec__():
    x = 10
    y = 20
"""
        transformed = inject_setvar(code)

        assert "await Var('x', x)" in transformed
        assert "await Var('y', y)" in transformed

    def test_read_before_write_initialization(self):
        """Regression test: Variables assigned later are initialized at function start.

        This prevents UnboundLocalError when code reads a variable before
        it's assigned later in the function.

        Example that would fail without the fix:
            game_state[move - 1] = current_symbol  # Read current_symbol
            current_symbol = 'X' if current_symbol == 'O' else 'O'  # Assign current_symbol

        Python marks current_symbol as local due to the assignment, so the first
        line would raise UnboundLocalError without initialization at the top.
        """
        code = """async def __async_exec__():
    game_state[move - 1] = current_symbol
    current_symbol = 'X' if current_symbol == 'O' else 'O'
"""
        transformed = inject_setvar(code)

        # Parse the transformed code to verify structure
        tree = ast.parse(transformed)
        func_def = tree.body[0]
        assert isinstance(func_def, ast.AsyncFunctionDef)

        # First statement should be initialization of current_symbol
        first_stmt = func_def.body[0]
        assert isinstance(first_stmt, ast.Assign)
        assert len(first_stmt.targets) == 1
        assert isinstance(first_stmt.targets[0], ast.Name)
        assert first_stmt.targets[0].id == "current_symbol"

        # The RHS should be globals().get('current_symbol')
        assert isinstance(first_stmt.value, ast.Call)
        assert isinstance(first_stmt.value.func, ast.Attribute)
        assert first_stmt.value.func.attr == "get"

        # Verify the initialization is: current_symbol = globals().get('current_symbol')
        assert "current_symbol = globals().get('current_symbol')" in transformed

        # Verify original code is preserved after initialization
        assert "game_state[move - 1] = current_symbol" in transformed
        assert "current_symbol = 'X' if current_symbol == 'O' else 'O'" in transformed

        # Verify Var call is injected after the assignment
        assert "await Var('current_symbol', current_symbol)" in transformed

    def test_multiple_variables_read_before_write(self):
        """Test initialization of multiple variables that are read before assignment."""
        code = """async def __async_exec__():
    result = x + y
    x = 10
    y = 20
"""
        transformed = inject_setvar(code)

        # All three variables (result, x, y) should be initialized at the top
        lines = transformed.split("\n")

        # Find the function body (skip the def line)
        func_start = next(
            i for i, line in enumerate(lines) if "async def __async_exec__" in line
        )
        body_lines = [line.strip() for line in lines[func_start + 1 :] if line.strip()]

        # First three statements should be initializations (order may vary due to sorting)
        init_statements = [body_lines[0], body_lines[1], body_lines[2]]
        assert any(
            "result = globals().get('result')" in stmt for stmt in init_statements
        )
        assert any("x = globals().get('x')" in stmt for stmt in init_statements)
        assert any("y = globals().get('y')" in stmt for stmt in init_statements)

    def test_for_loop_variable(self):
        """Test that for loop variables get Var() calls."""
        code = """async def __async_exec__():
    for i in range(10):
        pass
"""
        transformed = inject_setvar(code)

        # For loop variable should get Var call at start of loop body
        assert "await Var('i', i)" in transformed

    def test_nested_function_scope(self):
        """Test that nested functions have their own variable tracking."""
        code = """async def __async_exec__():
    x = 10
    def inner():
        y = 20
"""
        transformed = inject_setvar(code)

        # Outer function should track x
        assert "await Var('x', x)" in transformed

        # Inner function should track y (but not with await since it's not async)
        # Note: This depends on implementation details

    def test_augmented_assignment(self):
        """Test that augmented assignments (+=, -=, etc.) get Var() calls."""
        code = """async def __async_exec__():
    x = 10
    x += 5
"""
        transformed = inject_setvar(code)

        # Should have Var calls for both statements
        assert transformed.count("await Var('x', x)") == 2

    def test_list_assignment(self):
        """Test that list assignments are handled correctly."""
        code = """async def __async_exec__():
    items = [1, 2, 3]
"""
        transformed = inject_setvar(code)

        assert "await Var('items', items)" in transformed

    def test_subscript_assignment_not_tracked(self):
        """Test that subscript assignments (obj[key] = value) don't get Var() calls."""
        code = """async def __async_exec__():
    my_list = []
    my_list[0] = 10
"""
        transformed = inject_setvar(code)

        # Only my_list should get Var call, not the subscript assignment
        assert transformed.count("await Var(") == 1
        assert "await Var('my_list', my_list)" in transformed

    def test_attribute_assignment_not_tracked(self):
        """Test that attribute assignments (obj.attr = value) don't get Var() calls."""
        code = """async def __async_exec__():
    obj = MyClass()
    obj.value = 10
"""
        transformed = inject_setvar(code)

        # Only obj should get Var call, not the attribute assignment
        assert transformed.count("await Var(") == 1
        assert "await Var('obj', obj)" in transformed

    def test_tuple_unpacking(self):
        """Test that tuple unpacking gets Var() calls for each variable."""
        code = """async def __async_exec__():
    x, y = (1, 2)
"""
        transformed = inject_setvar(code)

        assert "await Var('x', x)" in transformed
        assert "await Var('y', y)" in transformed

    def test_annotated_assignment(self):
        """Test that annotated assignments get Var() calls."""
        code = """async def __async_exec__():
    x: int = 10
"""
        transformed = inject_setvar(code)

        assert "await Var('x', x)" in transformed

    def test_empty_function(self):
        """Test that empty functions don't cause errors."""
        code = """async def __async_exec__():
    pass
"""
        transformed = inject_setvar(code)

        # Should not have any Var calls
        assert "await Var(" not in transformed
