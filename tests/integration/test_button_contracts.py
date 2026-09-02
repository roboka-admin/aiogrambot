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
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not any(_name(base) == "CallbackData" for base in node.bases):
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
) -> ButtonContract | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return ButtonContract("callback", node.value, location=location)

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
            constraints: list[tuple[str, object]] = []
            for keyword in call.keywords:
                value = _literal(keyword.value)
                if value is not None:
                    constraints.append((keyword.arg or "", value))
            return ButtonContract(
                "callback",
                prefixes[class_name],
                tuple(sorted(constraints)),
                location,
            )

    return None


def _local_assignments(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, list[ast.AST]]:
    assignments: dict[str, list[ast.AST]] = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue

        for target in targets:
            if isinstance(target, ast.Name):
                assignments.setdefault(target.id, []).append(node.value)
    return assignments


def _callback_contracts(
    node: ast.AST,
    prefixes: dict[str, str],
    location: str,
    assignments: dict[str, list[ast.AST]],
) -> list[ButtonContract]:
    if isinstance(node, ast.Name) and node.id in assignments:
        contracts: list[ButtonContract] = []
        for value in assignments[node.id]:
            contracts.extend(
                _callback_contracts(value, prefixes, location, assignments)
            )
        return contracts

    contract = _callback_contract(node, prefixes, location)
    return [contract] if contract is not None else []


def _button_contracts() -> list[ButtonContract]:
    prefixes = _prefixes()
    result: list[ButtonContract] = []

    for path in _source_files("keyboards"):
        tree = ast.parse(path.read_text(), filename=str(path))
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        scopes: list[tuple[ast.AST, dict[str, list[ast.AST]]]] = [(tree, {})]
        scopes.extend(
            (function, _local_assignments(function)) for function in functions
        )

        for scope, assignments in scopes:
            for node in ast.walk(scope):
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
                            assignments,
                        )
                        assert contracts, (
                            "Unsupported callback_data expression at "
                            f"{location}"
                        )
                        result.extend(contracts)

                elif name == "KeyboardButton":
                    text = (
                        _literal(kwargs.get("text"))
                        if kwargs.get("text") is not None
                        else None
                    )
                    if isinstance(text, str):
                        result.append(
                            ButtonContract("message", text, location=location)
                        )

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
                            assignments,
                        )
                        assert contracts, (
                            "Unsupported callback_data expression at "
                            f"{location}"
                        )
                        result.extend(contracts)

    unique: dict[
        tuple[str, str, tuple[tuple[str, object], ...], str], ButtonContract
    ] = {}
    for button in result:
        unique[(button.kind, button.key, button.constraints, button.location)] = button
    return list(unique.values())


def _constraints_from_filter(node: ast.AST) -> list[tuple[str, object]]:
    constraints: list[tuple[str, object]] = []
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Compare)
            and len(child.ops) == 1
            and isinstance(child.ops[0], ast.Eq)
        ):
            if (
                isinstance(child.left, ast.Attribute)
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
            ):
                values: list[object] = []
                if child.args and isinstance(
                    child.args[0], (ast.Set, ast.List, ast.Tuple)
                ):
                    for item in child.args[0].elts:
                        value = _literal(item)
                        if value is not None:
                            values.append(value)
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
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                event_type = decorator.func.attr
                if event_type not in {"callback_query", "message"}:
                    continue

                kind = "callback" if event_type == "callback_query" else "message"
                location = f"{path.relative_to(ROOT)}:{node.lineno} ({node.name})"
                extracted: list[tuple[str, object]] = []

                for argument in decorator.args:
                    if (
                        isinstance(argument, ast.Call)
                        and isinstance(argument.func, ast.Attribute)
                        and argument.func.attr == "filter"
                    ):
                        callback_class = _name(argument.func.value)
                        if callback_class in prefixes:
                            extracted.append(("__callback_class__", callback_class))
                            extracted.extend(_constraints_from_filter(argument))
                    elif kind == "callback":
                        extracted.extend(_constraints_from_filter(argument))

                callback_class = next(
                    (
                        value
                        for key, value in extracted
                        if key == "__callback_class__"
                    ),
                    None,
                )
                constraints = tuple(
                    sorted(
                        (
                            key,
                            value,
                        )
                        for key, value in extracted
                        if key != "__callback_class__"
                    )
                )

                if callback_class is not None:
                    result.append(
                        HandlerContract(
                            "callback",
                            prefixes[callback_class],
                            constraints,
                            location,
                        )
                    )
                elif kind == "callback":
                    for child in ast.walk(decorator):
                        if (
                            isinstance(child, ast.Compare)
                            and len(child.ops) == 1
                            and isinstance(child.ops[0], ast.Eq)
                        ):
                            if (
                                isinstance(child.left, ast.Attribute)
                                and isinstance(child.left.value, ast.Name)
                                and child.left.value.id == "F"
                                and child.left.attr == "data"
                            ):
                                value = _literal(child.comparators[0])
                                if isinstance(value, str):
                                    result.append(
                                        HandlerContract(
                                            "callback", value, (), location
                                        )
                                    )
                else:
                    for child in ast.walk(decorator):
                        if (
                            isinstance(child, ast.Compare)
                            and len(child.ops) == 1
                            and isinstance(child.ops[0], ast.Eq)
                        ):
                            if (
                                isinstance(child.left, ast.Attribute)
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


def _included_handler_modules() -> set[str]:
    main_source = (ROOT / "main.py").read_text()
    tree = ast.parse(main_source, filename=str(ROOT / "main.py"))
    modules: set[str] = set()

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        if not node.module.startswith("handlers."):
            continue
        if any(alias.name == "router" for alias in node.names):
            modules.add(node.module)

    return modules


def test_every_keyboard_action_has_a_matching_handler():
    buttons = _button_contracts()
    handlers = _handler_contracts()

    missing = [
        f"{button.kind} '{button.key}' at {button.location}"
        for button in buttons
        if not any(_matches(button, handler) for handler in handlers)
    ]

    assert not missing, "Buttons without a matching handler:\n- " + "\n- ".join(missing)


def test_no_duplicate_exact_handler_contracts():
    handlers = _handler_contracts()
    seen: dict[tuple[str, str, tuple[tuple[str, object], ...]], str] = {}
    duplicates: list[str] = []

    for handler in handlers:
        key = (handler.kind, handler.key, handler.constraints)
        if key in seen:
            duplicates.append(f"{handler.location} duplicates {seen[key]}")
        else:
            seen[key] = handler.location

    assert not duplicates, "Duplicate exact handler contracts:\n- " + "\n- ".join(duplicates)


def test_every_handler_router_is_included_in_main():
    handler_modules = {
        f"handlers.{path.stem}"
        for path in _source_files("handlers")
        if path.name != "__init__.py"
    }
    included = _included_handler_modules()
    missing = sorted(handler_modules - included)

    assert not missing, "Handler routers not included in main.py:\n- " + "\n- ".join(missing)
