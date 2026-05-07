from dotenv import load_dotenv                                                                                                               
load_dotenv("token.env")                                                                                                                     

from dash import Dash
import dash_bootstrap_components as dbc

from pages.chart import layout  # also registers all chart callbacks

app = Dash(__name__, external_stylesheets=[dbc.themes.COSMO, dbc.icons.FONT_AWESOME])
app.layout = layout
server = app.server

if __name__ == "__main__":
    app.run(debug=True, dev_tools_hot_reload=True)
