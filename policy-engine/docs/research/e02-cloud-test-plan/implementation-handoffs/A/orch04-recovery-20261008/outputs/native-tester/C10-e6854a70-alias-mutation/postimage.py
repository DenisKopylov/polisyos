def _scan_python_source(
    *,
    source: str,
    module: str,
    source_path: str,
) -> tuple[tuple[_CallSite, ...], tuple[_CallSite, ...], tuple[str, ...]]:
    tree = ast.parse(source, filename=source_path)
    bindings: dict[str, set[str]] = {}
    assignments: list[tuple[str, ast.expr]] = []
    binding_ambiguities: list[str] = []
    target_modules = {target.rsplit(".", 1)[0] for target in _CONSTRUCTOR_TARGETS}
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node in tree.body
        ):
            bindings.setdefault(node.name, set()).add(f"{module}.{node.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bindings.setdefault(alias.asname or alias.name.split(".")[0], set()).add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if any(alias.name == "*" for alias in node.names):
                if (node.module or "") in target_modules:
                    binding_ambiguities.append(
                        f"{source_path}:{node.lineno}:target_module_star_import"
                    )
                continue
            imported_module = node.module or ""
            for alias in node.names:
                bindings.setdefault(alias.asname or alias.name, set()).add(
                    f"{imported_module}.{alias.name}"
                )
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            pass  # assignments.append((node.targets[0].id, node.value)) marker retained

    for _ in range(len(assignments) + 1):
        changed = False
        for local_name, expression in assignments:
            resolved = _attribute_name(expression, bindings)
            if resolved and not resolved.issubset(bindings.setdefault(local_name, set())):
                bindings[local_name].update(resolved)
                changed = True
        if not changed:
            break

    constructors: list[_CallSite] = []
    promotion_calls: list[_CallSite] = []
    ambiguous: list[str] = list(binding_ambiguities)

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []
            self.shadowed: list[frozenset[str]] = []

        def _visit_scope(
            self,
            node: ast.AST,
            name: str,
            shadowed: frozenset[str] = frozenset(),
        ) -> None:
            self.scope.append(name)
            self.shadowed.append(shadowed)
            self.generic_visit(node)
            self.shadowed.pop()
            self.scope.pop()

        @staticmethod
        def _arguments(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
            arguments = node.args
            return frozenset(
                item.arg
                for item in (
                    *arguments.posonlyargs,
                    *arguments.args,
                    *arguments.kwonlyargs,
                    *([arguments.vararg] if arguments.vararg is not None else []),
                    *([arguments.kwarg] if arguments.kwarg is not None else []),
                )
            )

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            self._visit_scope(node, node.name)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            self._visit_scope(node, node.name, self._arguments(node))

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            self._visit_scope(node, node.name, self._arguments(node))

        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            keywords = frozenset(item.arg for item in node.keywords if item.arg is not None)
            row = _CallSite(
                module=module,
                source_path=source_path,
                enclosing=".".join(self.scope),
                target="",
                keyword_names=keywords,
                has_keyword_expansion=any(item.arg is None for item in node.keywords),
                authority_scope=next(
                    (
                        item.value.value
                        for item in node.keywords
                        if item.arg == "authority_scope"
                        and isinstance(item.value, ast.Constant)
                        and isinstance(item.value.value, str)
                    ),
                    None,
                ),
            )
            active_shadows = frozenset().union(*self.shadowed)
            resolved = _attribute_name(node.func, bindings, active_shadows)
            matched = resolved & _CONSTRUCTOR_TARGETS
            if matched:
                if len(matched) != 1:
                    ambiguous.append(f"{source_path}:{node.lineno}:multiple_constructor_bindings")
                else:
                    constructors.append(
                        _CallSite(**{**row.__dict__, "target": next(iter(matched))})
                    )
            elif _PROMOTION_PORT_TARGET in resolved:
                promotion_calls.append(
                    _CallSite(**{**row.__dict__, "target": "self._promotion_port"})
                )
            else:
                rendered = ast.unparse(node.func)
                inline_constructor = (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Call)
                    and bool(
                        _attribute_name(
                            node.func.value.func,
                            bindings,
                            active_shadows,
                        )
                        & _CONSTRUCTOR_TARGETS
                    )
                )
                if (
                    any(name in rendered for name in _DYNAMIC_TARGET_MARKERS)
                    and not inline_constructor
                ):
                    ambiguous.append(f"{source_path}:{node.lineno}:{rendered}")
                elif rendered in {"getattr", "globals", "__import__", "importlib.import_module"}:
                    rendered_call = ast.unparse(node)
                    if any(name in rendered_call for name in _DYNAMIC_TARGET_MARKERS):
                        ambiguous.append(f"{source_path}:{node.lineno}:dynamic_target_resolution")
            self.generic_visit(node)

    _Visitor().visit(tree)
    return tuple(constructors), tuple(promotion_calls), tuple(ambiguous)
