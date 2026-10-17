"""Tests for UI translations in locales/."""
import json
import os
import re

import pytest

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales")
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _flatten(tree, prefix=""):
    flat = {}
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, path + "."))
        else:
            flat[path] = value
    return flat


def _load(name):
    with open(os.path.join(LOCALES_DIR, f"{name}.json"), encoding="utf-8") as f:
        return _flatten(json.load(f))


LANGUAGES = sorted(f[:-5] for f in os.listdir(LOCALES_DIR) if f.endswith(".json"))
OTHER_LANGUAGES = [lang for lang in LANGUAGES if lang != "en"]


def test_english_and_ukrainian_exist():
    assert {"en", "uk"} <= set(LANGUAGES)


@pytest.mark.parametrize("lang", OTHER_LANGUAGES)
def test_same_keys_as_english(lang):
    en, other = _load("en"), _load(lang)
    assert sorted(set(en) - set(other)) == [], f"missing in {lang}"
    assert sorted(set(other) - set(en)) == [], f"extra in {lang}"


@pytest.mark.parametrize("lang", OTHER_LANGUAGES)
def test_same_placeholders_as_english(lang):
    en, other = _load("en"), _load(lang)
    mismatched = {
        key: (PLACEHOLDER.findall(en[key]), PLACEHOLDER.findall(other[key]))
        for key in en
        if key in other and set(PLACEHOLDER.findall(en[key])) != set(PLACEHOLDER.findall(other[key]))
    }
    assert mismatched == {}


@pytest.mark.parametrize("lang", LANGUAGES)
def test_values_are_non_empty_strings(lang):
    empty = [key for key, value in _load(lang).items() if not isinstance(value, str) or not value.strip()]
    assert empty == []


@pytest.mark.parametrize("lang", LANGUAGES)
def test_meta(lang):
    flat = _load(lang)
    for key in ("meta.name", "meta.short", "meta.locale"):
        assert flat.get(key), f"{lang}: {key}"


class TestAppLocales:
    def test_default_language_loaded_first(self):
        import app as app_module
        assert list(app_module.LOCALES)[0] == app_module.DEFAULT_LANGUAGE == "en"
        assert "uk" in app_module.LOCALES

    def test_index_embeds_locales_and_language_button(self):
        import app as app_module
        app_module.app.config["TESTING"] = True
        with app_module.app.test_client() as c:
            html = c.get("/").get_data(as_text=True)
        assert 'id="language-btn"' in html
        # uk.json is embedded (non-ASCII is JSON-escaped in the page)
        uk_name = json.dumps(_load("uk")["meta.name"])[1:-1]
        assert '"uk":' in html and uk_name in html
        assert 'defaultLanguage: "en"' in html

    def test_template_keys_exist_in_english(self):
        """Every data-i18n / t('...') key used by the page is defined in en.json."""
        root = os.path.dirname(LOCALES_DIR)
        source = ""
        for rel in ("templates/index.html", "static/js/dashboard.js"):
            with open(os.path.join(root, rel), encoding="utf-8") as f:
                source += f.read()
        keys = set(re.findall(r'data-i18n="([\w.\-]+)"', source))
        keys |= {k for pair in re.findall(r'data-i18n-attr="([^"]+)"', source)
                 for k in [p.split(":", 1)[1] for p in pair.split(";")]}
        keys |= set(re.findall(r"\bt\('([\w.\-]+)'", source))
        keys |= set(re.findall(r"setI18nText\([^,]+,\s*'([\w.\-]+)'", source))
        # Keys built at runtime: weather.codes.<code>, battery.status.<key>
        keys = {k for k in keys if not k.endswith(".")}
        en = _load("en")
        assert sorted(k for k in keys if k not in en) == []
