"""`clean`: quita ANSI y restos de la negociación telnet."""
from gns3core import clean


def test_clean_quita_ansi():
    raw = "\x1b[1;32mOK\x1b[0m y \x1b[2Jfin\x1b[H"
    assert clean(raw) == "OK y fin"


def test_clean_quita_osc_y_charset():
    raw = "\x1b]0;titulo\x07texto\x1b(B"
    assert clean(raw) == "texto"


def test_clean_quita_ufffd_de_la_negociacion_telnet():
    # IAC WILL ECHO etc. llegan como U+FFFD al decodificar bytes no UTF-8.
    raw = "\ufffd\ufffd\x01PC1>\ufffd"
    assert clean(raw) == "\x01PC1>"
    assert "\ufffd" not in clean(raw)


def test_clean_normaliza_saltos_y_quita_nulos():
    assert clean("uno\r\ndos\rfinal\x00") == "uno\ndos\nfinal"
