"""`find_monitor_port` sobre un `/proc` simulado (directorio temporal)."""
import gns3core
from gns3core import find_monitor_port


def _proc(root, name, args=None, raw=None):
    d = root / name
    d.mkdir()
    if raw is not None:
        (d / "cmdline").write_bytes(raw)
    elif args is not None:
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in args) + b"\0")
    return d


def _simular_proc(monkeypatch, tmp_path):
    monkeypatch.setattr(gns3core, "Path", lambda _path: tmp_path)


def test_encuentra_el_puerto_por_uuid_en_un_solo_argumento(monkeypatch, tmp_path):
    _simular_proc(monkeypatch, tmp_path)
    _proc(tmp_path, "self")                                    # no numérico
    _proc(tmp_path, "11")                                      # sin cmdline legible
    _proc(tmp_path, "12", args=["/usr/bin/python", "-m", "x"])  # no es qemu
    _proc(tmp_path, "13", args=["qemu-system-x86_64", "-uuid", "nodo-1",
                                "-monitor tcp:127.0.0.1:41001"])

    assert find_monitor_port(node_id="nodo-1") == 41001


def test_encuentra_el_puerto_con_monitor_y_valor_separados(monkeypatch, tmp_path):
    _simular_proc(monkeypatch, tmp_path)
    _proc(tmp_path, "21", args=["qemu-system-x86_64", "-uuid", "nodo-2",
                                "-monitor", "tcp:127.0.0.1:41002"])

    assert find_monitor_port(node_id="nodo-2") == 41002


def test_busca_tambien_por_nombre_de_disco(monkeypatch, tmp_path):
    _simular_proc(monkeypatch, tmp_path)
    _proc(tmp_path, "31", args=["qemu-system-x86_64", "-uuid", "otro",
                                "-drive", "file=/discos/pfsense.qcow2",
                                "-monitor", "tcp:127.0.0.1:41003"])

    assert find_monitor_port(disk="pfsense.qcow2") == 41003


def test_ignora_procesos_que_no_casan_con_uuid_ni_disco(monkeypatch, tmp_path):
    _simular_proc(monkeypatch, tmp_path)
    _proc(tmp_path, "41", args=["qemu-system-x86_64", "-uuid", "nodo-3",
                                "-monitor", "tcp:127.0.0.1:41004"])

    assert find_monitor_port(node_id="nodo-4") is None
    assert find_monitor_port(disk="disco-que-no-esta") is None


def test_monitor_sin_tcp_no_devuelve_puerto(monkeypatch, tmp_path):
    _simular_proc(monkeypatch, tmp_path)
    _proc(tmp_path, "51", args=["qemu-system-x86_64", "-monitor", "stdio"])
    _proc(tmp_path, "52", args=["qemu-system-x86_64", "-monitor", "tcp:127.0.0.1"])
    _proc(tmp_path, "53", args=["qemu-system-x86_64", "-monitor", "tcp:malo:9999"])

    assert find_monitor_port() is None


def test_sin_procesos_qemu_devuelve_none(monkeypatch, tmp_path):
    _simular_proc(monkeypatch, tmp_path)
    assert find_monitor_port() is None


def test_ignora_entradas_no_numericas_y_procesos_sin_cmdline(monkeypatch, tmp_path):
    """Sin ninguna coincidencia el bucle recorre (y salta) todas las entradas."""
    _simular_proc(monkeypatch, tmp_path)
    _proc(tmp_path, "self")                 # no numérica
    _proc(tmp_path, "77")                   # numérica pero sin cmdline legible
    assert find_monitor_port() is None


def test_cmdline_vacio_no_rompe(monkeypatch, tmp_path):
    _simular_proc(monkeypatch, tmp_path)
    _proc(tmp_path, "61", raw=b"")
    assert find_monitor_port() is None


def test_uuid_manda_sobre_nombre_de_disco_copiado(monkeypatch, tmp_path):
    """El disco copiado al proyecto se llama hda_disk.qcow2: con uuid válido
    el nombre del disco original no debe filtrar el proceso."""
    _simular_proc(monkeypatch, tmp_path)
    _proc(tmp_path, "61", args=["qemu-system-x86_64", "-uuid", "nodo-5",
                                "-drive", "file=/proyectos/x/project-files/qemu/nodo-5/hda_disk.qcow2",
                                "-monitor", "tcp:127.0.0.1:41005"])

    assert find_monitor_port(node_id="nodo-5", disk="pfSense-minitest.qcow2") == 41005


def test_uuid_exacto_ignora_otro_proceso_que_lo_contiene_en_el_disco(monkeypatch, tmp_path):
    """El UUID de un nodo en la ruta del disco no identifica otro proceso QEMU."""
    _proc(tmp_path, "60", args=["qemu-system-x86_64", "-uuid", "otro-nodo",
                                "-drive", "file=/proyectos/x/project-files/qemu/nodo-5/ajeno.qcow2",
                                "-monitor", "tcp:127.0.0.1:41001"])
    _proc(tmp_path, "61", args=["qemu-system-x86_64", "-uuid", "nodo-5",
                                "-drive", "file=/proyectos/x/project-files/qemu/nodo-5/hda_disk.qcow2",
                                "-monitor", "tcp:127.0.0.1:41002"])

    class ProcRaiz:
        def iterdir(self):
            return iter([tmp_path / "60", tmp_path / "61"])

    monkeypatch.setattr(gns3core, "Path", lambda _path: ProcRaiz())

    assert find_monitor_port(node_id="nodo-5") == 41002
