"""AST transformer for injecting variable tracking calls.

This module provides functionality to transform Python AST to automatically
inject Var() calls after variable assignments, enabling runtime variable
tracking in playbook execution.
"""

import ast
from typing import List, Set


class InjectVar(ast.NodeTransformer):
    """Inject Var calls after all assignments."""

    def __init__(self) -> None:
        super().__init__()
        self.assigned_vars: Set[str] = (
            set()
        )  # Track variables assigned in current scope

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef:
        return self.visit_FunctionDef(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        # Save the current assigned_vars set and start fresh for this function scope
        saved_assigned_vars = self.assigned_vars
        self.assigned_vars = set()

        # First, collect all assigned variables in this function
        assigned_in_function = self._collect_assigned_vars(node.body)

        # Add initialization statements at the top of the function for variables
        # that are assigned anywhere in the function. This prevents UnboundLocalError
        # when reading a variable before it's assigned (since Python marks any
        # assigned variable as local for the entire function scope).
        init_stmts = []
        for var_name in sorted(assigned_in_function):  # Sort for deterministic output
            # Create: var_name = globals().get('var_name')
            # Using .get() returns None if not found, which is better than KeyError
            init_stmt = ast.Assign(
                targets=[ast.Name(id=var_name, ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Call(
                            func=ast.Name(id="globals", ctx=ast.Load()),
                            args=[],
                            keywords=[],
                        ),
                        attr="get",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(value=var_name)],
                    keywords=[],
                ),
            )
            init_stmts.append(init_stmt)

        # Then recursively visit child nodes
        self.generic_visit(node)

        # Transform the function body
        transformed_body = self._transform_body(node.body)

        # Prepend initialization statements
        node.body = init_stmts + transformed_body

        # Restore the parent scope's assigned_vars
        self.assigned_vars = saved_assigned_vars
        return node

    def visit_If(self, node: ast.If) -> ast.If:
        # First, recursively visit child nodes
        self.generic_visit(node)

        # Transform the if body and orelse
        node.body = self._transform_body(node.body)
        node.orelse = self._transform_body(node.orelse)
        return node

    def visit_While(self, node: ast.While) -> ast.While:
        # First, recursively visit child nodes
        self.generic_visit(node)

        # Transform the while body and orelse
        node.body = self._transform_body(node.body)
        node.orelse = self._transform_body(node.orelse)
        return node

    def visit_For(self, node: ast.For) -> ast.For:
        # First, recursively visit child nodes
        self.generic_visit(node)

        # Transform the for body and orelse
        node.body = self._transform_body(node.body)
        node.orelse = self._transform_body(node.orelse)

        # Handle for loop variables (e.g., for x in range(10))
        for var_name in self._get_target_names(node.target):
            # Insert Var at the beginning of the loop body
            setvar_call = self._make_setvar_call(var_name)
            node.body.insert(0, setvar_call)

        return node

    def visit_With(self, node: ast.With) -> ast.With:
        # First, recursively visit child nodes
        self.generic_visit(node)

        # Transform the with body
        node.body = self._transform_body(node.body)

        # Handle with statement variables (e.g., with open() as f)
        for item in node.items:
            if item.optional_vars:
                for var_name in self._get_target_names(item.optional_vars):
                    # Insert Var at the beginning of the with body
                    setvar_call = self._make_setvar_call(var_name)
                    node.body.insert(0, setvar_call)

        return node

    def visit_Try(self, node: ast.Try) -> ast.Try:
        # First, recursively visit child nodes
        self.generic_visit(node)

        # Transform all the try/except/else/finally bodies
        node.body = self._transform_body(node.body)
        for handler in node.handlers:
            handler.body = self._transform_body(handler.body)
        node.orelse = self._transform_body(node.orelse)
        node.finalbody = self._transform_body(node.finalbody)
        return node

    def _transform_body(self, body: List[ast.stmt]) -> List[ast.stmt]:
        """Transform a list of statements to inject Var calls after assignments."""
        new_body = []

        for stmt in body:
            # Add the statement first
            new_body.append(stmt)

            # Then inject Var calls after assignments
            if isinstance(stmt, ast.Assign):
                # After the assignment, inject Var calls
                for target in stmt.targets:
                    for var_name in self._get_target_names(target):
                        new_body.append(self._make_setvar_call(var_name))

            elif isinstance(stmt, ast.AnnAssign):
                # Handle annotated assignments (e.g., x: int = 10)
                if stmt.value is not None:  # Only if there's an actual assignment
                    for var_name in self._get_target_names(stmt.target):
                        new_body.append(self._make_setvar_call(var_name))

            elif isinstance(stmt, ast.AugAssign):
                # Handle augmented assignments (e.g., x += 10)
                for var_name in self._get_target_names(stmt.target):
                    new_body.append(self._make_setvar_call(var_name))

        return new_body

    def _get_target_names(self, target: ast.expr) -> List[str]:
        """Extract variable names from an assignment target."""
        if isinstance(target, ast.Name):
            return [target.id]
        elif isinstance(target, (ast.Tuple, ast.List)):
            names = []
            for elt in target.elts:
                names.extend(self._get_target_names(elt))
            return names
        elif isinstance(target, ast.Starred):
            return self._get_target_names(target.value)
        # Ignore attributes, subscripts (obj.x = 1, obj[0] = 1)
        return []

    def _make_setvar_call(self, var_name):
        """Create: await Var('var_name', var_name)"""
        return ast.Expr(
            value=ast.Await(
                value=ast.Call(
                    func=ast.Name(id="Var", ctx=ast.Load()),
                    args=[
                        ast.Constant(value=var_name),
                        ast.Name(id=var_name, ctx=ast.Load()),
                    ],
                    keywords=[],
                )
            )
        )

    def _collect_assigned_vars(self, body):
        """Collect all variables that are assigned in this body."""

        class AssignedVarCollector(ast.NodeVisitor):
            def __init__(self):
                self.assigned = set()

            def visit_Assign(self, node):
                for target in node.targets:
                    self._add_target_names(target)
                self.generic_visit(node)

            def visit_AnnAssign(self, node):
                if node.value is not None:
                    self._add_target_names(node.target)
                self.generic_visit(node)

            def visit_AugAssign(self, node):
                self._add_target_names(node.target)
                self.generic_visit(node)

            def visit_For(self, node):
                self._add_target_names(node.target)
                self.generic_visit(node)

            def visit_With(self, node):
                for item in node.items:
                    if item.optional_vars:
                        self._add_target_names(item.optional_vars)
                self.generic_visit(node)

            def _add_target_names(self, target):
                if isinstance(target, ast.Name):
                    self.assigned.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for elt in target.elts:
                        self._add_target_names(elt)
                elif isinstance(target, ast.Starred):
                    self._add_target_names(target.value)

        collector = AssignedVarCollector()
        for stmt in body:
            collector.visit(stmt)
        return collector.assigned


def inject_setvar(code: str) -> str:
    """Transform code to inject Var calls after all assignments.

    Args:
        code: Python source code to transform

    Returns:
        Transformed code with Var() calls injected after assignments
    """
    tree = ast.parse(code)
    transformer = InjectVar()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)
