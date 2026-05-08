from dash import Dash
import dash_bootstrap_components as dbc

from pages.map import layout 

app = Dash(__name__, external_stylesheets=[dbc.themes.COSMO, dbc.icons.FONT_AWESOME])
app.layout = layout

if __name__ == "__main__":
    app.run(debug=True, dev_tools_hot_reload=True)