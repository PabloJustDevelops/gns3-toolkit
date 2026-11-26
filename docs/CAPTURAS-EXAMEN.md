# Capturas por fase del examen

Secciones: Estado en este árbol · El bloque `captures:` · Ciclo completo · De dónde sale cada
imagen · Índice y documento final · Cómo comprobarlo aquí.

Guía del ciclo de capturas del laboratorio: unas pocas imágenes, una por fase, con su texto OCR en
un índice. No sustituye al guion de [EXAMEN.md](EXAMEN.md) ni cambia la vía nativa de
[pfSense nativo](PFSENSE-NATIVO.md). El esquema del manifiesto está en
[LAB-SPEC.md](LAB-SPEC.md) y los flags en [COMANDOS.md](COMANDOS.md).

## Estado en este árbol

En este worktree no están todavía las piezas de los carriles de capturas. Se comprueba con
`./cli/gns3lab --help`, con `./cli/gns3lab examen --help` y buscando `gns3_capturas` en
`gns3_mcp_server.py`.

| Pieza | Estado aquí | Carril |
|---|---|---|
| `captures.py` (`capture_phase`, `write_index`, `phases_from_spec`) | previsto en capcore; fichero ausente | `capcore` |
| Bloque `captures:` activo en `labspec.py` y flag `gns3lab lab apply --captures` | previsto en capcore; flag ausente | `capcore` |
| `webui_capture.py` (`WebUICapture.from_env`) | previsto en capweb; fichero ausente | `capweb` |
| `gns3lab examen capturas` | previsto en capweb; acción ausente | `capweb` |
| Tool MCP `gns3_capturas` | previsto en capmcp; tool ausente | `capmcp` |

Lo que sí existe hoy y sirve para capturar a mano es `gns3lab shot`, `gns3lab mon`,
`gns3lab key`/`type`, `gns3lab lab apply --yes --spec …` y `gns3lab examen verify`. Las órdenes y
salidas marcadas como «previsto» más abajo son el contrato acordado, no comandos ejecutables en
este árbol.

## El bloque `captures:`

El manifiesto YAML puede declarar fases de captura. Ejemplo de bloque, no salida medida:

```yaml
captures:
  - phase: topologia     # obligatorio: nombre de la fase
    after: apply         # obligatorio: apply | verify
    node: null           # opcional: nodo con monitor HMP, o null
  - phase: pfsense
    after: apply
    node: PF1
  - phase: reglas
    after: apply
    node: PF1
  - phase: nat
    after: verify
    node: PF1
  - phase: verificacion
    after: verify
    node: null
```

Reglas del contrato (previsto en capcore):

- Máximo **5 fases**. Una entrada sin `phase` o con un `after` distinto de `apply`/`verify` da un
  error con la ruta del campo, p. ej. `captures[1].after`.
- `node: null` significa que la fase no depende de un monitor de consola; con un nombre de nodo se
  captura el monitor HMP de ese nodo.
- La captura va después de la fase indicada: `apply` para topología y configuración, `verify` para
  el estado final.
- Si una captura falla, se reporta en el resultado y **no** cambia el exit code del montaje: el
  laboratorio se termina igual.

## Ciclo completo

Previsto en capcore — montar y capturar en el mismo paso:

```bash
gns3lab lab apply --spec examples/lab-ejemplo.yaml --captures --yes
```

Previsto en capweb — capturas del kit de examen, con o sin WebUI:

```bash
gns3lab examen capturas --out ~/GNS3/capturas
gns3lab examen capturas --webui --out ~/GNS3/capturas --phase verificacion
```

Previsto en capmcp — la tool `gns3_capturas` con `action="phases|console|webui|index"`. Lee la
spec de `GNS3_LAB_SPEC` o del argumento `spec`, captura por HMP o delega en `WebUICapture` y escribe
sólo imágenes e `indice.md` en `outdir`. No configura nada y su campo `error` nunca incluye la
contraseña.

Ejemplo de salida (ilustrativo; **no medido en este árbol**):

```text
fases: 5 · imágenes: 5 · fallos de captura: 0
índice: ~/GNS3/capturas/indice.md
```

Un fallo de captura se imprime como aviso con su fase y motivo; si la WebUI no está disponible, la
salida incluye la razón y `fallback=consola`.

## De dónde sale cada imagen

**Consola:** del monitor HMP, nunca de VNC. `screendump` escribe un PPM temporal, Pillow lo convierte
a `<outdir>/<NN>-<fase>.png` y el OCR se hace a escala x2 con `--psm 4` (a x1 confunde `w` con `u`).
Sin Pillow o sin `tesseract` la captura degrada y lo reporta; el OCR queda como cadena vacía, no
rompe la imagen. Hoy esto se hace con `gns3lab shot PF1 -p examen-kit` y `gns3lab mon PF1 ...`.
Trampas ya pagadas: `sendkey ret`, no `enter`; mayúsculas y símbolos con `shift-<tecla>`; la
consola del invitado duerme y `type` ya envía `shift` antes de la primera tecla útil. VNC es el
**último recurso**, sólo cuando HMP y la consola telnet no estén disponibles.

**WebUI:** navegador headless, sólo para evidencia visual y **sólo en modo lectura**. Páginas por
defecto: `interfaces`, `rules` y `dhcp`; `login_once`, `ignore_https_errors=True`, perfil efímero
bajo `/tmp`, un PNG por página y cierre en `finally`. Nunca se hace clic en Save/Apply ni se envía
un formulario de configuración: para configurar, la vía es
[pfSense nativo](PFSENSE-NATIVO.md). Si Playwright, el navegador o la IP no están disponibles, se
imprime la razón y se degrada a captura de consola sin bloquear el examen. Las credenciales salen
de `PFSENSE_HOST`/`PFSENSE_USER`/`PFSENSE_PASSWORD` del entorno; nunca se escriben en el repo, en
un log ni en un nombre de fichero. La instalación de Playwright/Chromium la hace el usuario fuera
de esta tarea (`playwright install chromium`).

## Índice y documento final

`write_index` (previsto en capcore) escribe `<outdir>/indice.md`: una tabla
`fase | archivo | nodo | OCR (recortado)` y una línea de estado con los fallos. Es el único
documento que genera el ciclo. **No se genera el documento final** ni un informe largo de capturas;
`gns3lab examen informe` es el informe de estado del kit y no compone este índice.

## Cómo comprobarlo aquí

```bash
python3 scripts/check-links.py
./cli/gns3lab examen --help
./cli/gns3lab lab apply --help
python3 scripts/verify.py
```

Con las tres piezas de los carriles integradas, el ciclo se valida además con
`pytest -q tests/test_captures.py tests/test_webui_capture.py tests/test_mcp_capturas.py`, con
dobles de monitor y de navegador: sin servidor GNS3, sin pfSense real y sin credenciales reales.
