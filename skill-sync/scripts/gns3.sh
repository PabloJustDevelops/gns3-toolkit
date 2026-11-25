#!/usr/bin/env bash
# Envoltorio delgado: fija el PATH al repo y delega todo en gns3lab.
# Sin lógica propia, sin credenciales y sin rutas de otros usuarios.
set -euo pipefail

export PATH="$HOME/Proyectos/gns3-toolkit/cli:$PATH"
exec gns3lab "$@"
