import dash
from dash import html

dash.register_page(__name__, path="/info", name="Info")

layout = html.Div([
    html.H2("About this app"),
    html.P("Content coming soon."),
], style={"padding": "24px"})
