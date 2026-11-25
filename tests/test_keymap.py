"""Traducción carácter -> tecla HMP (`sendkey`)."""
import pytest

from gns3core import key_for


@pytest.mark.parametrize(
    ("char", "key"),
    [
        ("a", "a"),
        ("A", "shift-a"),
        ("0", "0"),
        ("-", "minus"),
        (".", "dot"),
        (" ", "spc"),
        ("\n", "ret"),
        ("@", "shift-2"),
        (">", "shift-dot"),
        (":", "shift-semicolon"),
        ("_", "shift-minus"),
        ("?", "shift-slash"),
    ],
)
def test_key_for_mapeos_del_brief(char, key):
    assert key_for(char) == key


@pytest.mark.parametrize("char", ["ñ", "€", "á", "\x01"])
def test_key_for_caracter_no_mapeable_devuelve_none(char):
    assert key_for(char) is None
