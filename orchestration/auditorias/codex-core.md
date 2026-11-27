## Informe del revisor independiente

Encontró **seis bugs nuevos**. Los fragmentos se ejecutaron con `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY' … PY`: **exit 0**. Usaron dobles en memoria, sin modificar archivos ni contactar GNS3 o pfSense.

1. **P1 — La redacción de la contraseña altera el XML leído.** En pfsense.py:263 (pfsense.py:263), `run()` sustituye la contraseña en todo el `stdout`; get_config() lo parsea después (pfsense.py:298). Si la contraseña aparece en un valor, una operación de configuración puede guardar `***` en su lugar. Si aparece en una etiqueta, el XML puede dejar de parsearse.

   Reproducir con contraseña de ejemplo y XML `<pfsense><system/></pfsense>`: `get_config()` devuelve `{'ok': False, 'error': 'config.xml no es XML válido: not well-formed (invalid token): line 1, column 1'}`. **Verificado con un doble; el efecto en un firewall real no se probó.**

2. **P1 — Una asignación parcial puede duplicar una interfaz física.** En pfsense.py:427 (pfsense.py:427), `assign()` solo detecta duplicados dentro del mapping nuevo; no comprueba los roles que conserva del documento. `assign({'lan': 'em0'})` con WAN ya asignada a `em0` devuelve `{'ok': True}` y deja WAN y LAN en `em0`.

   **Impacto:** configuración WAN/LAN conflictiva, con riesgo de perder conectividad. La configuración generada se verificó; la respuesta del firewall no.

3. **P1 — La consola devuelve éxito tras cerrarse o no recibir el `expect`.** En gns3core.py:1036 (gns3core.py:1036), `ok` solo depende de `timed_out`. EOF o quietud sin encontrar el marcador terminan con `ok=True`; `run_many()` solo se detiene por timeout.

   Reproducir EOF durante `run('show ip')` o `run('reboot', expect='READY', idle=.001)`: ambos devuelven `ok=True`, `timed_out=False` y salida vacía. **Verificado en memoria.**

4. **P2 — No se codifican los nombres de archivo en la URL.** En gns3core.py:849 (gns3core.py:849), el path se interpola sin escapar; el mismo patrón aparece en otras funciones de archivos. `node_file_write(..., 'config#backup.txt', ...)` genera la ruta `/v2/projects/p/nodes/n/files/config`: `#backup.txt` desaparece como fragmento y la API puede informar éxito al escribir sobre `config`.

   **Impacto:** se puede escribir en un archivo distinto del solicitado. La URL generada se verificó; no se hizo una escritura real en GNS3.

5. **P2 — El rango DHCP puede quedar fuera de la subred de la interfaz.** En pfsense.py:502 (pfsense.py:502), se valida el formato y el orden de las IP, pero no su pertenencia a la subred. Con LAN `192.168.10.1/24`, `dhcp('lan', '10.0.0.10', '10.0.0.20')` devuelve `ok=True` y guarda ese rango.

   **Impacto:** el pool puede impedir que clientes LAN obtengan concesiones utilizables. El documento generado se verificó; el comportamiento de DHCP en pfSense no.

6. **P2 — `verify vpcs` rechaza gateways válidas terminadas en `.0` o `.255`.** En gns3core.py:1556 (gns3core.py:1556), se clasifica por último octeto antes de comprobar la subred. En una red `/23`, `192.168.11.0` es una dirección de host válida; aun así, `verify` la marca como error de gateway.

   **Impacto:** falso negativo y recomendación de cambiar una configuración correcta. Reproducido con `192.168.10.10/23`, gateway `192.168.11.0`; la comprobación devuelve `ok=False` con “parece la máscara”. No requiere firewall real.

Los issues #23–#25 se pudieron consultar y se excluyeron al comparar: cubren salida JSON de CLI, validación `rule(src/dst)` y problemas de instrucciones/pytest. El árbol estaba limpio al inicio. **No ejecuté la suite completa ni verifiqué los efectos de escritura o aplicación en servidores reales.**