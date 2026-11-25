# BRIEF — carril `rea` (reverse engineering de ubridge para enganchar más GNS3)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-rea` · rama `opencode/rea`.

## Contexto

El servidor GNS3 es Python legible y ya está inventariado (78 rutas en
`orchestration/inventario-rutas-gns3.txt`). Lo que **no** es Python es `ubridge`: el
componente C que GNS3 usa para tender los cables virtuales de las consolas y los enlaces.
Está en `~/.local/bin/ubridge` (286 KB, ELF), y es la pieza que decidiría si podemos
enganchar consolas y NIOs sin depender de la GUI.

La skill del proyecto está en `~/.hermes/skills/software-development/rea-reverse-engineering/SKILL.md`
y la de router rápido en `~/.hermes/skills/software-development/leanrea/SKILL.md`. **Léelas
antes de ejecutar nada.** Pablo autorizó REA sobre este binario, que es software local suyo.

## Objetivo

Producir **`docs/research/ubridge-console-enganche.md`** con hallazgos verificables:

1. Identificación del binario: `file`, `sha256sum`, `nm -C -S --defined-only`, `readelf -h`,
   e `imports`/`strings` con `rztriage` (o `rizin`/`radare2` directo). Cita la salida real.
2. Qué protocolos y transportes implementa (UDP, TCP, Telnet, VNC, pcap, UNIX socket),
   qué funciones los manejan y con qué símbolos/estrings se reconocen. Extrae solo lo que
   la herramienta muestra; separa observación de inferencia.
3. Si hace falta pseudocódigo, usa `rztriage decomp <binario> <símbolo>` o REA CLI con
   `--snapshot` (Ghidra tarda ~135 s en importar y el análisis completo no aporta aquí).
   No lances el auto-análisis completo de Ghidra.
4. Propuesta concreta de enganche para este repo: qué operaciones de `ubridge` podrían
   exponerse como comando/tool sin tocar la GUI (por ejemplo NIO UDP, reset de consola,
   captura de puerto), con el endpoint de GNS3 correspondiente del inventario y qué
   método de `gns3core.py` ya lo cubre o habría que añadir. Di explícitamente lo que
   **no** se puede hacer sin parchear el binario.

## Prohibido

- No modifiques ni ejecutes `ubridge` con flags que abran/escuchen puertos ni Capturas de
  proceso (`capture_process_scenario`, `*_adb_*`): son cambios fuera de la sesión.
- No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/` ni `PROJECT.md`.
  Tu único fichero de entrega es `docs/research/ubridge-console-enganche.md`.
- No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-rea
sha256sum ~/.local/bin/ubridge
file ~/.local/bin/ubridge
rztriage info ~/.local/bin/ubridge 2>&1 | head -12
rztriage imports ~/.local/bin/ubridge 2>&1 | head -20
```

Commit: `docs(research): reverse engineering de ubridge y vías de enganche`. Informa de los
hallazgos con salida real y del nivel de confianza de cada conclusión.
