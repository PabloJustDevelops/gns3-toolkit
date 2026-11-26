# Capturas por fase (referencia corta)

Guía completa en [docs/CAPTURAS-EXAMEN.md](../../docs/CAPTURAS-EXAMEN.md). Esquema del spec en
[docs/LAB-SPEC.md](../../docs/LAB-SPEC.md).

## Reglas duras

- **VNC es el último recurso.** La imagen de consola sale del monitor HMP: `gns3lab shot` y
  `gns3lab mon`, primero; VNC sólo si HMP y la consola telnet fallan. `screendump` escribe PPM,
  Pillow lo pasa a PNG y el OCR va a escala x2 con `--psm 4`; sin `tesseract`, OCR vacío.
- **La WebUI es sólo evidencia, nunca configuración.** Navegador headless en modo lectura:
  `interfaces`, `rules`, `dhcp`; perfil efímero, una captura por página, cerrar en `finally`.
  Prohibido clic en Save/Apply y envío de formularios. Para configurar pfSense, vía nativa por
  `config.xml`: [pfsense-nativo.md](pfsense-nativo.md).
- Credenciales sólo de entorno (`PFSENSE_HOST`, `PFSENSE_USER`, `PFSENSE_PASSWORD`): nunca en el
  repo, en un log ni en un nombre de fichero.
- Si la WebUI o el navegador no están disponibles, o falla una captura, se imprime la razón y se
  degrada a consola sin romper el montaje ni el examen.
- El resultado es `indice.md` (`fase | archivo | nodo | OCR`), no un documento final ni un informe
  largo.

## Bloque `captures:`

```yaml
captures:
  - phase: topologia
    after: apply        # apply | verify
    node: null          # o nombre de nodo con monitor HMP
  - phase: verificacion
    after: verify
    node: PF1
```

Máximo 5 fases. Una entrada sin `phase` o con `after` desconocido da error con la ruta del campo.

## Comandos y estado

Lo que existe hoy en el repo: `gns3lab shot <nodo> -p <proyecto>`, `gns3lab mon <nodo> <cmd>`,
`gns3lab lab apply --spec … --yes` y `gns3lab examen verify`.

Lo que está **previsto en otros carriles**, no ejecutable todavía:

| Pieza | Carril |
|---|---|
| `captures.py` y `lab apply --captures` | `capcore` |
| `webui_capture.py` y `gns3lab examen capturas [--webui] [--out …]` | `capweb` |
| tool MCP `gns3_capturas` (`phases\|console\|webui\|index`) | `capmcp` |

No instales Playwright ni Chromium desde la skill: si faltan, el código degrada con razón
explícita. «Previsto» no es «hecho».
