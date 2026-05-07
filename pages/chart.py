import plotly.graph_objects as go
from dash import dcc, html, Input, Output, callback

from data import q, build_where, ALL_REGIONS, ALL_TYPES

# ── Helpers ───────────────────────────────────────────────────────────────────
def make_options(values, all_label):
    return [{"label": all_label, "value": "average"}] + \
           [{"label": str(v), "value": v} for v in values]


# ── Layout ────────────────────────────────────────────────────────────────────
layout = html.Div([
    html.Div([
        html.Div([
            html.Label("Region"),
            dcc.Dropdown(
                id="c-region",
                options=make_options(ALL_REGIONS, "Average (all regions)"),
                value="average", clearable=False,
            ),
        ], style={"width": "24%"}),
        html.Div([
            html.Label("Province"),
            dcc.Dropdown(id="c-province", value="average", clearable=False),
        ], style={"width": "24%"}),
        html.Div([
            html.Label("Municipality"),
            dcc.Dropdown(id="c-mun", value="average", clearable=False),
        ], style={"width": "24%"}),
        html.Div([
            html.Label("Zone"),
            dcc.Dropdown(id="c-zone", value="average", clearable=False),
        ], style={"width": "24%"}),
    ], style={"display": "flex", "gap": "12px", "marginBottom": "12px"}),

    html.Div([
        html.Div([
            html.Label("Property type"),
            dcc.Dropdown(
                id="c-type",
                options=[{"label": t, "value": t} for t in ALL_TYPES],
                value="Residential housing", clearable=False,
            ),
        ], style={"width": "24%"}),
        html.Div([
            html.Label("Condition"),
            dcc.Dropdown(id="c-condition", value="average", clearable=False),
        ], style={"width": "24%"}),
    ], style={"display": "flex", "gap": "12px", "marginBottom": "24px"}),

    dcc.Graph(id="c-chart"),
], style={"padding": "24px", "fontFamily": "sans-serif"})


# ── Cascade callbacks ─────────────────────────────────────────────────────────
@callback(
    Output("c-province", "options"),
    Output("c-province", "value"),
    Output("c-province", "disabled"),
    Input("c-region", "value"),
)
def update_province(reg):
    w, p = build_where(reg=reg)
    vals = q(f'SELECT DISTINCT "Prov. name" FROM omi {w} ORDER BY "Prov. name"', p)["Prov. name"].tolist()
    return make_options(vals, "Average (all provinces)"), "average", (reg == "average")


@callback(
    Output("c-mun", "options"),
    Output("c-mun", "value"),
    Output("c-mun", "disabled"),
    Input("c-region", "value"),
    Input("c-province", "value"),
)
def update_mun(reg, prov):
    w, p = build_where(reg=reg, prov=prov)
    vals = q(f'SELECT DISTINCT "Mun. name" FROM omi {w} ORDER BY "Mun. name"', p)["Mun. name"].tolist()
    return make_options(vals, "Average (all municipalities)"), "average", (prov == "average")


@callback(
    Output("c-zone", "options"),
    Output("c-zone", "value"),
    Output("c-zone", "disabled"),
    Input("c-region", "value"),
    Input("c-province", "value"),
    Input("c-mun", "value"),
)
def update_zone(reg, prov, mun):
    w, p = build_where(reg=reg, prov=prov, mun=mun)
    vals = q(f"SELECT DISTINCT Zone FROM omi {w} ORDER BY Zone", p)["Zone"].tolist()
    return make_options(vals, "Average (all zones)"), "average", (mun == "average")


@callback(
    Output("c-condition", "options"),
    Output("c-condition", "value"),
    Input("c-region", "value"),
    Input("c-province", "value"),
    Input("c-mun", "value"),
    Input("c-zone", "value"),
)
def update_condition(reg, prov, mun, zone):
    w, p = build_where(reg=reg, prov=prov, mun=mun, zone=zone)
    vals = q(f"SELECT DISTINCT Condition FROM omi {w} ORDER BY Condition", p)["Condition"].tolist()
    return make_options(vals, "Average (all conditions)"), "average"


# ── Chart callback ────────────────────────────────────────────────────────────
@callback(
    Output("c-chart", "figure"),
    Input("c-region",    "value"),
    Input("c-province",  "value"),
    Input("c-mun",       "value"),
    Input("c-zone",      "value"),
    Input("c-type",      "value"),
    Input("c-condition", "value"),
)
def update_chart(reg, prov, mun, zone, prop_type, condition):
    w, p = build_where(reg=reg, prov=prov, mun=mun, zone=zone, prop_type=prop_type, condition=condition)
    plot_df = q(f"""
        SELECT Year_Semester,
               AVG("Min. price") AS "Min. price",
               AVG("Max. price") AS "Max. price"
        FROM omi {w}
        GROUP BY Year_Semester
        ORDER BY Year_Semester
    """, p)

    if plot_df.empty:
        return go.Figure().add_annotation(
            text="No data for current selection", showarrow=False, font_size=16
        )

    plot_df["Mean price"] = (plot_df["Max. price"] + plot_df["Min. price"]) / 2
    x = plot_df["Year_Semester"].str.replace("_", " - ")

    territory = mun if mun != "average" else prov if prov != "average" else \
                reg if reg != "average" else "All regions (avg)"
    zone_label = f"Zone: {zone}" if zone != "average" else "All zones (avg)"
    cond_label = condition.capitalize() if condition != "average" else "All conditions (avg)"
    subtitle = f"{prop_type} · {territory} · {zone_label} · {cond_label}"

    fig = go.Figure([
        go.Scatter(x=x, y=plot_df["Max. price"], mode="lines", name="Max. price",
                   line=dict(color="tomato", width=2),
                   hovertemplate="Max: %{y:,.0f}<extra></extra>"),
        go.Scatter(x=x, y=plot_df["Mean price"], mode="lines", name="Mean price",
                   line=dict(color="gray", width=2, dash="dash"),
                   hovertemplate="Mean: %{y:,.0f}<extra></extra>"),
        go.Scatter(x=x, y=plot_df["Min. price"], mode="lines", name="Min. price",
                   line=dict(color="steelblue", width=2),
                   hovertemplate="Min: %{y:,.0f}<extra></extra>"),
    ])
    fig.update_layout(
        title=dict(text=f"Buy Price Trends<br><sup>{subtitle}</sup>"),
        xaxis=dict(title="Year - Semester", tickangle=-45,
                   showspikes=True, spikemode="across", spikesnap="cursor",
                   spikecolor="grey", spikethickness=1, spikedash="dash"),
        yaxis=dict(title="Price (€/m²)"),
        hovermode="x unified", hoverdistance=50, spikedistance=50,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly", height=500,
    )
    return fig
