"""Static checks of static/js/dashboard.js (no JS test runner in this project)."""
import os
import re

JS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "js", "dashboard.js")


def test_top_level_code_uses_constants_after_their_definition():
    """`var X = ...` only takes its value when that line runs; top-level code above
    it sees undefined. setInterval(fetchWeather, WEATHER_POLL_MS) placed above the
    constant polled /api/weather ~250 times a second."""
    with open(JS_PATH, encoding="utf-8") as f:
        lines = f.read().split("\n")
    defined_at = {}
    for number, line in enumerate(lines, 1):
        match = re.match(r"var ([A-Z][A-Z0-9_]+)\s*=", line)
        if match:
            defined_at.setdefault(match.group(1), number)
    too_early = []
    for number, line in enumerate(lines, 1):
        # top-level statements only: indented lines run later, inside functions
        if not line.strip() or line[0] in " \t}/" or line.startswith(("function ", "var ")):
            continue
        for name in re.findall(r"\b[A-Z][A-Z0-9_]{3,}\b", line):
            if defined_at.get(name, 0) > number:
                too_early.append(f"line {number}: {name} (defined at line {defined_at[name]})")
    assert too_early == []
