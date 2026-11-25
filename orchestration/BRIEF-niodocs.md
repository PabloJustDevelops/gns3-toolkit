# BRIEF — carril `niodocs` (documentar NIO, eventos y límites controller/compute)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-niodocs` · rama `opencode/niodocs`.

## Contexto

El núcleo tiene 12 áreas. Los carriles `niocli` y `niomcp` están añadiendo, con el mismo
contrato, NIO/captura por puerto, acciones masivas, qemu img, VMs invitadas y eventos WS.
El informe de REA (`docs/research/ubridge-console-enganche.md`) concluyó que ubridge no sirve
Telnet/VNC/WebSocket y que la consola la sirve `gns3server`: por eso la vía de enganche es
la API del compute.

## Qué entregar

1. **`docs/NIO-Y-CAPTURAS.md`**: explica la diferencia entre captura de enlace
   (`/links/{id}/…`) y captura por puerto (`/computes/local/projects/…/ports/{p}/…`), con
   comando CLI, tool MCP y método del núcleo para cada una. Incluye el formato del body NIO y
   qué significa un `500` del compute (no lo disfraces). Sin inventar flags: verifica en el
   código de los otros carriles; si aún no existen, marca «en curso».
2. **`docs/EVENTOS.md`**: URL de `/v2/notifications/ws` y `/v2/projects/{id}/notifications/ws`,
   qué eventos se pueden esperar según los handlers de `gns3server`, y el comando/tool para
   suscribirse. Si el cliente no está implementado aún, di cómo se haría y el estado real.
3. **Actualiza `docs/API-COVERAGE.md`** de 11 a **12 áreas** (`nio_ports`) y
   **`docs/GUI-PORTADA.md`** con las operaciones nuevas. Actualiza `README.md` con los enlaces.
4. **`docs/LIMITES-CONTROLLER-COMPUTE.md`**: qué rutas son del controller y cuáles se
   reenvían al compute, por qué algunas devuelven 409 cuando VirtualBox/VMware no están
   instalados, y por qué `/v1/version` existe pero `/v2/controller` no.

## Reglas

Nada inventado; verifica cada nombre en el código. Enlaces relativos válidos. Español,
frases cortas, sin relleno.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/`, `AGENTS.md` ni
`PROJECT.md`. No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-niodocs
python3 - <<'EOF'
import pathlib, re
bad=[]
for md in pathlib.Path("docs").glob("*.md"):
    for link in re.findall(r"\]\((?!http)([^)#]+)", md.read_text()):
        if not (md.parent/link).exists() and not pathlib.Path(link).exists(): bad.append(f"{md}: {link}")
print("enlaces rotos:", bad or "ninguno")
EOF
grep -c '^|' docs/NIO-Y-CAPTURAS.md docs/API-COVERAGE.md docs/GUI-PORTADA.md
```

Commit: `docs: NIO/capturas por puerto, eventos WS y límites controller/compute`. Informa de gates.
