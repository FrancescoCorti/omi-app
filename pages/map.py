import folium
import pandas as pd
from dash import Dash, dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc

from data import load_geo, _build_geo_indexes

gdf_reg, gdf_prov, MUN_FILES, ZONE_FILES, PROV_TO_REG = _build_geo_indexes()

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_ZONE_PROVINCES = 3

_LEGEND_CSS = """
<style>
  .legend { color: white !important; background-color: rgba(0,0,0,0.7) !important; }
  .legend text { fill: white !important; }
</style>
"""

_PLACEHOLDER_MAP = """
<div style="display:flex;align-items:center;justify-content:center;
            height:100%;background:#111827;color:#9ca3af;font-family:sans-serif;font-size:14px;">
  <div style="text-align:center">
    <div style="font-size:2rem;margin-bottom:.5rem">{icon}</div>
    <div>{msg}</div>
  </div>
</div>
"""

_CANDIDATE_METRICS = ["Max. price", "Min. price"]
MAP_METRICS = [c for c in _CANDIDATE_METRICS if c in gdf_reg.columns] or ["Max. price"]

MAP_METRIC_LABELS = {
    "Max. price":  "Max. price (€/m²)",
    "Min. price":  "Min. price (€/m²)"
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def render_map(gdf, column="Max. price") -> str:
    if gdf.empty or column not in gdf.columns:
        return _PLACEHOLDER_MAP.format(icon="🗺️", msg="No data for this selection")
    m = gdf.explore(
        tiles="CartoDB.DarkMatter",
        column=column,
        style_kwds=dict(fillOpacity=0.3, weight=0.5),
        highlight_kwds=dict(fillOpacity=0.3, weight=1, color="white"),
    )
    m.get_root().html.add_child(folium.Element(_LEGEND_CSS))
    return m.get_root().render()


def opts(values, placeholder=None) -> list[dict]:
    clean = sorted({v for v in values if pd.notna(v)}, key=str)
    result = [{"label": str(v), "value": v} for v in clean]
    if placeholder:
        result = [{"label": placeholder, "value": "__all__"}] + result
    return result


# ── Layout ────────────────────────────────────────────────────────────────────
layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.P(
                    "Source: OMI — Osservatorio del Mercato Immobiliare",
                    className="text-secondary small mb-0 py-2",
                )
            )
        ),

        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Geographic Scope", className="small text-white fw-semibold mb-2"),
                        dbc.RadioItems(
                            id="m-scope",
                            options=[
                                {"label": " 🗺 Regions",       "value": "region"},
                                {"label": " 🏙 Provinces",     "value": "province"},
                                {"label": " 🏘 Municipalities", "value": "municipality"},
                                {"label": " 📍 Zones",         "value": "zone"},
                            ],
                            value="region",
                            className="mb-3",
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        html.Label("Region", className="small text-white fw-semibold mb-2"),
                        dcc.Dropdown(id="m-region", value="__all__", clearable=False, className="dbc"),
                    ],
                    md=2, id="m-region-col", style={"display": "none"},
                ),
                dbc.Col(
                    [
                        html.Label("Province", className="small text-white fw-semibold mb-2"),
                        dcc.Dropdown(id="m-province", value=[], multi=True, clearable=False, className="dbc"),
                        html.Small(id="m-province-warning", className="text-warning d-block"),
                    ],
                    md=2, id="m-province-col", style={"display": "none"},
                ),
                dbc.Col(
                    [
                        html.Label("Municipality", className="small text-white fw-semibold mb-2"),
                        dcc.Dropdown(id="m-mun", value="__all__", clearable=True, className="dbc"),
                    ],
                    md=2, id="m-mun-col", style={"display": "none"},
                ),
                dbc.Col(
                    [
                        html.Label("Metric", className="small text-white fw-semibold mb-2"),
                        dcc.Dropdown(
                            id="m-metric",
                            options=[{"label": MAP_METRIC_LABELS.get(c, c), "value": c} for c in MAP_METRICS],
                            value=MAP_METRICS[0],
                            clearable=False,
                            className="dbc",
                        ),
                    ],
                    md=2,
                ),
            ],
            className="mb-4 g-2",
        ),

        dbc.Row(
            dbc.Col(
                dcc.Loading(
                    html.Iframe(
                        id="m-frame",
                        srcDoc=_PLACEHOLDER_MAP.format(icon="⏳", msg="Loading map…"),
                        style={"width": "100%", "height": "700px", "border": "none"},
                    ),
                    type="circle",
                    color="#375a7f",
                ),
                className="bg-dark border rounded p-0",
            )
        ),
    ],
    fluid=True,
    className="px-4",
    style={"backgroundColor": "#111827", "minHeight": "100vh", "paddingBottom": "2rem"},
)


# ── Callbacks ─────────────────────────────────────────────────────────────────
@callback(
    Output("m-region-col",   "style"),
    Output("m-province-col", "style"),
    Output("m-mun-col",      "style"),
    Input("m-scope", "value"),
)
def toggle_filters(scope):
    show, hide = {"display": "block"}, {"display": "none"}
    return (
        show if scope in ("municipality", "zone") else hide,
        show if scope == "zone" else hide,
        show if scope == "zone" else hide,
    )


@callback(
    Output("m-region", "options"),
    Output("m-region", "value"),
    Input("m-scope", "value"),
)
def update_region_options(scope):
    placeholder = "All regions (filter)" if scope == "zone" else "Select a region"
    return opts(list(MUN_FILES.keys()), placeholder), "__all__"


@callback(
    Output("m-province", "options"),
    Output("m-province", "value"),
    Input("m-scope", "value"),
    Input("m-region", "value"),
)
def update_province_options(scope, region):
    if region and region != "__all__":
        provs = [p for p, r in PROV_TO_REG.items() if r == region]
    else:
        provs = list(ZONE_FILES.keys())
    return opts(provs), []


@callback(
    Output("m-province-warning", "children"),
    Input("m-province", "value"),
)
def warn_too_many_provinces(provs):
    if provs and len(provs) > MAX_ZONE_PROVINCES:
        return f"⚠ Max {MAX_ZONE_PROVINCES} provinces — showing first {MAX_ZONE_PROVINCES}"
    return ""


@callback(
    Output("m-mun", "options"),
    Input("m-province", "value"),
)
def update_municipality_options(provs):
    if not provs:
        return []
    gdfs = [load_geo(ZONE_FILES[p]) for p in provs[:MAX_ZONE_PROVINCES] if p in ZONE_FILES]
    if not gdfs:
        return []
    gdf = pd.concat(gdfs, ignore_index=True)
    return opts(gdf["mun_name"].dropna().unique(), "All municipalities")


@callback(
    Output("m-frame", "srcDoc"),
    Input("m-scope",    "value"),
    Input("m-region",   "value"),
    Input("m-province", "value"),
    Input("m-mun",      "value"),
    Input("m-metric",   "value"),
)
def update_map(scope, region, provinces, mun, metric):
    if scope == "region":
        return render_map(gdf_reg, metric)

    if scope == "province":
        return render_map(gdf_prov, metric)

    if scope == "municipality":
        if not region or region == "__all__":
            return _PLACEHOLDER_MAP.format(icon="👆", msg="Select a region to view municipalities")
        filepath = MUN_FILES.get(region)
        if not filepath:
            return _PLACEHOLDER_MAP.format(icon="🗺️", msg="No data for this region")
        gdf = load_geo(filepath)
        gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.0005, preserve_topology=True)
        return render_map(gdf, metric)

    # zone
    selected_provs = (provinces or [])[:MAX_ZONE_PROVINCES]
    if not selected_provs:
        if region and region != "__all__":
            reg_provs = [p for p, r in PROV_TO_REG.items() if r == region]
            gdfs = [load_geo(ZONE_FILES[p]) for p in reg_provs if p in ZONE_FILES]
            if not gdfs:
                return _PLACEHOLDER_MAP.format(icon="🗺️", msg="No zone data for this region")
            return render_map(pd.concat(gdfs, ignore_index=True), metric)
        return _PLACEHOLDER_MAP.format(icon="👆", msg="Select a region or provinces to view zones")

    gdfs = [load_geo(ZONE_FILES[p]) for p in selected_provs if p in ZONE_FILES]
    if not gdfs:
        return _PLACEHOLDER_MAP.format(icon="🗺️", msg="No data for selected provinces")
    gdf = pd.concat(gdfs, ignore_index=True)
    if mun and mun != "__all__":
        gdf = gdf[gdf["mun_name"] == mun]
    return render_map(gdf, metric)
