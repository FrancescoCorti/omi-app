from dotenv import load_dotenv
load_dotenv("token.env")

from pathlib import Path
import dash
from dash import Dash, html
import dash_bootstrap_components as dbc

app = Dash(__name__, use_pages=True, external_stylesheets=[dbc.themes.COSMO, dbc.icons.FONT_AWESOME])

_logo_file = Path(__file__).parent / "assets" / "logo.svg"
_logo_slot = (
    html.Img(src="/assets/logo.svg", style={"height": "48px"})
    if _logo_file.exists()
    else html.Div("Estate Insights", style={
        "fontWeight": "700",
        "fontSize": "1.25rem",
        "color": "#fff",
        "letterSpacing": "0.03em",
    })
)

sidebar = html.Div([
    html.Div(_logo_slot, id="sidebar-logo"),
    html.Div("Estate Insights", id="sidebar-title"),
    html.Hr(),
    dbc.Nav([
        dbc.NavLink("Chart", href="/",     active="exact"),
        dbc.NavLink("Info",  href="/info", active="exact"),
    ], vertical=True, pills=True),
], id="sidebar")

content = html.Div(dash.page_container, id="page-content")

app.layout = html.Div([sidebar, content], id="app-shell")
server = app.server

if __name__ == "__main__":
    app.run(debug=True, dev_tools_hot_reload=True)
