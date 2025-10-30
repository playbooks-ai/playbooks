import ast


class InjectVar(ast.NodeTransformer):
    """Inject Var calls after all assignments."""

    def visit_AsyncFunctionDef(self, node):
        return self.visit_FunctionDef(node)

    def visit_FunctionDef(self, node):
        # First, recursively visit child nodes
        self.generic_visit(node)

        # Transform the function body
        node.body = self._transform_body(node.body)
        return node

    def visit_If(self, node):
        # First, recursively visit child nodes
        self.generic_visit(node)

        # Transform the if body and orelse
        node.body = self._transform_body(node.body)
        node.orelse = self._transform_body(node.orelse)
        return node

    def visit_While(self, node):
        # First, recursively visit child nodes
        self.generic_visit(node)

        # Transform the while body and orelse
        node.body = self._transform_body(node.body)
        node.orelse = self._transform_body(node.orelse)
        return node

    def visit_For(self, node):
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

    def visit_With(self, node):
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

    def visit_Try(self, node):
        # First, recursively visit child nodes
        self.generic_visit(node)

        # Transform all the try/except/else/finally bodies
        node.body = self._transform_body(node.body)
        for handler in node.handlers:
            handler.body = self._transform_body(handler.body)
        node.orelse = self._transform_body(node.orelse)
        node.finalbody = self._transform_body(node.finalbody)
        return node

    def _transform_body(self, body):
        """Transform a list of statements to inject Var calls after assignments."""
        new_body = []

        for stmt in body:
            new_body.append(stmt)

            # After each assignment, inject Var calls
            if isinstance(stmt, ast.Assign):
                # Handle all targets (e.g., x = y = 10)
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

    def _get_target_names(self, target):
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


def inject_setvar(code):
    """Transform code to inject Var calls after all assignments."""
    tree = ast.parse(code)
    transformer = InjectVar()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)
