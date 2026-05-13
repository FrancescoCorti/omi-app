from dotenv import load_dotenv
load_dotenv("token.env")

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import data
from data import q, build_where, ALL_REGIONS, ALL_TYPES

BASE_DIR = Path(__file__).parent
LOGO_FILE = BASE_DIR / "assets" / "logo.svg"

app = FastAPI()
app.mount("/assets", StaticFiles(directory=BASE_DIR / "assets"), name="assets")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

try:
    data._init_geo_cache()
except Exception as _geo_exc:
    print(f"[geo] Map data unavailable: {_geo_exc}")


def _base_ctx(request: Request, active: str) -> dict:
    return {
        "request": request,
        "active": active,
        "logo_exists": LOGO_FILE.exists(),
    }


def _norm(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    return v


# ── Pages ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
@app.get("/home", response_class=HTMLResponse)
def page_home(request: Request):
    return templates.TemplateResponse("home.html", _base_ctx(request, active="home"))


@app.get("/chart", response_class=HTMLResponse)
def page_chart(request: Request):
    ctx = _base_ctx(request, active="chart")
    ctx.update({
        "regions": ALL_REGIONS,
        "types": ALL_TYPES,
        "default_type": "Residential housing" if "Residential housing" in ALL_TYPES else (ALL_TYPES[0] if ALL_TYPES else ""),
    })
    return templates.TemplateResponse("chart.html", ctx)


@app.get("/map", response_class=HTMLResponse)
def page_map(request: Request):
    ctx = _base_ctx(request, active="map")
    ctx["regions"] = ALL_REGIONS
    return templates.TemplateResponse("map.html", ctx)


@app.get("/info", response_class=HTMLResponse)
def page_info(request: Request):
    return templates.TemplateResponse("info.html", _base_ctx(request, active="info"))


# ── Single state endpoint: returns all dropdown options + chart in one shot ──
@app.get("/api/state")
def api_state(
    region: str | None = None,
    province: str | None = None,
    municipality: str | None = None,
    zone: str | None = None,
    type: str | None = None,
    condition: str | None = None,
):
    reg = _norm(region)
    prov = _norm(province)
    mun = _norm(municipality)
    zn = _norm(zone)
    pt = _norm(type)
    cond = _norm(condition)

    provinces: list[str] = []
    if reg is not None:
        w, p = build_where(reg=reg)
        provinces = q(f'SELECT DISTINCT "Prov. name" FROM omi {w} ORDER BY "Prov. name"', p)["Prov. name"].tolist()

    municipalities: list[str] = []
    if reg is not None and prov is not None:
        w, p = build_where(reg=reg, prov=prov)
        municipalities = q(f'SELECT DISTINCT "Mun. name" FROM omi {w} ORDER BY "Mun. name"', p)["Mun. name"].tolist()

    zones: list[str] = []
    if reg is not None and prov is not None and mun is not None:
        w, p = build_where(reg=reg, prov=prov, mun=mun)
        zones = q(f"SELECT DISTINCT Zone FROM omi {w} ORDER BY Zone", p)["Zone"].tolist()

    w, p = build_where(reg=reg, prov=prov, mun=mun, zone=zn)
    conditions = q(f"SELECT DISTINCT Condition FROM omi {w} ORDER BY Condition", p)["Condition"].tolist()

    w, params = build_where(reg=reg, prov=prov, mun=mun, zone=zn, prop_type=pt, condition=cond)
    df = q(
        f"""
        SELECT Year_Semester,
               AVG("Min. price") AS min_price,
               AVG("Max. price") AS max_price
        FROM omi {w}
        GROUP BY Year_Semester
        ORDER BY Year_Semester
        """,
        params,
    )

    subtitle = _build_subtitle(reg, prov, mun, zn, pt, cond)

    if df.empty:
        chart = {"x": [], "min": [], "mean": [], "max": [], "subtitle": subtitle, "empty": True}
    else:
        x = df["Year_Semester"].str.replace("_", " - ").tolist()
        mn = df["min_price"].round(2).tolist()
        mx = df["max_price"].round(2).tolist()
        mean = [round((a + b) / 2, 2) for a, b in zip(mn, mx)]
        chart = {"x": x, "min": mn, "mean": mean, "max": mx, "subtitle": subtitle, "empty": False}

    return JSONResponse({
        "options": {
            "provinces": provinces,
            "municipalities": municipalities,
            "zones": zones,
            "conditions": conditions,
        },
        "chart": chart,
    })


@app.get("/api/geo")
def api_geo(level: str = "region", region: str | None = None):
    reg = _norm(region)
    try:
        geojson = data.get_geo(level, reg)
    except Exception as exc:
        return JSONResponse({"type": "FeatureCollection", "features": [], "error": str(exc)})
    return JSONResponse(geojson)


def _build_subtitle(reg, prov, mun, zn, pt, cond) -> str:
    territory = mun or prov or reg or "All regions (avg)"
    zone_label = f"Zone: {zn}" if zn else "All zones (avg)"
    cond_label = cond.capitalize() if cond else "All conditions (avg)"
    type_label = pt or "All types"
    return f"{type_label} · {territory} · {zone_label} · {cond_label}"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8050, reload=True)
