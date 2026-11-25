# Aviso de versiones nuevas

La versión local vive en el fichero `VERSION` de la raíz del repositorio. La CLI la lee de
ahí; no hay una segunda copia en el código ni en la documentación.

## Uso

```bash
gns3lab --version                    # imprime la versión local y sale con 0 (sin red)
gns3lab doctor --check-updates       # chequeo del lab + aviso de versión nueva
gns3lab doctor --check-updates --json
```

Sin `--check-updates`, `doctor` no toca la red y su salida es la de siempre.

En texto, el bloque `actualizaciones` imprime tres líneas:

```text
  actualizaciones
    installed: 0.1.0
    latest: 0.2.0
    update_available: sí
```

Con `--json`, el informe de `doctor` añade un objeto `updates`:

```json
"updates": {
  "installed": "0.1.0",
  "latest": "0.2.0",
  "update_available": true,
  "source": "releases",
  "checked_at": "2026-11-26T00:00:00+00:00",
  "error": null
}
```

## Qué significa cada campo

| Campo | Significado |
|---|---|
| `installed` | Versión leída de `VERSION`. |
| `latest` | Última versión publicada, normalizada a `X.Y.Z`; `null` si no hay ninguna o no se pudo consultar. |
| `update_available` | `true` sólo cuando `latest` es numéricamente mayor que `installed`. |
| `source` | `releases` si salió de `/releases/latest`, `tags` si hubo 404 y se usó `/tags`, `none` si no se consultó. |
| `checked_at` | Momento de la consulta o de la entrada de caché, en ISO 8601 con zona UTC. |
| `error` | `null` si no hubo fallo; si lo hubo, un mensaje accionable (timeout, 403, red, respuesta inválida). |
| `note` | Sólo aparece en casos informativos: sin versiones publicadas o comprobación desactivada. |

La comparación es numérica por componentes (`X.Y.Z`), no léxica: `0.10.0` es mayor que `0.9.0`.
Se aceptan etiquetas con o sin prefijo `v`.

## Caché y desactivación

- Ruta: `$XDG_CACHE_HOME/gns3-toolkit/update-check.json`; si la variable no existe,
  `~/.cache/gns3-toolkit/update-check.json`.
- TTL: 24 horas. Una caché fresca evita la consulta remota; una caducada se refresca.
- `GNS3LAB_NO_UPDATE_CHECK=1`: no consulta GitHub. Si hay caché, la usa; si no, informa
  `sin comprobación remota` y sigue.
- Timeout de red: 3 segundos. Un fallo de red o de la API no cambia el código de salida de
  `doctor`: es una comprobación no bloqueante.

## Publicar una versión nueva

1. Actualiza `VERSION` con el número nuevo (`X.Y.Z`).
2. Crea el commit y la etiqueta:

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

3. Publica una release en GitHub con esa etiqueta. La CLI consulta primero la release; si no
   existe, cae a la lista de tags y elige la versión mayor.

La etiqueta y el contenido de `VERSION` deben coincidir: `VERSION` es lo instalado; la etiqueta
o release, lo publicado.

## Qué no hace

- No se auto-actualiza, no ejecuta `git pull` y no instala nada.
- No requiere autenticación ni token de GitHub.
- No consulta la red sin `--check-updates` ni con `GNS3LAB_NO_UPDATE_CHECK=1`.
- No modifica proyectos, nodos ni configuración del servidor GNS3.
- No cambia el código de salida de `doctor` por un fallo de la comprobación.
