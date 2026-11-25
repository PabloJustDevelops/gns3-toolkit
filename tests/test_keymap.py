"""Traducción carácter -> tecla HMP (`sendkey`)."""
import pytest

from gns3core import KEYMAP, NAMED, key_for


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


@pytest.mark.parametrize(("char", "key"), sorted(KEYMAP.items()))
def test_key_for_cubre_todo_el_mapa(char, key):
    assert key_for(char) == key


@pytest.mark.parametrize(("char", "key"), sorted(NAMED.items()))
def test_key_for_cubre_los_nombrados(char, key):
    assert key_for(char) == key


@pytest.mark.parametrize("char", list("abcdefghijklmnopqrstuvwxyz0123456789"))
def test_key_for_letras_y_digitos_van_tal_cual(char):
    assert key_for(char) == char


@pytest.mark.parametrize("char", list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
def test_key_for_mayusculas_van_con_shift(char):
    assert key_for(char) == "shift-" + char.lower()
