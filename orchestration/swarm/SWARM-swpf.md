# SWARM-swpf — auditoría pfSense nativa

- Repo/worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-swpf`, rama `opencode/swpf`, HEAD `ce2b20e`.
- Alcance: `pfsense.py` y `docs/PFSENSE-NATIVO.md`. No se ha escrito código de producción, no se han modificado tests, no commit ni PR.
- Verificación de línea base en esta sesión:
  - `.venv/bin/python -m pytest -q` → `3 failed, 928 passed`. Los 3 fallos son **preexistentes** y están fuera de este alcance: `tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[None-telnet|vnc-vnc|spice-spice]` → `AttributeError: 'ClienteExamenFalso' object has no attribute 'json_list_or_die'` en `cli/gns3lab:3470`. No son hallazgos de `pfsense.py`/`PFSENSE-NATIVO.md`.
  - `.venv/bin/python scripts/verify.py` → `OK: sin deriva`, exit 0 (`comandos=48 tools=50 áreas=12`).
  - `.venv/bin/python scripts/check-links.py` → `OK: sin enlaces rotos`, exit 0.
- Los hallazgos siguientes se reproducen **sin pfSense real**, doblando `get_config()`/`put_config()` y llamando a las funciones reales. Lo que depende del comportamiento de pfSense 2.7 al releer/aplicar `config.xml` se marca como **no verificado contra un firewall vivo**; el artefacto generado por `pfsense.py` sí se ha observado.

## Hallazgos priorizados (máximo 10)

### 1. `_endpoint()` no valida `src`/`dst`, y `rule()` devuelve `ok=True` con IP/CIDR inválidos
- **Fichero:línea:** `pfsense.py:194-200` (`_endpoint`), `pfsense.py:511-542` (`PfSense.rule`), especialmente `pfsense.py:529-533`.
- **Qué pasa:** `_endpoint()` sólo distingue `any`, `network` si hay `/`, y `address` en caso contrario. No llama a `ipaddress`, no comprueba que una red CIDR sea una red real (`192.168.1.1/24` no es `192.168.1.0/24`), no rechaza cadenas vacías ni alias inexistentes. `rule()` sólo valida `action`, `port` y `proto tcp/udp` cuando hay `port`; nunca `src`/`dst`. `_load_and_save()` acaba llamando `put_config()` y `rule()` devuelve `ok=True` si la recarga simulada/real devuelve 0.
- **Impacto concreto:** se puede persistir una regla `<source><address>nope</address>`, `<destination><network>999.999.999.999/99</network>`, `<address></address>`, etc. La API dice éxito; pfSense puede ignorar o no aplicar esa regla. Contrasta con `nat()` (`target` valida IPv4, `pfsense.py:546-550`) y `set_ip()` (`pfsense.py:450-456`). **Aplicación en pfSense no verificada**; el artefacto inválido sí se genera.
- **Reproducir/verificar:**
  ```python
  import pfsense
  pf = pfsense.PfSense(password=os.environ["PFSENSE_PASSWORD"])
  doc = pfsense.parse_config("<pfsense><system/><interfaces><lan><if>em1</if></lan></interfaces><filter/></pfsense>")
  # OJO: con <filter/> vacío cae en hallazgo 5; usa <filter><rule/></filter> o sin <filter>
  doc = pfsense.parse_config("<pfsense><system/><interfaces><lan><if>em1</if></lan></interfaces><filter><rule/></filter></pfsense>")
  pf.get_config = lambda: doc
  cap = {}
  pf.put_config = lambda d, backup=True: (cap.__setitem__("doc", d), {"ok": True})[1]
  r = pf.rule(action="pass", ifname="lan", proto="tcp", src="nope", dst="999.999.999.999/99")
  print(r["ok"], cap["doc"]["filter"]["rule"][0])
  ```
  Salida observada: `True {... 'source': {'address': 'nope'}, 'destination': {'network': '999.999.999.999/99', ...}}`. `_endpoint("wan") → {'address': 'wan'}`; `_endpoint("192.168.1.1/24") → {'network': '192.168.1.1/24'}`.
- **Además:** `_endpoint("wan"/"lan"/"wanip")` usa `<address>`, no `<network>`. **No verificado contra pfSense vivo**; en el árbol sólo se exige `any`/IP/CIDR.

### 2. `rule()` no valida `proto`
- **Fichero:línea:** `pfsense.py:511-537`, `pfsense.py:514` (`proto = str(proto).lower()`).
- **Qué pasa:** sólo `action` se restringe a `pass|block|reject`. `proto` se normaliza a minúsculas y se escribe `<protocol>...`. `proto="nonsense"` no falla; con `port`, sólo se exige `proto in ("tcp","udp")`. No hay lista de protocolos pfSense (`any`, `tcp`, `udp`, `tcp/udp`, `icmp`, `esp`, `ah`, `gre`, ...).
- **Impacto concreto:** `rule()` devuelve `ok=True` y `_insert_rule()` añade `<protocol>nonsense</protocol>`; pfSense no carga una regla con protocolo inexistente. **Aplicación en pfSense no verificada**; el `ok=True` + `<protocol>nonsense</protocol>` sí se observa.
- **Reproducir/verificar:** con `pf` dobleado como arriba, `pf.rule(action="pass", ifname="lan", proto="nonsense", src="any", dst="any")` → `ok True`, `<protocol>nonsense</protocol>`. La CLI `gns3lab pf rule ... --proto nonsense` pasa el valor sin `choices` (`cli/gns3lab`, parser `pf rule`, `--proto default=any`; fuera de alcance pero relevante).

### 3. `rule()` guarda `port` como la cadena original, no el entero validado
- **Fichero:línea:** `pfsense.py:517-531`, `pfsense.py:519-523`, `pfsense.py:531`.
- **Qué pasa:** `number = int(port)`; se valida `1 <= number <= 65535` y `proto in ("tcp","udp")`; pero `destination["port"] = str(port)`, no `str(number)`. `port=80` y `port="80"` dan `"80"`, pero `port="080"`, `port="80 "`, `port=80.0`, `port=True` producen `<port>080</port>`, `<port>80 </port>`, `<port>80.0</port>`, `<port>True</port>`. 
- **Impacto concreto:** `rule()` `ok=True`, pero el XML contiene un puerto que no es el entero canónico que se acaba de validar; `_config_contains` (`pfsense.py:121-139`) compara cadenas exactas. `intval`/`int` en pfSense podría tolerar algunos casos; **no verificado contra pfSense vivo**. Artefacto inválido sí generado.
- **Reproducir/verificar:** `pf.rule(action="pass", ifname="lan", proto="tcp", port="080")` → `ok True`, `<port>080</port>`. Salida observada. Con CLI `gns3lab pf rule ... --port`, `argparse type=int`, pero la API `PfSense.rule(port=...)` no coacciona.

### 4. `nat()` en `mode=automatic` inserta un `<rule>` saliente sin `<target>`
- **Fichero:línea:** `pfsense.py:544-573`, `pfsense.py:564-568`, `_insert_rule` `pfsense.py:180-191`.
- **Qué pasa:** siempre `_insert_rule(outbound, rule)`. `rule = {"interface": role, "source": {"any": ""}, "destination": {"any": ""}}`; sólo se añade `"target"` si `target is not None`. Con `target=None` se pone `outbound["mode"]="automatic"` **y** se inserta regla. No se eliminan reglas previas.
- **Impacto concreto:** `nat(ifname="wan")` devuelve `ok=True` y deja `<nat><outbound><mode>automatic</mode><rule>...sin target...</rule>...`. Una llamada posterior `nat(ifname="wan", target=X)` pone `mode=manual` e inserta la regla con `target` antes de `reject`, pero **después** de la regla sin `target`. En NAT manual, la regla genérica puede preceder a la específica. Los tests fijan el artefacto (`tests/test_pfsense.py::test_nat_inserta_antes_del_reject_y_fija_modo`) pero no prueban pfSense. **Efecto en pfSense no verificado contra firewall vivo**.
- **Reproducir/verificar:**
  ```python
  pf.nat("wan")                 # automatic
  print(cap["doc"]["nat"]["outbound"])  # {'mode':'automatic','rule':[{'interface':'wan','source':{'any':''},'destination':{'any':''}}]}
  pf2.nat("wan", target="192.0.2.10")
  # en manual: [no-target..., {'target':'192.0.2.10'...}, ...]
  ```
  Salida observada. El test `test_nat_rechaza_target_interfaz_u_outbound_invalidos` sólo comprueba `mode`/`rule[0]`, no ausencia de regla sin `target`.

### 5. `_parse_ifconfig()` no extrae IPv4 en interfaces punto-a-punto (`inet X --> Y netmask`)
- **Fichero:línea:** `pfsense.py:158-177`, `pfsense.py:168`.
- **Qué pasa:** `address = re.search(r"\binet\s+(\S+)\s+netmask\s+(\S+)", line)`. FreeBSD emite `inet 100.64.0.2 --> 100.64.0.1 netmask 0xffffffff` en interfaces `POINTOPOINT` (`ppp0`, túneles...). Tras `(\S+)` (`100.64.0.2`) viene `-->`, no `netmask`, así que no hay match. La interfaz se registra `{}`. 
- **Impacto concreto:** `PfSense.interfaces()` (`pfsense.py:377-408`) usa `_parse_ifconfig()`; para `ppp0`/punto-a-punto `ip=""`, `mask=<subnet configurado o "">`. `assign()` no se afecta (sólo lista nombres), pero la verificación de IP/máscara falla. **No verificado contra pfSense con PPPoE; reproducido con salida FreeBSD representativa.**
- **Reproducir/verificar:**
  ```python
  pfsense._parse_ifconfig(
      "ppp0: flags=8051<UP,POINTOPOINT,RUNNING,NOARP,MULTICAST> metric 0 mtu 1500\n"
      "    inet 100.64.0.2 --> 100.64.0.1 netmask 0xffffffff\n")
  ```
  Salida observada: `{'ppp0': {}}`. Comparar `em0 ... inet 192.0.2.1 netmask 0xffffff00` → `{'em0': {'ip': '192.0.2.1', 'mask': '255.255.255.0'}}`.

### 6. Un `<filter/>` vacío hace fallar `rule()` aunque `_insert_rule` soporta `rule` vacía
- **Fichero:línea:** `pfsense.py:24-45` (`_element_to_value`), `pfsense.py:534-537`, `pfsense.py:180-191`.
- **Qué pasa:** `_element_to_value` convierte `<filter/>`/`<filter></filter>` en `""`. `rule()` `filters = doc.setdefault("filter", {})` devuelve `""`; `if not isinstance(filters, dict): raise PfSenseError("la sección <filter> no es un diccionario")`. No resetea `""` a `{}`, pese a `_insert_rule` `existing == "" → []`. `nat()` sí resetea `nat`/`outbound` no-dict; `enable_ssh` resetea `system`/`ssh`; `rule()` no resetea `filter`.
- **Impacto concreto:** `PfSense.rule()` devuelve `ok=False`, `detail='la sección <filter> no es un diccionario'`, y no escribe regla en un `config.xml` con `<filter/>`. `_element_to_value` representa vacío como `""`. Test `test_rule_crea_seccion_filter_sin_reglas` sólo cubre **ausencia** de `filter`, no `<filter/>`.
- **Reproducir/verificar:**
  ```python
  xml = '<pfsense><system/><interfaces><lan><if>em1</if></lan></interfaces><filter/></pfsense>'
  pf.get_config = lambda: pfsense.parse_config(xml); pf.put_config = lambda d, backup=True: {"ok": True}
  pf.rule(action="pass", ifname="lan")["ok"]  # False; 'la sección <filter> no es un diccionario'
  ```
  Salida observada. `<filter><rule/></filter>` sí funciona (`_insert_rule` `existing==''`).

### 7. `_normalize_mask()` devuelve máscara punteada para `<subnet>`, inconsistente con pfSense `<subnet>CIDR</subnet>`
- **Fichero:línea:** `pfsense.py:142-155`, `pfsense.py:146`, `pfsense.py:153`; `PfSense.set_ip` `pfsense.py:448-474`, `pfsense.py:452`, `pfsense.py:467`; `PfSense.interfaces` `pfsense.py:396-405`.
- **Qué pasa:** `_normalize_mask()` docstring dice «devuelve la forma de config.xml», acepta punteada/CIDR y devuelve `str(ipaddress.IPv4Address(text))` o `netmask`. `_normalize_mask("24") → "255.255.255.0"`. `set_ip()` escribe `values["subnet"] = netmask`. Pero en `config.xml` pfSense usa `<subnet>24</subnet>` (CIDR); `_element_to_value`/`render_config` preservan el original; `interfaces()` lee `<subnet>24</subnet>`; el test de base `CONFIG_XML` usa `<subnet>24</subnet>`; el test `test_set_ip_normaliza_mascara_y_gateway` **fija** `subnet == "255.255.255.0"`. 
- **Impacto concreto:** `set_ip(ifname, ip, "24")` genera `<subnet>255.255.255.0</subnet>` en lugar de `<subnet>24</subnet>`. `_config_contains(parse_config(xml), verified)` (`pfsense.py:349`, `pfsense.py:121-139`) exige `"255.255.255.0"`; si pfSense reescribe a `"24"`, la verificación de reload-timeout falla. **Que pfSense 2.7 reescriba o rechace `<subnet>255.255.255.0</subnet>` no está verificado contra firewall vivo**; la inconsistencia interna y el artefacto sí. Doc `docs/PFSENSE-NATIVO.md:88` usa `... 24`, y CLI ayuda `(24 o 255.255.255.0)`.
- **Reproducir/verificar:**
  ```python
  pf.set_ip("em1", "192.168.10.2", "24", gateway="192.168.10.254")
  # original <subnet>24</subnet> -> escrito <subnet>255.255.255.0</subnet>
  pfsense._normalize_mask("24")           # '255.255.255.0'
  pfsense._normalize_mask("255.255.255.0")# '255.255.255.0'
  ```
  Salida observada. Sugerencia de verificación contra pfSense real: `pf.set_ip(..., mask="24")`, luego `pf.interfaces()` y `gns3lab pf config get`; comprobar `<subnet>`.

### 8. `set_ip()` `gateway` escribe IPv4 cruda en `<gateway>`, no un gateway pfSense con nombre
- **Fichero:línea:** `pfsense.py:448-474`, `pfsense.py:453-454`, `pfsense.py:468-469`.
- **Qué pasa:** `gateway = str(ipaddress.IPv4Address(gateway))`; `values["gateway"] = gateway`. `set_ip` no crea ni actualiza `<gateways><gateway_item><name>...</name><gateway>IP</gateway>...`. pfSense 2.7 suele usar `<interface>...<gateway>NOMBRE</gateway>` + `<gateway_item>`. 
- **Impacto concreto:** `gns3lab pf ip ... --gw IP` / `PfSense.set_ip(..., gateway=IP)` genera `<gateway>IP</gateway>`; `ok=True` si recarga devuelve 0; el default route puede no crearse. **No verificado contra pfSense vivo**; el artefacto `<gateway>192.168.10.254</gateway>` sí se observa. Test `test_set_ip_normaliza_mascara_y_gateway` fija IP cruda. Doc `docs/PFSENSE-NATIVO.md:87-89` dice «IP de la LAN y, si procede, gateway» sin aclarar nombre vs IP.
- **Reproducir/verificar:** `pf.set_ip("em1","192.168.10.2","24",gateway="192.168.10.254")` → `interfaces.lan.gateway == "192.168.10.254"`, sin cambios en `doc["gateways"]`. Verificación real: `pf.config` + `pf.status`/`netstat -rn` en pfSense.

### 9. `PfSense.status()` sustituye `interfaces` por una cadena de error; mezcla tipos
- **Fichero:línea:** `pfsense.py:272-290`, `pfsense.py:284-288`.
- **Qué pasa:** `result[key] = response["output"] if response["ok"] else response["error"]`. `interfaces` es `dict`/texto `ifconfig` si ok, pero `str` de error si `ifconfig` falla. `result["ok"]=False`, `errors` se añade. Otros campos siguen `str`. 
- **Impacto concreto:** consumidores que hacen `data["interfaces"].items()` / `len(...)` sobre un `dict` rompen o cuentan caracteres; `cli/gns3lab` `_pf_out` `len(data.get("interfaces") or {})` (fuera de alcance) puede imprimir longitud de string. `PfSense.status()` docstring `{"..."}` no fija esquema. **`PfSense.status()` no se ha ejecutado contra firewall real aquí**; reproducido doblando `run`.
- **Reproducir/verificar:**
  ```python
  pf.run = lambda cmd, timeout=None: ({'cmd':cmd,'output':'','ok':False,'error':'boom','returncode':1,'stderr':'boom'} if cmd=='ifconfig'
                                      else {'cmd':cmd,'output':'x','ok':True,'error':None,'returncode':0,'stderr':''})
  s = pf.status(); print(s); type(s["interfaces"])  # 'boom', <class 'str'>
  ```
  Salida observada. `tests/test_pfsense.py::test_status_aisla_errores_y_los_acumula` sólo verifica `ok=False` + `errors`.

### 10. `render_config()` no preserva declaración XML, comentarios ni `tail`; contradice «no borra secciones que no entiende»
- **Fichero:línea:** `pfsense.py:24-45`, `pfsense.py:60-91`; `docs/PFSENSE-NATIVO.md:105-106`.
- **Qué pasa:** `ET.fromstring` descarta comentarios y `<?xml ...?>`; `_element_to_value` sólo guarda `@attributes`, `#text` (`element.text`) y hijos; no `element.tail`. `render_config` `ET.tostring(root, encoding="unicode", short_empty_elements=True)` no emite `<?xml ...?>`. Una sección desconocida `<unknown>before<y/>after</unknown>` se parsea `{'#text':'before','y':''}` y se renderiza `<unknown>before<y /></unknown>`. 
- **Impacto concreto:** `put_config(render_config(...))` / `gns3lab pf config put` reescribe `/conf/config.xml` sin comentarios ni declaración, y pierde texto mixto. Las **secciones desconocidas element-only** se preservan y `test_parse_render_idempotentes...` lo verifica; la doc dice «no borra secciones del XML que no entiende», no «comentarios», pero `render_config` sí pierde `<!-- -->`. pfSense genera `<?xml version...?>`; **no verificado que pfSense falle sin declaración**; pérdida sí observada.
- **Reproducir/verificar:**
  ```python
  xml = '<?xml version="1.0"?>\n<pfsense><!--c--><system><hostname>fw</hostname></system><unknown>before<y/>after</unknown></pfsense>'
  out = pfsense.render_config(pfsense.parse_config(xml))
  print(out); print('<!--' in out, '<?xml' in out, 'after' in out)  # False False False
  ```

## Doc findings (`docs/PFSENSE-NATIVO.md`)
- `docs/PFSENSE-NATIVO.md:93` y `:104` dicen `rule()`/`nat()` «insertan antes de cualquier `reject`», pero `_insert_rule` inserta antes de `reject` **o `block`** (`pfsense.py:186-189`, `pfsense.py:180-191`). No es bug de runtime, sí doc inexacta. **Incluido como observación, no como hallazgo numerado**.
- `docs/PFSENSE-NATIVO.md:105-106` «no borra secciones del XML que no entiende» es cierto para secciones element-only, pero no para comentarios/declaración/`tail` (hallazgo 10).
- `docs/PFSENSE-NATIVO.md:55-65` lista `PFSENSE_HOST/PORT/USER/PASSWORD`; `PfSense.from_env` lee esos 4 y `PFSENSE_PORT or "22022"`. **`PFSENSE_TIMEOUT` no se lee** aunque `tests/test_pfsense.py` lo limpia en `limpia_entorno_pfsense`. `PfSense.timeout=20`. **Observación**.

## Verificación de reproducibilidad
- Todos los snippets usan `.venv/bin/python` en este worktree, `import pfsense`, `PfSense(password=os.environ["PFSENSE_PASSWORD"])`, `get_config=lambda: doc`, `put_config=lambda d, backup=True: {"ok": True}`. No se ha llamado a `PfSense.run` real, no se ha usado `sshpass`, no se ha contactado un pfSense.
- `pfsense.PfSense.run` real requiere `sshpass` + SSH y `PFSENSE_PASSWORD`; no disponible/no probado en esta sesión. Las afirmaciones sobre pfSense aplicando/leyendo `config.xml` se marcan explícitamente **no verificadas contra firewall vivo**.
- `python -m py_compile pfsense.py` no se ha ejecutado como gate separado; `pytest` y `scripts/verify.py` sí. No se han modificado ficheros del repo excepto este informe.

**Número de hallazgos: 10** (más 3 observaciones de documentación/variables no numeradas). No se han creado pruebas, no se ha modificado código de producción, no commit, no PR.
