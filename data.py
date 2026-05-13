import io
import json
import os
import re
import tempfile
import unicodedata

import duckdb
import geopandas as gpd
import pandas as pd
import requests
from glob import glob

# ── Tabular data (DuckDB) ─────────────────────────────────────────────────────
PARQUET_URL = (
    "https://raw.githubusercontent.com/FrancescoCorti/omi-data/main/omi_estimate.parquet"
)

_token = os.environ.get("GITHUB_TOKEN")
_headers = {"Authorization": f"token {_token}"} if _token else {}
_resp = requests.get(PARQUET_URL, headers=_headers)
_resp.raise_for_status()

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as _f:
    _f.write(_resp.content)
    _tmp_parquet = _f.name

_con = duckdb.connect()
_con.execute(f"CREATE VIEW omi AS SELECT * FROM read_parquet('{_tmp_parquet}')")


def q(sql, params=None):
    return _con.execute(sql, params or []).df()


def build_where(reg=None, prov=None, mun=None, zone=None, prop_type=None, condition=None):
    mapping = [
        ('"Reg. name"',  reg),
        ('"Prov. name"', prov),
        ('"Mun. name"',  mun),
        ('Zone',         zone),
        ('Type',         prop_type),
        ('Condition',    condition),
    ]
    clauses, params = [], []
    for col, val in mapping:
        if val and val != 'average':
            clauses.append(f"{col} = ?")
            params.append(val)
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


ALL_REGIONS    = q('SELECT DISTINCT "Reg. name" FROM omi ORDER BY "Reg. name"')["Reg. name"].tolist()
ALL_TYPES      = q("SELECT DISTINCT Type FROM omi ORDER BY Type")["Type"].tolist()
ALL_CONDITIONS = q("SELECT DISTINCT Condition FROM omi ORDER BY Condition")["Condition"].tolist()

# ── Geo data (remote, cached in memory) ───────────────────────────────────────
GEOJSON_DIR = "datasets/data_maps/geojson"
GEO_BASE_URL = "https://raw.githubusercontent.com/FrancescoCorti/omi-geodata/main"

_geo_cache: dict[str, gpd.GeoDataFrame] = {}
_zone_prov_index: dict[str, str] = {}   # province name → region name


def _safe_filename(name: str) -> str:
    """Mirror of prepare_data.safe_filename — must stay in sync with how files are named on GitHub."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s-]", "", name)
    return re.sub(r"[\s/]+", "_", name).strip("_")


def load_geo(path: str) -> gpd.GeoDataFrame:
    return gpd.read_file(path)


def _fetch_geo(url: str) -> gpd.GeoDataFrame:
    resp = requests.get(url, headers=_headers)
    resp.raise_for_status()
    return gpd.read_file(io.BytesIO(resp.content))


def _init_geo_cache() -> None:
    global _zone_prov_index
    gdf_reg = _fetch_geo(f"{GEO_BASE_URL}/reg_map.geojson")
    _geo_cache["region"] = gdf_reg

    gdf_prov = _fetch_geo(f"{GEO_BASE_URL}/prov_map.geojson")
    _geo_cache["province"] = gdf_prov

    if "Prov. name" in gdf_prov.columns and "Reg. name" in gdf_prov.columns:
        _zone_prov_index = (
            gdf_prov[["Prov. name", "Reg. name"]]
            .drop_duplicates("Prov. name")
            .set_index("Prov. name")["Reg. name"]
            .to_dict()
        )


def _load_mun(region: str) -> gpd.GeoDataFrame:
    key = f"mun:{region}"
    if key not in _geo_cache:
        fname = f"{_safe_filename(region)}.geojson"
        _geo_cache[key] = _fetch_geo(f"{GEO_BASE_URL}/mun_by_region/{fname}")
    return _geo_cache[key]


def _load_zone_province(province: str) -> gpd.GeoDataFrame:
    key = f"zprov:{province}"
    if key not in _geo_cache:
        fname = f"{_safe_filename(province)}.geojson"
        _geo_cache[key] = _fetch_geo(f"{GEO_BASE_URL}/zone_by_province/{fname}")
    return _geo_cache[key]


def get_geo(level: str, region: str | None = None) -> dict:
    """Return a GeoJSON FeatureCollection dict for the requested level/region."""
    if level == "region":
        gdf = _geo_cache.get("region")
    elif level == "province":
        gdf = _geo_cache.get("province")
    elif level == "municipality":
        if not region:
            return {"type": "FeatureCollection", "features": []}
        gdf = _load_mun(region)
    elif level == "zone":
        if not region:
            return {"type": "FeatureCollection", "features": []}
        provinces = [p for p, r in _zone_prov_index.items() if r == region]
        gdfs = [_load_zone_province(p) for p in provinces]
        if not gdfs:
            return {"type": "FeatureCollection", "features": []}
        gdf = gpd.GeoDataFrame(
            pd.concat(gdfs, ignore_index=True),
            geometry="geometry",
            crs=gdfs[0].crs,
        )
    else:
        return {"type": "FeatureCollection", "features": []}

    if gdf is None or gdf.empty:
        return {"type": "FeatureCollection", "features": []}
    return json.loads(gdf.to_json())


def _build_geo_indexes():
    gdf_reg = load_geo(f"{GEOJSON_DIR}/reg_map.geojson")
    gdf_reg["geometry"] = gdf_reg["geometry"].simplify(tolerance=0.001, preserve_topology=True)

    gdf_prov = load_geo(f"{GEOJSON_DIR}/prov_map.geojson")
    gdf_prov["geometry"] = gdf_prov["geometry"].simplify(tolerance=0.001, preserve_topology=True)

    mun_files: dict[str, str] = {}
    zone_files: dict[str, str] = {}
    prov_to_reg: dict[str, str] = {}

    for _f in sorted(glob(f"{GEOJSON_DIR}/mun_by_region/*.geojson")):
        _gdf = gpd.read_file(_f, rows=1)
        if "Reg. name" in _gdf.columns and not _gdf.empty:
            mun_files[_gdf["Reg. name"].iloc[0]] = _f

    for _f in sorted(glob(f"{GEOJSON_DIR}/zone_by_province/*.geojson")):
        _gdf = gpd.read_file(_f, rows=1)
        if "Prov. name" in _gdf.columns and not _gdf.empty:
            _prov = _gdf["Prov. name"].iloc[0]
            zone_files[_prov] = _f
            if "Reg. name" in _gdf.columns:
                prov_to_reg[_prov] = _gdf["Reg. name"].iloc[0]

    return gdf_reg, gdf_prov, mun_files, zone_files, prov_to_reg
