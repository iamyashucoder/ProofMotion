import ast

FORBIDDEN_IMPORTS = {"os", "subprocess", "socket", "requests", "pathlib", "shutil"}
FORBIDDEN_CALLS = {"eval", "exec", "open", "__import__"}


def validate_generated_code(code: str) -> tuple[bool, str | None]:
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return False, str(error)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name.split(".")[0] for alias in node.names]
            if any(name in FORBIDDEN_IMPORTS for name in names):
                return False, f"Forbidden import: {names}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            return False, f"Forbidden function call: {node.func.id}"
    return True, None
