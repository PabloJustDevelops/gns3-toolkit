# BRIEF — carril `fix-pf` (swarm de fixes)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-fix-pf` · rama `opencode/fix-pf`.
Base: `master` en `50669b4`. Modelo asignado: **HungerG Free**.

## Alcance

Solo puedes modificar: pfsense.py, scripts/labspec.py y tests de pfSense/labspec. No toques ningún otro archivo; otros carriles trabajan en paralelo.
Lee `AGENTS.md` antes de empezar. Los números vienen de `orchestration/INFORME-SWARM-2.md`.

## Hallazgos a arreglar (en orden)

1. ALTA pfsense.py:263 — run() redacta la contraseña en stdout antes de que get_config() lo parsee; una coincidencia puede romper el XML o alterar un valor guardado. Redactar solo en la salida presentada al usuario, nunca en el XML que se parsea.
2. ALTA pfsense.py:418-444 — assign() solo detecta duplicados dentro del mapping recibido; conserva roles omitidos que ya usan la misma interfaz. Comprobar también los roles existentes del config.xml.
3. ALTA pfsense.py:194-199,529-537 — rule() decide entre address/network por la presencia de '/' y no valida IPv4 ni CIDR. Validar con ipaddress; devolver error con el valor rechazado.
4. MEDIA pfsense.py:476-502 — dhcp() no comprueba que el rango esté dentro de la red de la interfaz.
5. MEDIA pfsense.py:514-533 — rule() no valida proto cuando no hay puerto.
6. MEDIA pfsense.py:24-29,534-537 — rule() falla si <filter/> está vacío porque lo convierte en cadena.
7. MEDIA pfsense.py:564-568 — nat() en modo automático inserta rule sin target; revisar con prueba de ida y vuelta.
8. MEDIA pfsense.py:142-155,466-467 — <subnet> se guarda con máscara punteada; normalizar a CIDR.
9. MEDIA pfsense.py:453-454,468-469 — <gateway> guarda IPv4 cruda; revisar si debe ser nombre de gateway y ajustar con evidencia.
10. MEDIA pfsense.py:94-102 + scripts/labspec.py:532-548 — detect_ifnames() devuelve solo WAN/LAN y lab verify exige data.adapter_type. Añadir el campo sin tocar cli/gns3lab.

## Contrato

1. Cada hallazgo lleva su **test que falla sin el arreglo** y pasa con él. No quites tests existentes.
2. Mantén la cobertura del 100 % en `gns3core.py` y `pfsense.py` si tocas esos ficheros (gate del CI).
3. No añadas secretos ni credenciales literales; usa variables de entorno.
4. Verifica con los gates reales: suite completa (`env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q`), `python3 scripts/verify.py` y `python3 scripts/check-links.py`.
5. Si un hallazgo requiere tocar un archivo fuera de tu alcance, **no lo hagas**: reporta el bloqueo y sigue con los demás.

## Entrega

Commit en `opencode/fix-pf`, `git push -u origin opencode/fix-pf` y `gh pr create --base master`
(título con `fix:` y cuerpo enumerando los hallazgos numerados). No mergees. Reporta URL del PR,
tests ejecutados y cualquier hallazgo que no hayas podido arreglar.
