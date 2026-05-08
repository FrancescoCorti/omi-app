from dotenv import load_dotenv
load_dotenv("token.env")

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from data import q, build_where, ALL_REGIONS, ALL_TYPES, ALL_CONDITIONS

BASE_DIR = Path(__file__).parent
LOGO_FILE = BASE_DIR / "assets" / "logo.svg"

app = FastAPI()
app.mount("/assets", StaticFiles(directory=BASE_DIR / "assets"), name="assets")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def _base_ctx(request: Request, active: str) -> dict:
    return {
        "request": request,
        "active": active,
        "logo_exists": LOGO_FILE.exists(),
    }


def _norm(v: str | None) -> str | None:
    """Empty string from a select means 'no filter at this level' — same role as Dash's 'average' sentinel."""
    if v is None or v == "":
        return None
    return v


# ── Pages ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def page_chart(request: Request):
    ctx = _base_ctx(request, active="chart")
    ctx.update({
        "regions": ALL_REGIONS,
        "types": ALL_TYPES,
        "conditions": ALL_CONDITIONS,
        "default_type": "Residential housing" if "Residential housing" in ALL_TYPES else (ALL_TYPES[0] if ALL_TYPES else ""),
    })
    return templates.TemplateResponse("chart.html", ctx)


@app.get("/info", response_class=HTMLResponse)
def page_info(request: Request):
    return templates.TemplateResponse("info.html", _base_ctx(request, active="info"))


# ── Chart data ────────────────────────────────────────────────────────────────
@app.get("/api/chart")
def api_chart(
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
        return JSONResponse({"x": [], "min": [], "mean": [], "max": [], "subtitle": subtitle, "empty": True})

    x = df["Year_Semester"].str.replace("_", " - ").tolist()
    mn = df["min_price"].round(2).tolist()
    mx = df["max_price"].round(2).tolist()
    mean = [round((a + b) / 2, 2) for a, b in zip(mn, mx)]

    return JSONResponse({"x": x, "min": mn, "mean": mean, "max": mx, "subtitle": subtitle, "empty": False})


def _build_subtitle(reg, prov, mun, zn, pt, cond) -> str:
    territory = mun or prov or reg or "All regions (avg)"
    zone_label = f"Zone: {zn}" if zn else "All zones (avg)"
    cond_label = cond.capitalize() if cond else "All conditions (avg)"
    type_label = pt or "All types"
    return f"{type_label} · {territory} · {zone_label} · {cond_label}"


# ── Cascade dropdowns (HTMX partials) ─────────────────────────────────────────
@app.get("/partials/province", response_class=HTMLResponse)
def partial_province(request: Request, region: str | None = None):
    reg = _norm(region)
    if reg is None:
        values = []
    else:
        w, p = build_where(reg=reg)
        values = q(f'SELECT DISTINCT "Prov. name" FROM omi {w} ORDER BY "Prov. name"', p)["Prov. name"].tolist()
    return templates.TemplateResponse("partials/province.html", {
        "request": request,
        "values": values,
        "disabled": reg is None,
        "cascade": True,
    })


@app.get("/partials/municipality", response_class=HTMLResponse)
def partial_municipality(request: Request, region: str | None = None, province: str | None = None):
    reg, prov = _norm(region), _norm(province)
    if prov is None:
        values = []
    else:
        w, p = build_where(reg=reg, prov=prov)
        values = q(f'SELECT DISTINCT "Mun. name" FROM omi {w} ORDER BY "Mun. name"', p)["Mun. name"].tolist()
    return templates.TemplateResponse("partials/municipality.html", {
        "request": request,
        "values": values,
        "disabled": prov is None,
        "cascade": True,
    })


@app.get("/partials/zone", response_class=HTMLResponse)
def partial_zone(request: Request, region: str | None = None, province: str | None = None, municipality: str | None = None):
    reg, prov, mun = _norm(region), _norm(province), _norm(municipality)
    if mun is None:
        values = []
    else:
        w, p = build_where(reg=reg, prov=prov, mun=mun)
        values = q(f"SELECT DISTINCT Zone FROM omi {w} ORDER BY Zone", p)["Zone"].tolist()
    return templates.TemplateResponse("partials/zone.html", {
        "request": request,
        "values": values,
        "disabled": mun is None,
        "cascade": True,
    })


@app.get("/partials/condition", response_class=HTMLResponse)
def partial_condition(
    request: Request,
    region: str | None = None,
    province: str | None = None,
    municipality: str | None = None,
    zone: str | None = None,
):
    reg, prov, mun, zn = _norm(region), _norm(province), _norm(municipality), _norm(zone)
    w, p = build_where(reg=reg, prov=prov, mun=mun, zone=zn)
    values = q(f"SELECT DISTINCT Condition FROM omi {w} ORDER BY Condition", p)["Condition"].tolist()
    return templates.TemplateResponse("partials/condition.html", {
        "request": request,
        "values": values,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8050, reload=True)
