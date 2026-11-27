## Hallazgos

1. **[P1] El batch permite operaciones destructivas sin `confirm`** — gns3_mcp_server.py:3792 (gns3_mcp_server.py:3792)  
   `gns3_batch` bloquea `gns3_node_edit(action="delete")`, pero permite borrados equivalentes mediante `gns3_nodes(action="delete", node="*")`. También omite `gns3_template(delete)`, `gns3_snapshots(restore/delete)` y `gns3_drawings(clear/delete)`.  
   **Verificación:** usar el doble de `tests/test_mcp_nodes.py` desde `gns3_batch` sin `confirm` y comprobar que se ejecuta el DELETE.

2. **[P1] La redacción puede dejar parte de una contraseña** — gns3_mcp_server.py:572 (gns3_mcp_server.py:572)  
   Se sustituye el usuario antes que la contraseña. Con `GNS3_USER=admin` y `GNS3_PASSWORD=<valor de ejemplo>`, un error que contenga la contraseña puede quedar como `[redactado]-123456`. El mismo orden aparece en `_redact_informe`.  
   **Verificación:** ampliar `test_lab_action_error_redacta_detail_anidado` con credenciales solapadas y comprobar que no sobrevive el sufijo.

3. **[P1] Un fallo al parar nodos puede dejarlos detenidos durante un export** — gns3_mcp_server.py:3049 (gns3_mcp_server.py:3049)  
   La parada de nodos ocurre antes del `try/finally` que los rearranca. Si una parada posterior falla, los nodos ya detenidos no se recuperan. Además, una excepción al rearrancar puede impedir intentar los restantes.  
   **Verificación:** con un cliente falso de dos nodos arrancados, hacer que la primera parada tenga éxito y la segunda falle; comprobar que se intentan los rearranques pertinentes.

4. **[P2] El fallback de captura puede devolver el PCAP de otro enlace** — gns3_mcp_server.py:2123 (gns3_mcp_server.py:2123)  
   Si falla la descarga REST, se elige el `.pcap` más reciente del proyecto. Al pedir una captura, podría guardarse bajo el identificador del enlace solicitado el tráfico de otro enlace.  
   **Verificación:** preparar dos PCAP con contenido y fechas distintos, forzar un 409 para el enlace antiguo y comprobar qué bytes se devuelven.

5. **[P2] La importación exige un proyecto existente** — gns3_mcp_server.py:3033 (gns3_mcp_server.py:3033)  
   `action="import"` llama primero a `_pid_or_error`, que requiere resolver y abrir un proyecto. Así, importar en un servidor sin proyectos —o con varios sin selección— falla antes de la importación, que genera su propio UUID.  
   **Verificación:** usar un cliente falso con `/v2/projects=[]` y un archivo importable; comprobar que la ejecución termina antes del POST de importación.

6. **[P2] La recuperación de una lectura puede cerrar un cliente HTTP compartido** — gns3_mcp_server.py:129 (gns3_mcp_server.py:129)  
   Las lecturas del batch comparten el mismo `httpx.Client`. Si una lectura lo cierra al recuperarse de una conexión rota mientras otra lo tiene prestado, la segunda puede fallar con `RuntimeError("Cannot send a request, as the client has been closed.")`.  
   **Verificación:** coordinar dos hilos con barreras y forzar `RemoteProtocolError` en uno; comprobar si la otra lectura intenta usar el cliente cerrado.

7. **[P2] Dos capturas concurrentes pueden sobrescribirse** — captures.py:55 (captures.py:55)  
   Dos llamadas con el mismo `outdir` y fase pueden calcular el mismo número de captura y escribir la misma ruta. Ambas podrían devolver `ok=True`, aunque una captura sustituya a la otra y el OCR no corresponda a la imagen conservada.  
   **Verificación:** sincronizar dos monitores falsos tras calcular el número y comprobar que se conservan ambas capturas en rutas distintas.

8. **[P2] La captura web puede marcar como válida una página fallida** — webui_capture.py:186 (webui_capture.py:186)  
   Tras el login inicial, se ignora la respuesta de cada `goto` y no se comprueba si la página volvió al formulario de acceso. Una respuesta 404/500 o una redirección al login puede terminar registrada como captura válida, con `ok=True`.  
   **Verificación:** hacer que `FakePage.goto` devuelva 500 o muestre el login al navegar a `firewall_rules.php`; comprobar que activa el fallback y no registra esa página como captura válida.

La revisión independiente fue estática. No se ejecutaron pruebas; los escenarios indicados quedan pendientes de ejecución.