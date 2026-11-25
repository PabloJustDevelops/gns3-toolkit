#!/usr/bin/env python3
"""Banco de rendimiento reproducible de gns3-toolkit, sin servidor GNS3.

Mide cinco capas con los dobles de ``tests/conftest.py``: arranque de la CLI,
registro de tools del MCP, ``gns3_batch`` en paralelo frente a secuencial,
parseo/render de ``config.xml`` de pfSense y serialización JSON de un informe.

Uso:
    .venv/bin/python scripts/bench.py --quick
    .venv/bin/python scripts/bench.py --full

Salida: una línea ``metric`` por medida (``n``, ``median_ms``, ``p95_ms``),
los ratios disponibles y ``exit_code=0/1``. No escribe ficheros ni habla con
ningún servidor real; el HTTP sale de un ``FakeApi`` en 127.0.0.1.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Latencia simulada por lectura del lote: el FakeApi responde al instante, así que
# se inyecta un retardo explícito para medir el solape del ThreadPoolExecutor.
LATENCIA_LOTE_S = 0.020

CONFIG_XML = """<pfsense>
  <system><hostname>fw-lab</hostname><domain>lab.local</domain>
    <ssh><enable>on</enable><port>22022</port></ssh></system>
  <interfaces>
    <wan><if>em0</if><ipaddr>192.0.2.1</ipaddr><subnet>24</subnet></wan>
    <lan><if>em1</if><ipaddr>192.168.10.1</ipaddr><subnet>24</subnet></lan>
  </interfaces>
  <dhcpd><lan><enable></enable>
    <range><from>192.168.10.100</from><to>192.168.10.200</to></range></lan></dhcpd>
  <filter>
    <rule><type>pass</type><interface>lan</interface><destination><any></any></destination></rule>
    <rule><type>pass</type><interface>wan</interface><protocol>tcp</protocol><dstport>22022</dstport></rule>
    <rule><type>pass</type><interface>wan</interface><protocol>icmp</protocol></rule>
    <rule><type>reject</type><interface>wan</interface></rule>
  </filter>
  <nat><outbound><mode>automatic</mode>
    <rule><type>pass</type><interface>wan</interface><source><network>192.168.10.0/24</network></source></rule>
    <rule><type>reject</type><interface>wan</interface></rule></outbound></nat>
  <desconocido modo="si"><item id="a">uno</item><item id="b">dos</item></desconocido>
</pfsense>"""


def _p95(muestras: list[float]) -> float:
    ordenadas = sorted(muestras)
    indice = max(0, math.ceil(0.95 * len(ordenadas)) - 1)
    return ordenadas[indice]


def _medir(funcion, repeticiones: int) -> tuple[list[float], str | None]:
    """Devuelve las muestras en ms y el primer error, si lo hubo."""
    muestras: list[float] = []
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        try:
            funcion()
        except Exception as exc:  # el banco informa del fallo, no lo esconde
            return muestras, f"{type(exc).__name__}: {exc}"
        muestras.append((time.perf_counter() - inicio) * 1000.0)
    return muestras, None


def _linea_metrica(nombre: str, muestras: list[float], error: str | None) -> float | None:
    if error or not muestras:
        print(f"metric {nombre} ok=0 error={error or 'sin muestras'}")
        return None
    mediana = statistics.median(muestras)
    print(f"metric {nombre} n={len(muestras)} median_ms={mediana:.3f} "
          f"p95_ms={_p95(muestras):.3f} ok=1")
    return mediana


def _medir_cli(repeticiones: int) -> float | None:
    def arranque() -> None:
        proc = subprocess.run(
            [sys.executable, str(RAIZ / "cli" / "gns3lab"), "--help"],
            cwd=RAIZ, capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"gns3lab --help salió con {proc.returncode}: "
                               f"{proc.stderr.strip()[:200]}")

    muestras, error = _medir(arranque, repeticiones)
    return _linea_metrica("cli_help", muestras, error)


def _medir_mcp(repeticiones: int) -> tuple[float | None, int]:
    import gns3_mcp_server as server

    def listado() -> int:
        return len(asyncio.run(server.mcp.list_tools()))

    total = 0

    def una_vez() -> None:
        nonlocal total
        total = listado()
        if total <= 0:
            raise RuntimeError("mcp.list_tools() no devolvió tools")

    una_vez()  # calentamiento: el primer listado construye el registro interno
    muestras, error = _medir(una_vez, repeticiones)
    mediana = _linea_metrica("mcp_list_tools", muestras, error)
    print(f"metric mcp_tools count={total}")
    return mediana, total


def _medir_lote(repeticiones: int) -> tuple[float | None, float | None]:
    import gns3_mcp_server as server
    from gns3core import Client

    sys.path.insert(0, str(RAIZ / "tests"))
    import conftest  # doble HTTP local, sin dependencias de red externa

    api = conftest.FakeApi()
    rutas = {
        "gns3_status": ("/v2/version", {"version": "2.2.61", "local": True}),
        "gns3_topology": ("/v2/projects", [{"project_id": "p1", "name": "lab",
                                            "status": "opened"}]),
        "gns3_templates": ("/v2/templates", [{"template_id": "t1", "name": "PC"}]),
        "gns3_appliances": ("/v2/appliances", [{"name": "pfSense"}]),
        "gns3_statistics": ("/v2/statistics", {"nodes": 5, "links": 4}),
    }
    cliente = Client(api.url)
    for ruta, payload in rutas.values():
        api.route("GET", ruta, 200, payload)

    def lectura(ruta: str):
        def tool(**_kwargs):
            estatus, cuerpo = cliente.get(ruta)
            if estatus != 200:
                raise RuntimeError(f"{ruta} devolvió {estatus}")
            time.sleep(LATENCIA_LOTE_S)  # I/O simulado, ver LATENCIA_LOTE_S
            return cuerpo
        return tool

    funciones = {nombre: lectura(ruta) for nombre, (ruta, _) in rutas.items()}
    operaciones = [{"tool": nombre, "args": {}} for nombre in rutas]
    original = server._registered_tool_functions
    server._registered_tool_functions = lambda: dict(funciones)
    try:
        def en_paralelo() -> None:
            resultado = server.gns3_batch(operaciones)
            if not resultado.get("ok") or not resultado.get("parallel"):
                raise RuntimeError(f"lote paralelo inesperado: {resultado}")

        def en_secuencia() -> None:
            # stop_on_error fuerza el camino secuencial del mismo gns3_batch
            resultado = server.gns3_batch(operaciones, stop_on_error=True)
            if not resultado.get("ok") or resultado.get("parallel"):
                raise RuntimeError(f"lote secuencial inesperado: {resultado}")

        en_paralelo()  # calentamiento de pool e imports
        en_secuencia()
        muestras_par, error_par = _medir(en_paralelo, repeticiones)
        muestras_seq, error_seq = _medir(en_secuencia, repeticiones)
    finally:
        server._registered_tool_functions = original
        api.close()

    mediana_par = _linea_metrica("batch_parallel", muestras_par, error_par)
    mediana_seq = _linea_metrica("batch_sequential", muestras_seq, error_seq)
    print(f"metric batch_lecturas count={len(operaciones)} "
          f"latencia_ms={LATENCIA_LOTE_S * 1000:.0f}")
    if mediana_par and mediana_seq:
        print(f"ratio batch_speedup median={mediana_seq / mediana_par:.2f}x")
    return mediana_par, mediana_seq


def _medir_pfsense(repeticiones: int) -> tuple[float | None, float | None]:
    import pfsense

    documento = pfsense.parse_config(CONFIG_XML)

    def parseo() -> None:
        if "interfaces" not in pfsense.parse_config(CONFIG_XML):
            raise RuntimeError("parse_config perdió <interfaces>")

    def render() -> None:
        if "<pfsense>" not in pfsense.render_config(documento):
            raise RuntimeError("render_config no generó <pfsense>")

    muestras_parse, error_parse = _medir(parseo, repeticiones)
    muestras_render, error_render = _medir(render, repeticiones)
    return (_linea_metrica("pfsense_parse", muestras_parse, error_parse),
            _linea_metrica("pfsense_render", muestras_render, error_render))


def _informe_representativo() -> dict:
    nodos = [{"node_id": f"n{i}", "name": f"nodo-{i}", "node_type": "qemu",
              "status": "started" if i % 2 else "stopped", "console": 5000 + i,
              "properties": {"ram": 512, "adapters": 2, "adapter_type": "e1000"}}
             for i in range(25)]
    enlaces = [{"link_id": f"l{i}", "nodes": [{"node_id": f"n{i}", "adapter_number": 0,
                                               "port_number": 0},
                                              {"node_id": f"n{i + 1}", "adapter_number": 0,
                                               "port_number": 0}]}
               for i in range(24)]
    return {
        "status": {"running": True, "version": "2.2.61", "projects": 1,
                   "computes": [{"name": "local", "connected": True}]},
        "project": {"project_id": "p1", "name": "lab", "status": "opened"},
        "topology": {"nodes": nodos, "links": enlaces},
        "findings": ["nodos no arrancados: nodo-0, nodo-2, nodo-4"],
        "pending": ["ping extremo a extremo", "rutas, VLAN y NAT efectivos"],
    }


def _medir_json(repeticiones: int) -> float | None:
    informe = _informe_representativo()

    def serializa() -> None:
        texto = json.dumps(informe, ensure_ascii=False, indent=2, sort_keys=True)
        if len(texto) < 1000:
            raise RuntimeError("el informe representativo es demasiado pequeño")

    muestras, error = _medir(serializa, repeticiones)
    print(f"metric json_informe bytes={len(json.dumps(informe, ensure_ascii=False, indent=2, sort_keys=True))}")
    return _linea_metrica("json_serialize", muestras, error)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="banco de rendimiento de gns3-toolkit")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--quick", action="store_true", help="pocas repeticiones (suite)")
    modo.add_argument("--full", action="store_true", help="banco completo (informe)")
    args = ap.parse_args(argv)
    rapido = not args.full
    reps = {"cli": 2 if rapido else 5,
            "mcp": 3 if rapido else 10,
            "batch": 3 if rapido else 7,
            "pfsense": 3 if rapido else 10,
            "json": 3 if rapido else 10}

    import fastmcp

    print(f"bench mode={'quick' if rapido else 'full'} "
          f"python={platform.python_version()} fastmcp={fastmcp.__version__} "
          f"date={datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')} "
          f"platform={platform.platform()}")

    fallos = 0
    resultados: dict[str, float | None] = {}
    try:
        resultados["cli_help"] = _medir_cli(reps["cli"])
        mediana_mcp, total_tools = _medir_mcp(reps["mcp"])
        resultados["mcp_list_tools"] = mediana_mcp
        if total_tools <= 0:
            fallos += 1
        resultados["batch_parallel"], resultados["batch_sequential"] = _medir_lote(reps["batch"])
        resultados["pfsense_parse"], resultados["pfsense_render"] = _medir_pfsense(reps["pfsense"])
        resultados["json_serialize"] = _medir_json(reps["json"])
    except Exception as exc:
        print(f"bench error={type(exc).__name__}: {exc}")
        fallos += 1

    fallos += sum(1 for valor in resultados.values() if valor is None)
    codigo = 0 if fallos == 0 else 1
    print(f"exit_code={codigo}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
