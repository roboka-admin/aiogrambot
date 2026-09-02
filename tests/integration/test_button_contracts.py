from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ButtonContract:
    kind: str
    key: str
    constraints: tuple[tuple[str, object], ...] = ()
    location: str = ""


@dataclass(frozen=True)
class HandlerContract:
    kind: str
    key: str
    constraints: tuple[tuple[str, object], ...] = ()
    location: str = ""


def _source_files(directory: str) -> list[Path]:
    return sorted((ROOT / directory).glob("*.py"))


def _literal(node: ast.AST | None) -> object | None:
    if isinstance(node, ast.Constant) and isinstance(
        node.value, (str, int, float, bool, type(None))
    ):
        return node.value
    return None


def _literal_values(
    node: ast.AST | None,
    variable_values: dict[str, list[ast.AST]],
    seen: set[str] | None = None,
) -> list[object]:
    """Resolve literal values used indirectly in callback constructor fields."""
    seen = set() if seen is None else seen

    value = _literal(node)
    if value is not None:
        return [value]

    if isinstance(node, ast.Name):
        if node.id in seen or node.id not in variable_values:
            return []
        seen.add(node.id)
        result: list[object] = []
        for assigned_value in variable_values[node.id]:
            result.extend(_literal_values(assigned_value, variable_values, seen.copy()))
        return result

    if isinstance(node, ast.IfExp):
        return _literal_values(node.body, variable_values, seen.copy()) + _literal_values(
            node.orelse, variable_values, seen.copy()
        )

    return []


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _prefixes() -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for path in _source_files("callbacks"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not any(
                _name(base) == "CallbackData" for base in node.bases
            ):
                continue
            for keyword in node.keywords:
                if keyword.arg == "prefix":
                    value = _literal(keyword.value)
                    if isinstance(value, str):
                        prefixes[node.name] = value
    return prefixes


def _callback_contract(
    node: ast.AST,
    prefixes: dict[str, str],
    location: str,
    variable_values: dict[str, list[ast.AST]],
) -> list[ButtonContract]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [ButtonContract("callback_raw", node.value, location=location)]

    call = node
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "pack"
    ):
        call = node.func.value

    if isinstance(call, ast.Call):
        class_name = _name(call.func)
        if class_name in prefixes:
            resolved_constraints: list[list[tuple[str, object]]] = []
            for keyword in call.keywords:
                values = _literal_values(keyword.value, variable_values)
                if values:
                    resolved_constraints.append(
                        [(keyword.arg or "", value) for value in values]
                    )

            contracts = [
                ButtonContract("callback_data", class_name, (), location)
            ]
            for field_constraints in resolved_constraints:
                contracts = [
                    ButtonContract(
                        contract.kind,
                        contract.key,
                        tuple(sorted((*contract.constraints, constraint))),
                        contract.location,
                    )
                    for contract in contracts
                    for constraint in field_constraints
                ]
            return contracts
    return []


def _function_returns(tree: ast.AST) -> dict[str, list[ast.AST]]:
    returns: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            values = [
                child.value for child in ast.walk(node) if isinstance(child, ast.Return)
            ]
            if values:
                returns.setdefault(node.name, []).extend(values)
    return returns


def _variable_values(tree: ast.AST) -> dict[str, list[ast.AST]]:
    """Collect local variable assignments used to build callback_data values."""
    values: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values.setdefault(target.id, []).append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                values.setdefault(node.target.id, []).append(node.value)
    return values


def _callback_contracts(
    node: ast.AST,
    prefixes: dict[str, str],
    location: str,
    function_returns: dict[str, list[ast.AST]],
    variable_values: dict[str, list[ast.AST]],
    seen: set[tuple[str, str]] | None = None,
) -> list[ButtonContract]:
    seen = set() if seen is None else seen

    if isinstance(node, ast.Name):
        variable_name = node.id
        if variable_name in variable_values and ("variable", variable_name) not in seen:
            seen.add(("variable", variable_name))
            result: list[ButtonContract] = []
            for value in variable_values[variable_name]:
                result.extend(
                    _callback_contracts(
                        value,
                        prefixes,
                        location,
                        function_returns,
                        variable_values,
                        seen,
                    )
                )
            return result

    if isinstance(node, ast.IfExp):
        result: list[ButtonContract] = []
        for branch in (node.body, node.orelse):
            result.extend(
                _callback_contracts(
                    branch,
                    prefixes,
                    location,
                    function_returns,
                    variable_values,
                    seen.copy(),
                )
            )
        return result

    if isinstance(node, ast.Call):
        function_name = _name(node.func)
        if function_name in function_returns and ("function", function_name) not in seen:
            seen.add(("function", function_name))
            result: list[ButtonContract] = []
            for value in function_returns[function_name]:
                result.extend(
                    _callback_contracts(
                        value,
                        prefixes,
                        location,
                        function_returns,
                        variable_values,
                        seen,
                    )
                )
            return result

    return _callback_contract(node, prefixes, location, variable_values)


def _button_contracts() -> list[ButtonContract]:
    prefixes = _prefixes()
    result: list[ButtonContract] = []
    for path in _source_files("keyboards"):
        tree = ast.parse(path.read_text(), filename=str(path))
        function_returns = _function_returns(tree)
        variable_values = _variable_values(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _name(node.func)
            kwargs = {keyword.arg: keyword.value for keyword in node.keywords}
            location = f"{path.relative_to(ROOT)}:{node.lineno}"

            if name == "InlineKeyboardButton":
                callback_data = kwargs.get("callback_data")
                if callback_data is not None:
                    contracts = _callback_contracts(
                        callback_data,
                        prefixes,
                        location,
                        function_returns,
                        variable_values,
                    )
                    assert contracts, f"Unsupported callback_data expression at {location}"
                    result.extend(contracts)
            elif name == "KeyboardButton":
                text = _literal(kwargs.get("text"))
                if isinstance(text, str):
                    result.append(ButtonContract("message", text, location=location))
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "button"
            ):
                callback_data = kwargs.get("callback_data")
                if callback_data is not None:
                    contracts = _callback_contracts(
                        callback_data,
                        prefixes,
                        location,
                        function_returns,
                        variable_values,
                    )
                    assert contracts, f"Unsupported callback_data expression at {location}"
                    result.extend(contracts)
    return result


def _constraints_from_filter(node: ast.AST) -> list[tuple[str, object]]:
    constraints: list[tuple[str, object]] = []
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Compare)
            and len(child.ops) == 1
            and isinstance(child.ops[0], ast.Eq)
            and isinstance(child.left, ast.Attribute)
            and isinstance(child.left.value, ast.Name)
            and child.left.value.id == "F"
        ):
            value = _literal(child.comparators[0])
            if value is not None:
                constraints.append((child.left.attr, value))
        elif (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "in_"
        ):
            target = child.func.value
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "F"
                and child.args
                and isinstance(child.args[0], (ast.Set, ast.List, ast.Tuple))
            ):
                values = [
                    value
                    for item in child.args[0].elts
                    if (value := _literal(item)) is not None
                ]
                if values:
                    constraints.append(
                        (target.attr, tuple(sorted(values, key=repr)))
                    )
    return constraints


def _handler_contracts() -> list[HandlerContract]:
    prefixes = _prefixes()
    result: list[HandlerContract] = []
    for path in _source_files("handlers"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if (
                    not isinstance(decorator, ast.Call)
                    or not isinstance(decorator.func, ast.Attribute)
                ):
                    continue
                event_type = decorator.func.attr
                if event_type not in {"callback_query", "message"}:
                    continue

                location = f"{path.relative_to(ROOT)}:{node.lineno} ({node.name})"
                callback_class: str | None = None
                constraints: list[tuple[str, object]] = []
                for argument in decorator.args:
                    if (
                        isinstance(argument, ast.Call)
                        and isinstance(argument.func, ast.Attribute)
                        and argument.func.attr == "filter"
                    ):
                        candidate = _name(argument.func.value)
                        if candidate in prefixes:
                            callback_class = candidate
                        constraints.extend(_constraints_from_filter(argument))
                    else:
                        constraints.extend(_constraints_from_filter(argument))

                if callback_class is not None:
                    result.append(
                        HandlerContract(
                            "callback_data",
                            callback_class,
                            tuple(sorted(constraints)),
                            location,
                        )
                    )
                    continue

                if event_type == "callback_query":
                    for child in ast.walk(decorator):
                        if (
                            isinstance(child, ast.Compare)
                            and len(child.ops) == 1
                            and isinstance(child.ops[0], ast.Eq)
                            and isinstance(child.left, ast.Attribute)
                            and isinstance(child.left.value, ast.Name)
                            and child.left.value.id == "F"
                            and child.left.attr == "data"
                        ):
                            value = _literal(child.comparators[0])
                            if isinstance(value, str):
                                result.append(
                                    HandlerContract(
                                        "callback_raw", value, (), location
                                    )
                                )
                else:
                    for child in ast.walk(decorator):
                        if (
                            isinstance(child, ast.Compare)
                            and len(child.ops) == 1
                            and isinstance(child.ops[0], ast.Eq)
                            and isinstance(child.left, ast.Attribute)
                            and isinstance(child.left.value, ast.Name)
                            and child.left.value.id == "F"
                            and child.left.attr == "text"
                        ):
                            value = _literal(child.comparators[0])
                            if isinstance(value, str):
                                result.append(
                                    HandlerContract(
                                        "message", value, (), location
                                    )
                                )
    return result


def _matches(button: ButtonContract, handler: HandlerContract) -> bool:
    if button.kind != handler.kind or button.key != handler.key:
        return False
    button_constraints = dict(button.constraints)
    for field, expected in handler.constraints:
        if field not in button_constraints:
            return False
        actual = button_constraints[field]
        if isinstance(expected, tuple):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def test_every_keyboard_action_has_a_matching_handler():
    buttons = _button_contracts()
    handlers = _handler_contracts()
    missing = [
        f"{button.kind} '{button.key}' at {button.location}"
        for button in buttons
        if not any(_matches(button, handler) for handler in handlers)
    ]
    assert not missing, (
        "Buttons without a matching handler:\n- " + "\n- ".join(missing)
    )


def test_no_duplicate_conflicting_callback_handlers():
    handlers = [
        handler
        for handler in _handler_contracts()
        if handler.kind in {"callback_data", "callback_raw"}
    ]
    seen: dict[tuple[str, str, tuple[tuple[str, object], ...]], str] = {}
    duplicates: list[str] = []
    for handler in handlers:
        key = (handler.kind, handler.key, handler.constraints)
        if key in seen:
            duplicates.append(f"{handler.location} duplicates {seen[key]}")
        else:
            seen[key] = handler.location
    assert not duplicates, (
        "Conflicting duplicate callback handlers:\n- "
        + "\n- ".join(duplicates)
    )


def _included_handler_modules() -> set[str]:
    tree = ast.parse(
        (ROOT / "main.py").read_text(),
        filename=str(ROOT / "main.py"),
    )
    return {
        node.module
        for node in tree.body
        if (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("handlers.")
            and any(alias.name == "router" for alias in node.names)
        )
    }


def test_every_handler_router_is_included_in_main():
    handler_modules = {
        f"handlers.{path.stem}"
        for path in _source_files("handlers")
        if path.name != "__init__.py"
    }
    missing = sorted(handler_modules - _included_handler_modules())
    assert not missing, (
        "Handler routers not included in main.py:\n- "
        + "\n- ".join(missing)
    )
