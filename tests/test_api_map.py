"""`API_V2_MAP`: las once áreas que el núcleo dice cubrir."""
from gns3core import API_V2_MAP

AREAS = {"server", "computes", "projects", "templates", "nodes",
         "links", "drawings", "snapshots", "symbols", "gui_admin", "emulators"}


def test_api_v2_map_declara_las_once_areas():
    assert set(API_V2_MAP) == AREAS
    assert len(API_V2_MAP) == 11


def test_api_v2_map_no_tiene_areas_vacias():
    for area, rutas in API_V2_MAP.items():
        assert isinstance(rutas, tuple), f"{area} no es tupla"
        assert rutas, f"{area} está vacía"
        assert all(isinstance(r, str) and r.startswith(("GET", "POST", "PUT", "DELETE"))
                   for r in rutas), f"{area} tiene una ruta sin método: {rutas}"
