from dash import Dash
import dash_bootstrap_components as dbc

from pages.map import layout  # also registers all map callbacks + loads geo indexes

app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
app.layout = layout

if __name__ == "__main__":
    app.run(debug=True)
