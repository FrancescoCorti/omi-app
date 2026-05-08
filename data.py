import os
import tempfile

import duckdb
import geopandas as gpd
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

# ── Geo data (loaded only when map page is active) ────────────────────────────
GEOJSON_DIR = "datasets/data_maps/geojson"



def load_geo(path: str) -> gpd.GeoDataFrame:
    return gpd.read_file(path)


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
