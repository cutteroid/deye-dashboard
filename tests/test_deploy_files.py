"""Every module the app imports is shipped by the Dockerfile and deploy.sh."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def _local_modules():
    """Top-level project modules / packages imported by app.py (and what they import)."""
    names = set()
    todo = ["app"]
    while todo:
        module = todo.pop()
        path = os.path.join(ROOT, f"{module}.py")
        if not os.path.exists(path):
            path = os.path.join(ROOT, module, "__init__.py")
        source = open(path, encoding="utf-8").read()
        for name in re.findall(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", source, re.M):
            if name not in names and (os.path.exists(os.path.join(ROOT, f"{name}.py"))
                                      or os.path.isdir(os.path.join(ROOT, name))):
                names.add(name)
                todo.append(name)
    return names


def test_docker_image_has_every_module():
    copied = set(re.findall(r"^COPY (\S+?)/? ", _read("Dockerfile"), re.M))
    missing = {name for name in _local_modules() if f"{name}.py" not in copied and name not in copied}
    assert missing == set()


def test_deploy_script_ships_every_module():
    files = set(re.findall(r'^\s+"([^"]+)"$', _read("deploy.sh"), re.M))
    missing = {name for name in _local_modules() if f"{name}.py" not in files and name not in files}
    assert missing == set()
