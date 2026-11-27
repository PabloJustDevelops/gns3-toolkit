# Informe consolidado — swarm 2 (DAG `gk7-swarm2`)
Seis informes de cinco agentes (`gpt-6-luna` high ×2, `gpt-6.1-terra` medium, hy4 flash, hungerg) más una revisión con `gpt-6.2-sol` low. Base `58f5b52`. Cada hallazgo fue contrastado con el código real por la revisión; lo que no se pudo ejecutar se marca como no verificado.
## Alta prioridad (12)
| Prioridad | Hallazgo | Reportado por | Evidencia |
|---|---|---|---|
| Alta | La redacción altera el XML de configuración de pfSense | Codex Core, Hy4 | `pfsense.py:263` transforma stdout antes de que `get_config()` lo parsee en `pfsense.py:294-300`. Una coincidencia puede invalidar el XML o alterar un valor que acabe guardado. |
| Alta | Una asignación parcial puede duplicar una interfaz física | Codex Core | `pfsense.py:418-444` detecta duplicados entre valores recibidos y conserva los roles omitidos. |
| Alta | Consola con falso éxito tras cierre o sin cumplir `expect` | Codex Core, Hy4 | `gns3core.py:927-936,998-999,1023-1047` sale por cierre o quietud, calcula `ok` solo por timeout y la cadena solo se detiene por timeout. |
| Alta | Operaciones destructivas sin confirmación uniforme en el batch | Codex MCP, Hy4 | `gns3_mcp_server.py:3784-3805` usa una lista parcial de operaciones bloqueadas. La política debe cubrir todas las mutaciones destructivas equivalentes. |
| Alta | La redacción puede dejar parte de una contraseña | Codex MCP, Hy4 | `gns3_mcp_server.py:569-586,4000-4009` sustituye los nombres de usuario antes de las contraseñas. Si coinciden parcialmente, la sustitución cambia el texto buscado por la siguiente pasada. |
| Alta | Una exportación MCP puede dejar nodos detenidos | Codex MCP | `gns3_mcp_server.py:3044-3056` para nodos antes del `try` y rearranca en un único bucle sin aislamiento por nodo. Los estados HTTP de ambas operaciones se ignoran. |
| Alta | La reconstrucción de WAN depende de un `uuid` fuera de alcance | Codex CLI, Hy4 | `cli/gns3lab:1179-1201` usa `uuid` sin import global. Los imports en `cli/gns3lab:1301,1354,1442` son locales. |
| Alta | `examen setup` anuncia que el kit está listo pese a un fallo de arranque | Codex CLI, Hy4 | `cli/gns3lab:3658-3668` imprime el fallo, agrega los estados como texto y devuelve 0 sin evaluarlos. |
| Alta | Un fallo de precondición puede dejar un proyecto vacío que bloquea el reintento | Codex CLI | `cli/gns3lab:3555-3563` crea antes de resolver QEMU en `cli/gns3lab:3593`. La excepción de `cli/gns3lab:3494-3495` deja el nombre ocupado y `cli/gns3lab:3524-3528` devuelve 0 por mera existencia. |
| Alta | `examen setup` ignora el fallo de escritura de la marca que requiere `reset` | Codex CLI, Hy4, SWARM (swcli) | `cli/gns3lab:3652-3656` descarta el resultado HTTP. `cli/gns3lab:3797-3805` comprueba la marca antes de reiniciar. |
| Alta | `rule()` acepta extremos IPv4/CIDR mal formados | SWARM (swpf, Hermes) | `pfsense.py:194-199,529-537` decide la etiqueta por la presencia de una barra e incorpora el literal al XML sin validación de dirección o prefijo. |
| Alta | Los tres fallos históricos de `ClienteExamenFalso` | SWARM (cinco carriles, Hermes) | **Resuelto.** `tests/test_pf_console.py:269` implementa `json_list_or_die()`. Los casos históricos pasan en la selección dirigida indicada abajo. |

## Media prioridad (25)
| Prioridad | Hallazgo | Reportado por | Evidencia |
|---|---|---|---|
| Media | Rutas de archivos sin codificar en la URL | Codex Core, Hy4 | `gns3core.py:168,550-554,582-584,835-851` interpola los nombres en la URL. Los caracteres reservados pueden cambiar el recurso que recibe la operación. |
| Media | El rango DHCP puede quedar fuera de la red de la interfaz | Codex Core | `pfsense.py:476-502` valida formato y orden, resuelve el rol y copia el rango sin compararlo con su IP y máscara. |
| Media | `verify vpcs` rechaza gateways válidas por su último octeto | Codex Core | `gns3core.py:1552-1569` falla por terminación antes de considerar el prefijo. En una subred /23 existen hosts válidos con esos octetos finales. |
| Media | `lab apply --json` mezcla progreso y resultado estructurado | Codex CLI | `cli/gns3lab:4589-4595` ejecuta el aplicador antes de emitir el resultado y `scripts/labspec.py:443-459` escribe el progreso por stdout. La opción global puede envolverlo como texto y perder el esquema de `lab`. |
| Media | `all` ignora el JSON local | Codex CLI, Hy4 | `cli/gns3lab:2722-2728` siempre imprime un resumen humano. El envoltorio global es independiente en `cli/gns3lab:4655-4691`. |
| Media | `examen verify --json` queda sin respuesta estructurada si cae el servidor | Codex CLI | `cli/gns3lab:4079-4086` retorna 2 por la caída antes de llegar a `_examen_verify()`, que sí formatea esa situación en `cli/gns3lab:3703-3706`. |
| Media | `test` puede pasar con VPCS sin comprobar | Codex CLI | `cli/gns3lab:1066-1087` omite nodos sin consola o con error de conexión. `cli/gns3lab:1117-1135` solo cuenta fallos de los pings que pudo ejecutar. |
| Media | El fallback de PCAP puede atribuir la captura al enlace equivocado | Codex MCP | `gns3_mcp_server.py:2110-2133` sustituye la descarga fallida por el PCAP más reciente del proyecto, y lo guarda con la etiqueta del enlace solicitado. |
| Media | Importar por MCP exige un proyecto previo para una operación que crea uno nuevo | Codex MCP | `gns3_mcp_server.py:3033-3036,2445-2453` resuelve y abre un proyecto antes de la rama que genera su propio ID en `gns3_mcp_server.py:3080-3090`. |
| Media | Un reintento de lectura puede cerrar el cliente HTTP prestado a otro hilo | Codex MCP | `gns3_mcp_server.py:110-143,3960-3966` comparte el cliente entre lecturas y lo cierra sin sincronizar las solicitudes que ya lo obtuvieron. |
| Media | Dos capturas concurrentes pueden guardar en la misma ruta | Codex MCP | `captures.py:35-42,52-63,88-107` calcula el número a partir del directorio sin reservarlo antes de guardar y hacer OCR. |
| Media | Una captura WebUI puede registrar una página de error como evidencia válida | Codex MCP | `webui_capture.py:180-196` comprueba el login inicial, ignora la respuesta de cada navegación y devuelve éxito si las capturas terminaron sin excepción. |
| Media | `pf detect` omite el adaptador que espera `lab verify` | Hy4, HungerG | `pfsense.py:94-102` devuelve solo WAN/LAN. `cli/gns3lab:4147-4159,4221-4229` agrega el adaptador solo en el fallback, mientras `scripts/labspec.py:532-548` exige `data.adapter_type`. |
| Media | `watch --json` escribe un resumen humano en stdout | SWARM (swcli, Hermes) | `cli/gns3lab:2906-2917` emite los eventos y luego el resumen como texto. El texto rompe la salida estructurada incluso si el consumidor admite un flujo de eventos. |
| Media | `vm vms --json` emite varios documentos en una consulta | SWARM (swcli, Hermes) | `cli/gns3lab:2758-2774` recorre ambos motores por defecto y llama al formateador por cada respuesta exitosa. |
| Media | Borrados explícitos de CLI sin confirmación homogénea | SWARM (swcli) | `cli/gns3lab:1857-1865,2261-2264,2425-2432,2514-2518` ejecuta los borrados de snapshot, nodo, dibujo y enlace sin pasar por `_confirm` en esos caminos. |
| Media | `exec` puede terminar con un traceback por un cierre después de conectar | SWARM (swcli) | `cli/gns3lab:1912-1933` captura `ConsoleError` solo al obtener la consola. `gns3core.py:914-919,942-955,985` permite el mismo error durante el envío desde `wait_ready()` o `run_many()`. |
| Media | `lab` en modo humano omite el mensaje de error | SWARM (swcli) | `cli/gns3lab:4634-4636` pasa el error solo como dato. `cli/gns3lab:4403-4410` imprime en modo humano únicamente si recibe `texto`. |
| Media | `rule()` puede guardar un protocolo ajeno a su contrato | SWARM (swpf) | `pfsense.py:514-533` solo acota el protocolo en presencia de un puerto. Sin puerto persiste la cadena normalizada sin validarla. |
| Media | `rule()` rechaza una sección `<filter/>` vacía | SWARM (swpf) | `pfsense.py:24-29,534-537` convierte el elemento vacío en cadena y luego exige diccionario. |
| Media | El guion usa tres nombres de proyecto | HungerG | `docs/EXAMEN.md:9,16-18,69-71` declara `examen`, crea `Kit de examen` y opera sobre `examen-kit`. |
| Media | `examen verify` no comprueba los enlaces prometidos ni el mapa VLAN | HungerG | `docs/EXAMEN.md:17` anuncia enlaces. `cli/gns3lab:3725-3777` inspecciona los estados, discos, NAT y hace ping desde el primer VPCS arrancado, sin leer enlaces ni puertos. |
| Media | El NAT automático sin `target` causa un fallo funcional | SWARM (swpf) | `pfsense.py:564-568` sí deja una regla sin `target` en modo automático, y `tests/test_pfsense.py:534` cubre el cambio de modo. El artefacto por sí solo no demuestra un fallo con NAT automático ni tras volver a manual. |
| Media | Una máscara punteada en `<subnet>` hace fallar pfSense | SWARM (swpf) | `pfsense.py:142-155,466-467` efectivamente genera el formato punteado y `tests/test_pfsense.py:432` lo espera. El fixture parte de un prefijo. La diferencia de representación queda comprobada, pero su rechazo o efecto en la recarga no se ha acreditado. |
| Media | Guardar la IP en `<gateway>` impide crear la ruta por defecto | SWARM (swpf) | `pfsense.py:453-454,468-469` guarda la IPv4 y el test de IP y gateway fija esa representación. No hay comprobación de la ruta tras aplicar ni evidencia local de que el campo exija un nombre en este camino. |

## Recomendaciones
- `orchestration/auditorias/recomendaciones-hy4.md`: propuestas de producto contrastadas con grep.
- `orchestration/auditorias/recomendaciones-hungerg.md`: propuestas de flujo de examen que respetan «VNC último recurso» y clonación de imagen.
- La revisión con Sol 6.2 las valora al final de `revision-sol.md`.

## No verificado
- La suite completa dentro del sandbox de Codex falló por sockets bloqueados; se ejecutó desde el host antes del run: 931 passed.
- El efecto en un pfSense o GNS3 reales de los hallazgos no se probó: las reproducciones usan dobles en memoria.
- Los 5 hallazgos descartados y sus motivos están en `orchestration/auditorias/revision-sol.md`.

## Criterios del run
CRITERION c1 #bd79cf: met - `ls orchestration/auditorias/*.md | wc -l` → 6 informes (587 líneas), con fichero:línea y forma de verificarlo.
CRITERION c2 #bd79cf: met - `revision-sol.md` acepta 43 y descarta 5 con evidencia y motivo concreto.
CRITERION c3 #bd79cf: met - `python3 scripts/check-links.py` → `OK: sin enlaces rotos`; `python3 scripts/verify.py` → `comandos=48 tools=50 áreas=12 / OK: sin deriva`; sin literales de credenciales en los informes.
