# BRIEF — carril `capdocs` (documentación de capturas por fase y WebUI)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-capdocs` · rama `opencode/capdocs`.

## Contexto

Los carriles `capcore`, `capweb` y `capmcp` están añadiendo capturas por fase desde HMP,
capturas de la WebUI con navegador headless y la tool `gns3_capturas`. Lee `AGENTS.md`,
`docs/EXAMEN.md`, `docs/PFSENSE-NATIVO.md`, `docs/LAB-SPEC.md`, `docs/INDEX.md`,
`docs/COMANDOS.md`, `skill-sync/README.md` y los tres briefs `BRIEF-cap*.md`.

## Qué entregar (solo docs; no toques la skill real)

1. **`docs/CAPTURAS-EXAMEN.md`**: guía del ciclo:
   - bloque `captures:` en el manifiesto (máximo 5 fases: topología, pfSense, reglas, NAT, verificación);
   - `gns3lab lab apply --captures` y `gns3lab examen capturas [--webui] [--out …]`;
   - HMP para consola, navegador headless solo para la WebUI y solo en modo lectura;
   - credenciales desde entorno, perfil efímero, degradación a consola si falla;
   - índice `indice.md` con fase/archivo/OCR; **no generar el documento final**.
   Salidas de ejemplo marcadas como ejemplo, nunca como salida medida.
2. Actualizar **`docs/EXAMEN.md`**, **`docs/LAB-SPEC.md`**, **`docs/INDEX.md`** y
   **`docs/COMANDOS.md`** con los comandos y la tool nuevos, sin borrar lo existente.
3. **`skill-sync/references/capturas-fases.md`**: versión corta para la skill, con la regla
   «VNC último recurso» y «la WebUI solo para evidencia, nunca para configurar». Añadirlo a
   `skill-sync/README.md`.

## Reglas

Verifica cada comando en `cli/gns3lab` y cada tool en `gns3_mcp_server.py`. Si algo está aún
en otro carril, márcalo como «previsto en capcore/capweb/capmcp», nunca como hecho. Enlaces
relativos válidos, español, sin cifras no medidas.

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-capdocs
python3 scripts/check-links.py
ls -l docs/CAPTURAS-EXAMEN.md skill-sync/references/capturas-fases.md
```

Commit en `opencode/capdocs`; **no push a master**, no PR.
