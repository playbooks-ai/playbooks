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
        self._collect_assigned_vars(node.body)

        # Then recursively visit child nodes
        self.generic_visit(node)

        # Transform the function body
        node.body = self._transform_body(node.body)

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
            # Transform assignments that read before write (e.g., x = x * 2)
            if isinstance(stmt, ast.Assign):
                transformed_stmts = self._transform_assign_with_read_before_write(stmt)
                new_body.extend(transformed_stmts)

                # After the assignment, inject Var calls
                for target in stmt.targets:
                    for var_name in self._get_target_names(target):
                        new_body.append(self._make_setvar_call(var_name))

            elif isinstance(stmt, ast.AnnAssign):
                new_body.append(stmt)
                # Handle annotated assignments (e.g., x: int = 10)
                if stmt.value is not None:  # Only if there's an actual assignment
                    for var_name in self._get_target_names(stmt.target):
                        new_body.append(self._make_setvar_call(var_name))

            elif isinstance(stmt, ast.AugAssign):
                new_body.append(stmt)
                # Handle augmented assignments (e.g., x += 10)
                for var_name in self._get_target_names(stmt.target):
                    new_body.append(self._make_setvar_call(var_name))

            else:
                new_body.append(stmt)

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

    def _transform_assign_with_read_before_write(self, node):
        """Transform assignments that read from the same variable before writing.

        Transforms:
            x = x * 2
        Into:
            x = globals().get('x', x) if 'x' in locals() else globals()['x'] * 2

        Actually, simpler approach - transform to:
            x = (x if 'x' in locals() else globals()['x']) * 2

        Even simpler - since we pre-populate namespace, just transform to:
            if 'x' not in locals():
                x = globals()['x']
            x = x * 2
        """

        # Check if this assignment reads from any of the assigned variables
        class VarUsageChecker(ast.NodeVisitor):
            def __init__(self, assigned_vars):
                self.assigned_vars = assigned_vars
                self.uses_assigned_var = False

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load) and node.id in self.assigned_vars:
                    self.uses_assigned_var = True

        assigned_names = []
        for target in node.targets:
            assigned_names.extend(self._get_target_names(target))

        checker = VarUsageChecker(set(assigned_names))
        checker.visit(node.value)

        if not checker.uses_assigned_var:
            return [node]

        # Transform: for each assigned variable that's read in the value,
        # add a statement before the assignment to load it from globals if not in locals
        result = []
        for var_name in assigned_names:
            # Create: if 'var_name' not in locals(): var_name = globals()['var_name']
            init_stmt = ast.If(
                test=ast.UnaryOp(
                    op=ast.Not(),
                    operand=ast.Compare(
                        left=ast.Constant(value=var_name),
                        ops=[ast.In()],
                        comparators=[
                            ast.Call(
                                func=ast.Name(id="locals", ctx=ast.Load()),
                                args=[],
                                keywords=[],
                            )
                        ],
                    ),
                ),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=var_name, ctx=ast.Store())],
                        value=ast.Subscript(
                            value=ast.Call(
                                func=ast.Name(id="globals", ctx=ast.Load()),
                                args=[],
                                keywords=[],
                            ),
                            slice=ast.Constant(value=var_name),
                            ctx=ast.Load(),
                        ),
                    )
                ],
                orelse=[],
            )
            result.append(init_stmt)

        result.append(node)
        return result


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
