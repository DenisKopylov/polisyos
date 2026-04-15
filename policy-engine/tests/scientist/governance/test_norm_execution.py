"""
Phase 18 Tests: Safe Expression Evaluation

Test Categories:
1. SECURITY - Verify forbidden constructs are rejected
2. POLICY - Verify ASTPolicy validation rules
3. EVALUATION - Verify correct evaluation logic
4. BACKEND - Verify ExpressionASTBackend integration
5. EDGE_CASES - Division by zero, missing variables, etc.
"""
from __future__ import annotations

import pytest

from polisyos.core.governance.legal.ast_policy import (
    ASTLimits,
    ASTPolicy,
    SecurityError,
)
from polisyos.core.governance.legal.backends.expr_ast import (
    ExpressionASTBackend,
    SafeExpressionEvaluator,
)
from polisyos.core.governance.passes.base import IssueSeverity
from polisyos.ir.norm_pack import NormPack, NormRule, NormRef, RuleType


class TestSecurityRejection:
    """Verify that dangerous constructs are rejected."""

    @pytest.mark.parametrize("malicious_expr,attack_name", [
        ("__import__('os').system('echo hack')", "import_attack"),
        ("eval('1+1')", "eval_attack"),
        ("exec('x=1')", "exec_attack"),
        ("open('/etc/passwd').read()", "file_attack"),
        ("print('hello')", "print_call"),
        ("len([1,2,3])", "builtin_call"),
        ("max(1, 2)", "max_call"),
        ("list(range(10))", "constructor_call"),
        ("x.__class__.__bases__[0].__subclasses__()", "class_escape"),
        ("''.__class__.__mro__[1].__subclasses__()", "string_escape"),
        ("x.__dict__", "dict_access"),
        ("x.method()", "method_call"),
        ("globals()['__builtins__']", "globals_access"),
        ("x[0]", "subscript"),
        ("{'a': 1}['a']", "dict_subscript"),
        ("import os", "import_statement"),
        ("from os import system", "from_import"),
        ("while True: pass", "infinite_loop"),
        ("for i in range(10**9): pass", "billion_loop"),
        ("[x for x in range(10)]", "list_comp"),
        ("{x for x in range(10)}", "set_comp"),
        ("{x: x for x in range(10)}", "dict_comp"),
        ("(x for x in range(10))", "generator"),
        ("lambda: 1", "lambda"),
        ("(lambda: 1)()", "iife_lambda"),
        ("(x := 1)", "walrus"),
        ("f'{__import__(\"os\")}'", "fstring_import"),
    ])
    def test_rejects_malicious_expression(
        self,
        malicious_expr: str,
        attack_name: str,
    ) -> None:
        """Ensure malicious expressions are rejected during validation."""
        is_valid, error = ASTPolicy.validate(malicious_expr)

        assert not is_valid, (
            f"SECURITY FAILURE: {attack_name} should be rejected!\n"
            f"Expression: {malicious_expr}"
        )
        assert error is not None

    def test_rejects_dunder_names(self) -> None:
        """Block access to dunder attributes."""
        is_valid, error = ASTPolicy.validate("__builtins__")
        assert not is_valid
        assert "Dunder names forbidden" in error

    def test_evaluator_validates_before_execution(self) -> None:
        """Ensure evaluator doesn't execute invalid expressions."""
        evaluator = SafeExpressionEvaluator({"x": 1})

        with pytest.raises(SecurityError):
            evaluator.evaluate("__import__('os')")


class TestASTPolicy:
    """Test ASTPolicy validation rules."""

    def test_accepts_valid_expressions(self) -> None:
        """Valid expressions should pass validation."""
        valid_exprs = [
            "x > 10",
            "x == y",
            "a and b",
            "a or b or c",
            "not x",
            "x + y - z",
            "x * y / z",
            "(x > 0) and (y < 100)",
            "x >= 0 and x <= 100",
            "a < b < c",
            "1 + 2 + 3",
            "True and False",
            "-x",
            "x % 4 == 0",
        ]

        for expr in valid_exprs:
            is_valid, error = ASTPolicy.validate(expr)
            assert is_valid, f"Should accept: {expr}, error: {error}"

    def test_rejects_too_many_nodes(self) -> None:
        """Expressions with too many nodes should be rejected."""
        big_expr = " or ".join([f"x{i}" for i in range(50)])

        limits = ASTLimits(MAX_NODES=20)
        is_valid, error = ASTPolicy.validate(big_expr, limits=limits)

        assert not is_valid
        assert "too complex" in error.lower()

    def test_rejects_too_deep_nesting(self) -> None:
        """Deeply nested expressions should be rejected."""
        deep_expr = "not " * 12 + "x"

        limits = ASTLimits(MAX_DEPTH=5)
        is_valid, error = ASTPolicy.validate(deep_expr, limits=limits)

        assert not is_valid
        assert "too deeply nested" in error.lower()

    def test_rejects_too_many_names(self) -> None:
        """Expressions with too many unique variables should be rejected."""
        many_names = " and ".join([f"var{i}" for i in range(30)])

        limits = ASTLimits(MAX_NAMES=10)
        is_valid, error = ASTPolicy.validate(many_names, limits=limits)

        assert not is_valid
        assert "Too many unique variables" in error

    def test_rejects_too_long_expression(self) -> None:
        """Very long expressions should be rejected."""
        long_expr = "x " + "+ x " * 500

        limits = ASTLimits(MAX_EXPRESSION_LENGTH=100)
        is_valid, error = ASTPolicy.validate(long_expr, limits=limits)

        assert not is_valid
        assert "too long" in error.lower()

    def test_extract_names(self) -> None:
        """Should correctly extract variable names."""
        names = ASTPolicy.extract_names("x > 10 and y < z")
        assert names == {"x", "y", "z"}


class TestSafeExpressionEvaluator:
    """Test SafeExpressionEvaluator logic."""

    @pytest.fixture
    def context(self) -> dict:
        return {
            "x": 10,
            "y": 5,
            "z": 3,
            "flag": True,
            "name": "test",
            "rate": 0.05,
            "budget_deficit_pct": 2.5,
            "has_budget_data": True,
        }

    def test_and_operation(self, context: dict) -> None:
        evaluator = SafeExpressionEvaluator(context)
        assert evaluator.evaluate("x > 5 and y > 3") is True
        assert evaluator.evaluate("x > 5 and y > 10") is False

    def test_or_operation(self, context: dict) -> None:
        evaluator = SafeExpressionEvaluator(context)
        assert evaluator.evaluate("x > 100 or y > 3") is True
        assert evaluator.evaluate("x > 100 or y > 100") is False

    def test_not_operation(self, context: dict) -> None:
        evaluator = SafeExpressionEvaluator(context)
        assert evaluator.evaluate("not flag") is False
        assert evaluator.evaluate("not (x < 5)") is True

    def test_complex_boolean(self, context: dict) -> None:
        evaluator = SafeExpressionEvaluator(context)
        assert evaluator.evaluate("(x > 5 or y < 0) and not (z == 0)") is True

    def test_comparisons(self, context: dict) -> None:
        evaluator = SafeExpressionEvaluator(context)

        assert evaluator.evaluate("x == 10") is True
        assert evaluator.evaluate("x != 10") is False
        assert evaluator.evaluate("x < 20") is True
        assert evaluator.evaluate("x <= 10") is True
        assert evaluator.evaluate("x > 5") is True
        assert evaluator.evaluate("x >= 10") is True

    def test_chained_comparison(self, context: dict) -> None:
        """Test Python's chained comparisons: a < b < c"""
        evaluator = SafeExpressionEvaluator(context)

        assert evaluator.evaluate("0 < x < 20") is True
        assert evaluator.evaluate("0 < x < 5") is False
        assert evaluator.evaluate("z < y < x") is True

    def test_arithmetic(self, context: dict) -> None:
        evaluator = SafeExpressionEvaluator(context)

        assert evaluator.evaluate("x + y") == 15
        assert evaluator.evaluate("x - y") == 5
        assert evaluator.evaluate("x * y") == 50
        assert evaluator.evaluate("x / y") == 2.0
        assert evaluator.evaluate("x // z") == 3
        assert evaluator.evaluate("x % z") == 1

    def test_unary_minus(self, context: dict) -> None:
        evaluator = SafeExpressionEvaluator(context)
        assert evaluator.evaluate("-x") == -10
        assert evaluator.evaluate("-x + y") == -5

    def test_literals(self, context: dict) -> None:
        evaluator = SafeExpressionEvaluator(context)

        assert evaluator.evaluate("True") is True
        assert evaluator.evaluate("False") is False
        assert evaluator.evaluate("42") == 42
        assert evaluator.evaluate("3.14") == 3.14

    def test_budget_check(self, context: dict) -> None:
        """Test realistic budget compliance check."""
        evaluator = SafeExpressionEvaluator(context)

        assert evaluator.evaluate("budget_deficit_pct < 3.0") is True
        assert evaluator.evaluate(
            "has_budget_data and budget_deficit_pct <= 3.0"
        ) is True

    def test_mixed_chained_comparison(self, context: dict) -> None:
        evaluator = SafeExpressionEvaluator(context)
        assert evaluator.evaluate("0 < z < y <= x") is True

    def test_ast_cache_is_bounded(self, context: dict) -> None:
        evaluator = SafeExpressionEvaluator(context, cache_maxsize=2)

        evaluator.evaluate("x > 1")
        evaluator.evaluate("y > 1")
        evaluator.evaluate("z > 1")

        assert len(evaluator._ast_cache) == 2  # noqa: SLF001 - cache policy regression test


class TestEdgeCases:
    """Test error handling and edge cases."""

    def test_missing_variable(self) -> None:
        """Missing variables should raise ValueError, not KeyError."""
        evaluator = SafeExpressionEvaluator({"x": 10})

        with pytest.raises(ValueError) as exc_info:
            evaluator.evaluate("missing_var > 0")

        assert "Unknown variable" in str(exc_info.value)
        assert "missing_var" in str(exc_info.value)

    def test_division_by_zero(self) -> None:
        """Division by zero should raise ValueError."""
        evaluator = SafeExpressionEvaluator({"x": 10, "y": 0})

        with pytest.raises(ValueError) as exc_info:
            evaluator.evaluate("x / y")

        assert "Division by zero" in str(exc_info.value)

    def test_modulo_by_zero(self) -> None:
        """Modulo by zero should raise ValueError."""
        evaluator = SafeExpressionEvaluator({"x": 10, "y": 0})

        with pytest.raises(ValueError) as exc_info:
            evaluator.evaluate("x % y")

        assert "Modulo by zero" in str(exc_info.value)

    def test_empty_expression(self) -> None:
        """Empty expressions should be rejected."""
        is_valid, error = ASTPolicy.validate("")
        assert not is_valid
        assert "non-empty" in error.lower()

    def test_none_expression(self) -> None:
        """None expressions should be rejected."""
        is_valid, _error = ASTPolicy.validate(None)  # type: ignore
        assert not is_valid

    def test_syntax_error(self) -> None:
        """Syntax errors should be caught during validation."""
        is_valid, error = ASTPolicy.validate("x >>>> y")
        assert not is_valid
        assert "Syntax error" in error


class TestExpressionASTBackend:
    """Test ExpressionASTBackend integration."""

    @pytest.fixture
    def sample_norm_pack(self) -> NormPack:
        return NormPack(
            pack_id="test_pack",
            jurisdiction="TEST",
            norms=[
                NormRule(
                    norm_id="deficit_limit",
                    rule_type=RuleType.PROHIBITION,
                    description="Deficit must not exceed 3%",
                    backend_refs=["expr_ast"],
                    backend_metadata={
                        "when": "has_budget_data",
                        "must_not": "deficit_pct > 3.0",
                    },
                ),
                NormRule(
                    norm_id="min_wage",
                    rule_type=RuleType.OBLIGATION,
                    description="Minimum wage must meet federal floor",
                    backend_refs=["expr_ast"],
                    backend_metadata={
                        "when": "has_wage_policy",
                        "must": "min_wage >= federal_min",
                    },
                ),
            ],
        )

    def test_compliant_context(self, sample_norm_pack: NormPack) -> None:
        """No issues when all conditions are met."""
        backend = ExpressionASTBackend()

        context = {
            "has_budget_data": True,
            "deficit_pct": 2.0,
            "has_wage_policy": True,
            "min_wage": 15.0,
            "federal_min": 7.25,
        }

        issues = backend.evaluate(sample_norm_pack, context)
        blockers = [i for i in issues if i.severity == IssueSeverity.BLOCKER]

        assert len(blockers) == 0

    def test_violation_detected(self, sample_norm_pack: NormPack) -> None:
        """Violations should generate BLOCKER issues."""
        backend = ExpressionASTBackend()

        context = {
            "has_budget_data": True,
            "deficit_pct": 5.0,
            "has_wage_policy": True,
            "min_wage": 15.0,
            "federal_min": 7.25,
        }

        issues = backend.evaluate(sample_norm_pack, context)
        blockers = [i for i in issues if i.severity == IssueSeverity.BLOCKER]

        assert len(blockers) == 1
        assert blockers[0].code == "deficit_limit"
        assert "Prohibition violated" in blockers[0].message

    def test_rule_not_applicable(self, sample_norm_pack: NormPack) -> None:
        """Rules should not trigger when 'when' condition is false."""
        backend = ExpressionASTBackend()

        context = {
            "has_budget_data": False,
            "deficit_pct": 99.0,
            "has_wage_policy": False,
            "min_wage": 0.0,
            "federal_min": 100.0,
        }

        issues = backend.evaluate(sample_norm_pack, context)
        blockers = [i for i in issues if i.severity == IssueSeverity.BLOCKER]

        assert len(blockers) == 0

    def test_ignores_non_expr_ast_norms(self) -> None:
        """Backend should skip norms that don't reference it."""
        pack = NormPack(
            pack_id="mixed_pack",
            jurisdiction="TEST",
            norms=[
                NormRule(
                    norm_id="llm_only",
                    rule_type=RuleType.OBLIGATION,
                    description="Complex norm for LLM backend",
                    backend_refs=["llm"],
                    backend_metadata={"legal_text": "Complex interpretation needed"},
                ),
            ],
        )

        backend = ExpressionASTBackend()
        issues = backend.evaluate(pack, {"x": 1})

        assert len(issues) == 0

    def test_handles_none_norm_pack(self) -> None:
        """Backend should handle None NormPack gracefully."""
        backend = ExpressionASTBackend()
        issues = backend.evaluate(None, {"x": 1})
        assert issues == []

    def test_handles_empty_norm_pack(self) -> None:
        """Backend should handle empty NormPack gracefully."""
        pack = NormPack(pack_id="empty", jurisdiction="TEST", norms=[])
        backend = ExpressionASTBackend()
        issues = backend.evaluate(pack, {"x": 1})
        assert issues == []


class TestRegressions:
    """Regression tests for previously discovered issues."""

    def test_short_circuit_and(self) -> None:
        """Verify short-circuit evaluation for 'and'."""
        evaluator = SafeExpressionEvaluator({
            "should_check": False,
        })

        result = evaluator.evaluate("should_check and missing_var")
        assert result is False

    def test_short_circuit_or(self) -> None:
        """Verify short-circuit evaluation for 'or'."""
        evaluator = SafeExpressionEvaluator({
            "already_true": True,
        })

        result = evaluator.evaluate("already_true or missing_var")
        assert result is True

    def test_ast_cache_isolation(self) -> None:
        """Ensure AST cache doesn't leak between contexts."""
        eval1 = SafeExpressionEvaluator({"x": 10})
        eval2 = SafeExpressionEvaluator({"x": 20})

        assert eval1.evaluate("x") == 10
        assert eval2.evaluate("x") == 20
