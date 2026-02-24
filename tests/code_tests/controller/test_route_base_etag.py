import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
for path in (SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from nsj_rest_lib.controller.route_base import RouteBase


def test_parse_if_none_match_multiple_values():
    header = '"one" , "two" , "three"'

    assert RouteBase.parse_if_none_match(header) == ["one", "two", "three"]


def test_parse_if_none_match_supports_escapes():
    header = '"a\\"b", "c"'

    assert RouteBase.parse_if_none_match(header) == ['a"b', "c"]


def test_parse_if_none_match_ignores_unterminated_values():
    header = '"unterminated'

    assert RouteBase.parse_if_none_match(header) == []


def test_parse_if_none_match_accepts_weak_etags():
    header = 'W/"weak", "strong"'

    assert RouteBase.parse_if_none_match(header) == ["weak", "strong"]


def test_quote_and_escape_string_wraps_and_escapes():
    assert RouteBase.quote_and_escape_string('a"b') == '"a\\"b"'
    assert RouteBase.quote_and_escape_string("plain") == '"plain"'
    assert RouteBase.quote_and_escape_string("") == '""'
