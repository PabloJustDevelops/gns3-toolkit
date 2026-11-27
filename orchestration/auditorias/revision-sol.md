# Revisión independiente de los informes de gns3-toolkit

Código contrastado en el árbol de trabajo sobre `58f5b52`. Fuentes: `codex-core.md`, `codex-cli.md`, `codex-mcp.md`, `recomendaciones-hy4.md`, `recomendaciones-hungerg.md` y `orchestration/SWARM-INFORME.md`. Para las entradas abreviadas de SWARM se consultaron también sus informes de carril. Las referencias son líneas del árbol actual.

**43 hallazgos aceptados y 5 descartados.** Cada fila cuenta una vez. Las coincidencias entre fuentes se agrupan. Las mejoras de producto se valoran al final.

## Hallazgos aceptados

| Prioridad | Hallazgo | Quién lo reportó | Evidencia verificada |
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
| Baja | El ejecutable `pytest` documentado falla al importar módulos | SWARM (swcore, Hermes) | `AGENTS.md:44-45` indica el ejecutable y `pytest.ini:1-2` solo fija `testpaths`. Con entorno limpio se reproducen cinco errores de colección. |
| Baja | El comprobador de enlaces declara rotos los destinos locales con número de línea | Hy4 | `scripts/check-links.py:18,31-38,58-62` trata el sufijo de línea como parte del fichero. Resultado actual: 23 incidencias. El paso de CI de `.github/workflows/ci.yml:39-40` ejecuta el otro comprobador, `verify.py`. |
| Baja | Cifras desactualizadas en `AGENTS.md` | SWARM (swmcp, Hermes) | `AGENTS.md:13,15` declara 47 comandos y 700 pruebas. Las ejecuciones actuales verifican 48 comandos y 931 pruebas colectadas. `scripts/verify.py:17,181-182` deja fuera `AGENTS.md` de la comprobación documental de cifras. |
| Baja | `templates` no valida la forma del listado | SWARM (swcli) | `cli/gns3lab:1571-1579` solo comprueba HTTP y aplica `t.get()` a cada elemento. Si recibe un objeto en vez de una lista, itera sus claves y puede fallar. El error HTTP solo imprime el estado y el JSON global sigue disponible. |
| Baja | Varias ramas CLI muestran el cuerpo HTTP crudo | SWARM (swcli) | `cli/gns3lab:422,428,2109,2270,2381` incluye el cuerpo directamente en lugar del mensaje interno. |
| Baja | `_err()` pierde el mensaje interno con determinadas representaciones del schema | SWARM (swcli) | `cli/gns3lab:2117-2125` solo extrae `message` entre comillas dobles y devuelve hasta 400 caracteres del error original si no coincide. |
| Baja | `rule()` valida un puerto convertido y guarda el valor original | SWARM (swpf) | `pfsense.py:517-531` comprueba `int(port)`, pero persiste `str(port)`. Afecta al contrato de la API Python, aun cuando la CLI ya convierte el argumento. |
| Baja | `ifconfig` punto a punto pierde la IPv4 | SWARM (swpf) | `pfsense.py:158-177` espera `netmask` inmediatamente después de la dirección. Una línea con extremo remoto intercalado deja la interfaz sin IP parseada. |
| Baja | La ida y vuelta de XML pierde comentarios, declaración y parte del texto mixto | SWARM (swpf) | `pfsense.py:24-45,48-58,84-91` usa el parseo por defecto, no representa `tail` y serializa sin declaración. Es pérdida de fidelidad. Las secciones desconocidas de solo elementos sí se conservan. |
| Baja | Documentación de capturas obsoleta y contrato CLI incompleto | HungerG | `docs/CAPTURAS-EXAMEN.md:13-28` marca ausentes módulos y entradas implementados en `captures.py:45,126`, `webui_capture.py:92`, `cli/gns3lab:4008-4066` y `gns3_mcp_server.py:980,1095`. La CLI fija PF1 y no escribe índice, y el parser de `lab` aún no expone `--captures` en `cli/gns3lab:5129-5152`. |

## Hallazgos descartados

| Prioridad alegada | Hallazgo | Quién lo reportó | Evidencia verificada y motivo |
|---|---|---|---|
| Alta | Los tres fallos históricos de `ClienteExamenFalso` | SWARM (cinco carriles, Hermes) | **Resuelto.** `tests/test_pf_console.py:269` implementa `json_list_or_die()`. Los casos históricos pasan en la selección dirigida indicada abajo. |
| Media | El NAT automático sin `target` causa un fallo funcional | SWARM (swpf) | `pfsense.py:564-568` sí deja una regla sin `target` en modo automático, y `tests/test_pfsense.py:534` cubre el cambio de modo. El artefacto por sí solo no demuestra un fallo con NAT automático ni tras volver a manual. |
| Media | Una máscara punteada en `<subnet>` hace fallar pfSense | SWARM (swpf) | `pfsense.py:142-155,466-467` efectivamente genera el formato punteado y `tests/test_pfsense.py:432` lo espera. El fixture parte de un prefijo. La diferencia de representación queda comprobada, pero su rechazo o efecto en la recarga no se ha acreditado. |
| Media | Guardar la IP en `<gateway>` impide crear la ruta por defecto | SWARM (swpf) | `pfsense.py:453-454,468-469` guarda la IPv4 y el test de IP y gateway fija esa representación. No hay comprobación de la ruta tras aplicar ni evidencia local de que el campo exija un nombre en este camino. |
| Baja | `PfSense.status().interfaces` cambia de diccionario a cadena en caso de error | SWARM (swpf) | `pfsense.py:263-270,274-288` devuelve texto de `ifconfig` o texto de error. El diccionario pertenece a otro método, `interfaces()` en `pfsense.py:377`. La CLI sí cuenta caracteres como interfaces en `cli/gns3lab:4290-4293`, una observación distinta del supuesto cambio de tipo. |

También se acota el alcance de los hallazgos aceptados. El fallo de recuperación del export se verifica para excepciones de parada o rearranque. Un error HTTP devuelto como valor se ignora y sigue otro camino. La pérdida de metadatos y texto mixto del XML se verifica en el parser. El informe de SWARM no acredita que la ausencia de la declaración o de comentarios cause un fallo en pfSense. La exclusión de código inline propuesta para el comprobador de enlaces ya existe en `scripts/check-links.py:58`.

## Valoración de producto y examen

- **Fiabilidad antes que automatización.** Las propuestas de Hy4 atacan problemas vigentes. Para redacción, preservar el XML dentro de la lectura interna y mantener la redacción en las salidas públicas. Para consola y batch, fijar contratos explícitos de resultado y confirmación. Para CLI, mantener una respuesta estructurada estable y distinguir arranque incompleto, marca no escrita y proyecto incompleto.
- **Guion y preflight.** Unificar el nombre y precisar qué comprueba `verify` tiene efecto inmediato. Mover la comprobación del binario QEMU antes de crear el proyecto responde a un defecto confirmado. Validar imagen, clon y adaptador encaja con el perfil de examen. `setup` ya crea un linked clone y usa telnet por defecto en `cli/gns3lab:3520,3587-3600`. Exigir siempre un proyecto origen o eliminar VNC/SPICE ampliaría el alcance. La documentación ya distingue la instalación inicial en `docs/PFSENSE-NATIVO.md:6-13`, aunque el guion del examen aún mezcla esa ruta con la de imagen preparada en `docs/EXAMEN.md:74-75,256-257`.
- **Checkpoint y rollback.** Aportan valor para repetir el examen. El guion ya documenta un snapshot manual en `docs/EXAMEN.md:78-84`. `setup` arranca tras escribir la marca y `reset` para y vuelve a arrancar, como se ve en `cli/gns3lab:3652-3658,3809-3819`. Automatizar un checkpoint anterior al arranque y ofrecer restauración serían funciones nuevas.
- **Bootstrap y vía nativa.** Conviene explicitar cuándo se necesita consola o HMP para llegar a SSH. Un bootstrap guiado por prompts puede recortar pasos manuales en `docs/EXAMEN.md:108-131`. Tras SSH, la edición nativa cubre asignación de interfaces existentes, IP, DHCP, reglas y NAT. Crear la VLAN que usa el guion en `docs/EXAMEN.md:165-175` sigue siendo un paso aparte. La propuesta de reemplazar todo el menú con los comandos actuales queda así acotada.
- **Verificación de examen y VPN.** Dar prioridad a comprobar enlaces, puertos, VLAN y conectividad de cada VPCS. Un ping a Internet solo prueba la salida desde el origen que lo ejecuta. La VPN aporta valor si forma parte de la evaluación. Hace falta definir el tipo de VPN, el peer y el tráfico esperado antes de diseñar una comprobación que distinga túnel y conectividad general. `gns3core.py:1305` registra únicamente `qemu`, `pf` y `vpcs`.
- **Capturas.** Actualizar primero el inventario de funciones existentes. El índice de la CLI, la selección de nodo y `--captures` en `lab apply/verify` completan el contrato pendiente. La opción `--phase` anuncia alcance de consola y directorio en `cli/gns3lab:5049-5050`. Darle semántica de selección de páginas WebUI sería una ampliación. Para evidencia de examen, resolver primero las colisiones de nombres y comprobar que la página capturada es la esperada.

## Comprobaciones ejecutadas

| Comando | Código | Salida relevante |
|---|---|---|
| `git rev-parse --short HEAD` | 0 | `58f5b52` |
| `python3 -B scripts/check-links.py` | 1 | `ROTO: 23 hallazgos` en los tres informes Codex. |
| `python3 -B scripts/verify.py` | 0 | `comandos=48 tools=50 áreas=12`, `OK: sin deriva`. |
| `env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider --collect-only` | 2 | `879 tests collected, 5 errors in 1.11s`, con `ModuleNotFoundError` de módulos del repo. |
| `.venv/bin/python -E -B -m pytest -q -p no:cacheprovider --collect-only` | 0 | `931 tests collected in 0.93s`. |
| `.venv/bin/python -E -B -m pytest -q -p no:cacheprovider tests/test_pf_console.py -k examen_setup --tb=short` | 0 | `4 passed, 15 deselected in 0.79s`. |
| `.venv/bin/python -E -B -m pytest -q -p no:cacheprovider` | 1 | `38 failed, 479 passed, 414 errors in 14.41s`. El entorno bloqueó la creación de sockets locales en fixtures HTTP y telnet con `PermissionError: [Errno 1] Operation not permitted`. La ejecución no permite certificar la suite completa. |

Las entradas técnicas se contrastaron por lectura directa de las líneas indicadas. No se contactó un servidor GNS3, un firewall pfSense ni un peer VPN para verificar efectos en vivo.
