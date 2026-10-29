import gradio as gr #type:ignore
import requests #type:ignore
import pandas as pd #type:ignore
import plotly.graph_objects as go #type:ignore
import os
import json
import re


API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = os.environ.get("API_PORT", "9001")
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"

API_URL_TOP_PARTS = f"{API_BASE_URL}/api/warranty/top-parts"
API_URL_BIKE_MODEL = f"{API_BASE_URL}/api/warranty/top-parts/for-bike-model"
API_URL_FAILURE_RATIO = f"{API_BASE_URL}/api/warranty/failure-ratio/by-bike-model"
API_URL_PREDICTION_DETAILED = f"{API_BASE_URL}/api/warranty/predict/detailed"

# API_URL_TOP_PARTS = "http://0.0.0.0:9001/api/warranty/top-parts"
# API_URL_BIKE_MODEL = "http://0.0.0.0:9001/api/warranty/top-parts/for-bike-model"

# Bike model grouping config (used to aggregate similar models)
# NOTE: In Docker, cwd and layout can differ. We resolve the path from a set of common candidates.
def resolve_bike_model_groups_path() -> str:
    env_path = os.environ.get("BIKE_MODEL_GROUPS_PATH")
    here = os.path.dirname(__file__)
    cwd = os.getcwd()

    candidates = [
        env_path,
        # repo layout (gradio_panel/ at repo root, config at app/config/)
        os.path.join(here, "..", "app", "config", "bike_model_groups.json"),
        # container layout where WORKDIR is /app and config is /app/config/
        os.path.join(cwd, "config", "bike_model_groups.json"),
        os.path.join(cwd, "app", "config", "bike_model_groups.json"),
        "/app/config/bike_model_groups.json",
        "/app/app/config/bike_model_groups.json",
    ]

    for p in candidates:
        if not p:
            continue
        if os.path.exists(p):
            return os.path.abspath(p)

    # If nothing exists, return the first non-empty candidate (for clearer log messages)
    for p in candidates:
        if p:
            return os.path.abspath(p)
    return "bike_model_groups.json"


BIKE_MODEL_GROUPS_PATH = resolve_bike_model_groups_path()

# Historical data CSV (created on first /predict/detailed call)
ENHANCED_DATA_FILENAME = "df_monthly_enhanced_filled.csv"


def resolve_enhanced_data_path() -> str:
    # env_path = os.environ.get("ENHANCED_DATA_PATH")
    # here = os.path.dirname(__file__)
    # cwd = os.getcwd()
    #
    # candidates = [
    #     env_path,
    #     # repo layout (gradio_panel/ at repo root, cluster_data at app/cluster_data/)
    #     os.path.join(here, "..", "app", "cluster_data", ENHANCED_DATA_FILENAME),
    #     os.path.join(cwd, "app", "cluster_data", ENHANCED_DATA_FILENAME),
    #     os.path.join(cwd, "app", "app", "cluster_data", ENHANCED_DATA_FILENAME),
    #     os.path.join(cwd, "cluster_data", ENHANCED_DATA_FILENAME),
    #     "/app/cluster_data/df_monthly_enhanced_filled.csv",
    #     # "/app/app/cluster_data/df_monthly_enhanced_filled.csv",
    # ]
    #
    # for p in candidates:
    #     if not p:
    #         continue
    #     if os.path.exists(p):
    #         return os.path.abspath(p)
    #
    # for p in candidates:
    #     if p:
    #         return os.path.abspath(p)
    # return ENHANCED_DATA_FILENAME
    return os.path.join(".", "cluster_data", ENHANCED_DATA_FILENAME)


ENHANCED_DATA_PATH = resolve_enhanced_data_path()

# Fallback config: used if the JSON file isn't present inside the container.
# This is copied from app/config/bike_model_groups.json so the dropdown can still render keys.
BIKE_MODEL_GROUPS_FALLBACK = {
    "Aerox155": [
        "Aerox155 Grey Vermillion PGD",
        "Aerox155 Metallic Black SMX",
        "Aerox155 Racing Blue DPBMY",
        "Aerox155 Silver WMC",
    ],
    "Alpha": ["Alpha Marble Black"],
    "FAZER FI V 2.0": [
        "FAZER FI V 2.0 Marble White 2WS300BWC1",
        "FAZER FI V 2.0 Ravine Black 2WS200SMX",
    ],
    "FZ V3": ["FZ V3 Metric Black SMX", "FZ V3 Racing Blue DPBMY"],
    "FZ-X": [
        "FZ-X (BYJ1) Dark Matt Blue MFG",
        "FZ-X (BYJ1) Matt Black MFG",
        "FZ-X (BYJ1) Matt Copper MFG",
        "FZ-X (BYJ1) Matt Titan MFG",
        "FZ-X (Matt Copper)",
        "FZ-X (Metallic Blue)",
        "FZ-X Matt Black MBL2",
        "FZ-X Matt Copper MDOM3",
        "FZ-X Metallic Blue BMC",
    ],
    "FZ25": ["FZ25 (250CC)"],
    "FZN 250": ["FZN 250 (DF81) Black", "FZN 250 (DF81) Racing Blue", "FZN 250 (DF81) White"],
    "FZS DD": [
        "FZS DD Armada Blue CKD",
        "FZS DD Armada Blue MFG",
        "FZS DD Black Metallic MFG",
        "FZS DD Dark knight MFG",
        "FZS DD Dark Night CKD",
        "FZS DD Grey Metallic MFG",
        "FZS DD Matt Green CKD",
        "FZS DD Matt Grey Metallic MFG",
    ],
    "FZS FI V 2.0": [
        "FZS FI V 2.0 (SE) Matt Green 2GS300MBL2",
        "FZS FI V 2.0 (SE) Matt Green 2GS700MBL2",
        "FZS FI V 2.0 Hurricane Grey 2GS600MNM3",
        "FZS FI V 2.0 Knight Red 2GS600MDRM4",
        "FZS FI V 2.0 Lighting Cyan 2GS600CM6",
        "FZS FI V 2.0 Opal White 2GS600BWC1",
        "FZS FI V 2.0 Viper Black 2GS400SMX",
    ],
    "FZS V-2.0 DD": ["FZS V-2.0 DD Armada Blue MDPBM1"],
    "FZS V2": ["Fzs DD V2.0 Dark Knight", "Fzs DD V2.0 Matt Green", "FZS v2-Dark Night 2GS900010A MBL2"],
    "FZS V3": [
        "FZS V3 (BDY5) Dark Matt Blue",
        "FZS V3 (BDY5) Matt Red",
        "FZS V3 (BDY6) Majesty Red",
        "FZS V3 (BDY6) Metallic Black",
        "FZS V3 (BDY6) Metallic Grey",
        "FZS V3 Dark Matt Blue MDPBM1",
        "FZS V3 Gray & Cyan Blue MNM3",
        "FZS V3 Matt Black MBL2",
    ],
    "FZS V3.0": [
        "FZS V3.0 Dark Matt Blue CKD",
        "FZS V3.0 Dark Matt Blue MFG",
        "FZS V3.0 Dark Matt Blue MFG (MDPBM1)",
        "FZS V3.0 Grey & Cyan Blue CKD",
        "FZS V3.0 Matt Black CKD",
        "FZS V3.0 Matt Black MFG",
        "FZS V3.0 Matt Black MFG (MBL2)",
        "FZS V3.0 Matt Red MFG",
        "FZS V3.0 Metallic Red CKD",
        "FZS V3.0 Metallic Red MFG",
        "FZS V3.0 Vintage Green MFG",
        "FZS V3.0 White CKD",
    ],
    "FZS V4": [
        "FZS V4 (DE91) Dark Matt Blue",
        "FZS V4 (DE91) Matt Black",
        "FZS V4 (DE92) Ice Fluo Vermillion",
        "FZS V4 (DE92) Majesty Red",
        "FZS V4 (DE92) Matt Black",
        "FZS V4 (DE92) Metallic Grey",
        "FZS V4 (DE92) Racing Blue",
        "FZS V4 (DE92) Sparkle Green",
    ],
    "Fascino": ["Fascino Unite White"],
    "Fazer": ["Fazer Burning Red VRC1", "Fazer Midnight Black SMX"],
    "Fazer FZH150": ["Fazer FZH150 (DH21) Black", "Fazer FZH150 (DH21) Blue", "Fazer FZH150 (DH21) Red"],
    "MT 15": ["MT 15 ABS India Black SMX", "MT 15 ABS India Blue MDPBM1"],
    "MT15 V2": [
        "MT15 V2 Cyan Storm PGD",
        "MT15 V2 Ice Fluo Vermillion MLNM4",
        "MT15 V2 Metallic Black SMX",
        "MT15 V2 Racing Blue DPBMY",
    ],
    "N Max": ["N Max Scooter Grey MNM3"],
    "Other": ["FUEL PUMP COMP."],
    "R15 V3": ["R15 V3 Dark Knight MBL2", "R15 V3 MotoGP SMX", "R15 V3 Racing Blue DPBMY", "R15 V3 Thunder Grey MNM3"],
    "R15 V3.0": ["R15 V3.0 Black SMX", "R15 V3.0 Blue DPBMC", "R15 V3.0 Movistar DPBMC", "R15 V3.0 Yellow YM6"],
    "R15 V4": ["R15 V4 (BPDF00) Intensity White", "R15 V4 Dark Knight LGB", "R15 V4 Metallic Red VRC1", "R15 V4 Racing Blue DPBMY"],
    "R15M": ["R15M (BPDD00) Metallic Grey", "R15M (Metallic Grey BPDD00)", "R15M (Metallic Grey)", "R15M Metallic Grey WMC"],
    "Ray ZR": [
        "Ray ZR SR 125 FI Blue DPBMY",
        "Ray ZR SR 125 FI Green NHG",
        "Ray ZR SR Blue DPBMY",
        "Ray ZR Street Rally (Red) B2V1000-010A M",
    ],
    "RayZR Street Rally": ["RayZR Street Rally-DPBMY(Blue)", "RayZR Street Rally-MNM3(Red/Gray)"],
    "SALUTO Disc": [
        "SALUTO (Disc) Glory Green 2LP800YB",
        "SALUTO (Disc) Matt Green 2LPB00MBL2",
        "SALUTO (Disc) Smoky Black 2LP800MNM3",
        "SALUTO (Disc) Sparky Cyan 2LP800CM6",
        "Saluto Disc AB MFG",
        "Saluto Disc MG CKD",
        "Saluto Disc MG MFG",
        "Saluto Disc SC CKD",
        "Saluto Disc SC MFG",
    ],
    "SALUTO Drum": ["SALUTO (Drum) Victory Red 2LP400DRMK", "SALUTO (Drum) Victory Red 2LP500DRMK"],
    "SZRR": ["SZRR (SE) Matt Green 2PY500MBL2", "SZRR Beast Black 2PY400SMX", "SZRR Predator Cyan 2PY400CM6"],
    "Saluto": [
        "Saluto UBS Armada Blue MFG",
        "Saluto UBS Dark Purplish Blue MFG",
        "Saluto UBS Matt Black MFG",
        "Saluto UBS Pastel Dark Grey MFG",
        "Saluto UBS Sparkle Green MFG",
    ],
    "XSR155": ["XSR155 (Matt Black)", "XSR155 (Matt Green Metallic)", "XSR155 (Radical White)", "XSR155 (White Metallic)"],
}

BIKE_MODEL_GROUPS = {}
BIKE_MODEL_GROUP_LOOKUP = {}
BIKE_MODEL_GROUP_KEYS = []
# Simple list of bike model names (top-level JSON keys) for the dropdown
BIKE_MODEL_KEY_CHOICES = []


def normalize_bike_name(value: object) -> str:
    """Normalize bike names for matching (trim + collapse whitespace + remove NBSP)."""
    if value is None:
        return ""
    s = str(value).replace("\u00a0", " ").strip()
    # Collapse repeated whitespace to single spaces
    return " ".join(s.split())


def load_bike_model_key_choices():
    """Load dropdown bike model keys from the JSON config (top-level keys)."""
    global BIKE_MODEL_KEY_CHOICES
    try:
        with open(BIKE_MODEL_GROUPS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            print(f"⚠️ bike_model_groups.json is not a JSON object: {BIKE_MODEL_GROUPS_PATH}")
            data = BIKE_MODEL_GROUPS_FALLBACK

        keys = [str(k).strip() for k in data.keys()]
        keys = [k for k in keys if k]
        keys = sorted(keys, key=lambda s: s.lower())
        BIKE_MODEL_KEY_CHOICES = keys

        # Debug print so you can verify keys are present in runtime logs
        preview = ", ".join(keys[:25])
        more = "" if len(keys) <= 25 else f" ... (+{len(keys) - 25} more)"
        print(f"✅ Loaded {len(keys)} bike model keys from {BIKE_MODEL_GROUPS_PATH}: {preview}{more}")
        return BIKE_MODEL_KEY_CHOICES
    except FileNotFoundError:
        # Docker/mount issue: fallback so UI still works.
        keys = sorted(BIKE_MODEL_GROUPS_FALLBACK.keys(), key=lambda s: str(s).lower())
        BIKE_MODEL_KEY_CHOICES = keys
        preview = ", ".join(keys[:25])
        more = "" if len(keys) <= 25 else f" ... (+{len(keys) - 25} more)"
        print(
            f"⚠️ Bike model groups file not found: {BIKE_MODEL_GROUPS_PATH}. "
            f"Using fallback keys ({len(keys)}): {preview}{more}"
        )
        return BIKE_MODEL_KEY_CHOICES
    except Exception as e:
        print(f"⚠️ Failed to load bike model keys: {e} (path: {BIKE_MODEL_GROUPS_PATH})")

    BIKE_MODEL_KEY_CHOICES = []
    return BIKE_MODEL_KEY_CHOICES


def load_bike_model_groups():
    """Load bike model groups and build a reverse lookup."""
    global BIKE_MODEL_GROUPS, BIKE_MODEL_GROUP_LOOKUP, BIKE_MODEL_GROUP_KEYS
    groups = {}
    lookup = {}
    try:
        with open(BIKE_MODEL_GROUPS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            data = BIKE_MODEL_GROUPS_FALLBACK

        for group_key, model_list in data.items():
            key = normalize_bike_name(group_key)
            if not key:
                continue
            lookup[key] = key
            lookup[normalize_bike_name(key)] = key
            cleaned_models = []
            if isinstance(model_list, list):
                for model_name in model_list:
                    model = normalize_bike_name(model_name)
                    if not model:
                        continue
                    cleaned_models.append(model)
                    lookup[model] = key
                    lookup[normalize_bike_name(model)] = key
            groups[key] = cleaned_models
    except FileNotFoundError:
        print(f"⚠️ Bike model groups file not found: {BIKE_MODEL_GROUPS_PATH} (using fallback groups)")
        data = BIKE_MODEL_GROUPS_FALLBACK
        for group_key, model_list in data.items():
            key = normalize_bike_name(group_key)
            if not key:
                continue
            lookup[key] = key
            lookup[normalize_bike_name(key)] = key
            cleaned_models = []
            if isinstance(model_list, list):
                for model_name in model_list:
                    model = normalize_bike_name(model_name)
                    if not model:
                        continue
                    cleaned_models.append(model)
                    lookup[model] = key
                    lookup[normalize_bike_name(model)] = key
            groups[key] = cleaned_models
    except Exception as e:
        print(f"⚠️ Failed to load bike model groups: {e}")

    BIKE_MODEL_GROUPS = groups
    BIKE_MODEL_GROUP_LOOKUP = lookup
    BIKE_MODEL_GROUP_KEYS = sorted(BIKE_MODEL_GROUPS.keys(), key=lambda s: str(s).lower())
    return BIKE_MODEL_GROUPS


def resolve_bike_model_group(bike_model: str):
    """Resolve a bike model into its group key and list of models."""
    if not bike_model:
        return None, []
    name = bike_model.strip()
    if not name:
        return None, []

    if name in BIKE_MODEL_GROUPS:
        group_key = name
        models = BIKE_MODEL_GROUPS.get(group_key, [])
    else:
        group_key = BIKE_MODEL_GROUP_LOOKUP.get(name, name)
        models = BIKE_MODEL_GROUPS.get(group_key, [name])

    # Ensure unique models while preserving order
    seen = set()
    unique_models = []
    for model in models:
        if model not in seen:
            unique_models.append(model)
            seen.add(model)

    return group_key, unique_models


def get_bike_model_choices():
    """Return bike model names for the dropdown (JSON top-level keys)."""
    if not BIKE_MODEL_KEY_CHOICES:
        load_bike_model_key_choices()
    return BIKE_MODEL_KEY_CHOICES or []


def aggregate_failure_ratio_by_group(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate failure ratio data by bike model group."""
    if df is None or df.empty or not BIKE_MODEL_GROUP_LOOKUP:
        return df

    work_df = df.copy()
    # API may return either totalFailedChassis (new) or totalPartsClaimed (old)
    for col in ["bikeName", "bikeCode", "totalBikeSold", "totalFailedChassis", "totalPartsClaimed", "partsFailureRatio"]:
        if col not in work_df.columns:
            alt = next((c for c in work_df.columns if c.lower() == col.lower()), None)
            if alt:
                work_df[col] = work_df[alt]

    if "bikeName" not in work_df.columns:
        return df

    # Normalize names so minor whitespace differences don't break grouping
    work_df["bikeName"] = work_df["bikeName"].astype(str)
    work_df["__bikeNameNorm"] = work_df["bikeName"].map(normalize_bike_name)
    work_df["__group_key"] = work_df["__bikeNameNorm"].map(
        lambda name: BIKE_MODEL_GROUP_LOOKUP.get(name, name)
    )

    work_df["totalBikeSold"] = pd.to_numeric(work_df.get("totalBikeSold", 0), errors="coerce").fillna(0)
    # Prefer new numerator if present; otherwise fall back to old field.
    if "totalFailedChassis" in work_df.columns:
        work_df["totalFailedChassis"] = pd.to_numeric(work_df.get("totalFailedChassis", 0), errors="coerce").fillna(0)
    else:
        work_df["totalFailedChassis"] = pd.to_numeric(work_df.get("totalPartsClaimed", 0), errors="coerce").fillna(0)

    def _join_unique(values):
        cleaned = [str(v).strip() for v in values if str(v).strip()]
        return ", ".join(dict.fromkeys(cleaned))

    aggregated = (
        work_df.groupby("__group_key", as_index=False)
        .agg(
            bikeCode=("bikeCode", _join_unique),
            totalBikeSold=("totalBikeSold", "sum"),
            totalFailedChassis=("totalFailedChassis", "sum"),
        )
    )
    aggregated["partsFailureRatio"] = aggregated.apply(
        lambda row: (row["totalFailedChassis"] / row["totalBikeSold"]) if row["totalBikeSold"] else 0.0,
        axis=1,
    )
    aggregated["bikeName"] = aggregated["__group_key"]
    aggregated = aggregated.drop(columns=["__group_key"])
    return aggregated


# Load bike model group config
load_bike_model_groups()
load_bike_model_key_choices()


def search_bikes(query: str):
    """Filter bikes locally from pre-loaded list."""
    if not query or len(query.strip()) < 2:
        return gr.update(choices=[])
    
    # Fast local search using pre-loaded list
    query_lower = query.strip().lower()

    choices = get_bike_model_choices()

    # Use generator for faster filtering, limit early
    count = 0
    filtered_names = []
    for name in choices:
        if query_lower in name.lower():
            filtered_names.append(name)
            count += 1
            if count >= 30:  # Limit to 30 for faster rendering
                break
    
    return gr.update(choices=filtered_names)


def create_bar_chart(df, title="Warranty Exposure Dashboard"):
    """Create a horizontal bar chart from the dataframe."""
    if df.empty:
        # Return empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="#64748b")
        )
        fig.update_layout(
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            height=400
        )
        return fig
    
    columns = df.columns.tolist()
    columns_lower = [c.lower() for c in columns]
    
    # Try to find specific columns: partcode, partname, claimcount
    label_col = None
    value_col = None
    code_col = None
    
    # Find claimcount column for values
    for i, col in enumerate(columns_lower):
        if 'claimcount' in col or 'claim_count' in col or 'count' in col:
            value_col = columns[i]
            break

    qty_col = next(
        (col for col in columns if col.lower().replace("_", "") == "totalqty"),
        None,
    )
    
    # Find partname column for labels (y-axis)
    for i, col in enumerate(columns_lower):
        if 'partname' in col or 'part_name' in col or 'name' in col:
            label_col = columns[i]
            break
    
    # Find partcode column for hover display
    for i, col in enumerate(columns_lower):
        if 'partcode' in col or 'part_code' in col or 'code' in col:
            code_col = columns[i]
            break
    
    # Fallback to first/second columns if specific ones not found
    if not label_col and len(columns) >= 1:
        label_col = columns[0]
    if not value_col and len(columns) >= 2:
        value_col = columns[1]
    
    if not value_col:
        return None

    # ---- Aggregate by part name (label) so multiple partCodes for the same partName are summed ----
    work_df = df.copy()
    if label_col:
        work_df[label_col] = work_df[label_col].astype(str)
    if code_col:
        work_df[code_col] = work_df[code_col].astype(str)

    # Ensure numeric values for sorting/gradient
    work_df[value_col] = pd.to_numeric(work_df[value_col], errors="coerce").fillna(0)
    if qty_col:
        work_df[qty_col] = pd.to_numeric(work_df[qty_col], errors="coerce")

    # Aggregate by part name (label_col), summing claim counts and collecting part codes for hover
    if label_col:
        agg_dict = {value_col: (value_col, "sum")}
        if qty_col:
            agg_dict[qty_col] = (qty_col, lambda values: values.sum(min_count=1))
        
        # If partcode column exists, collect unique codes for hover; otherwise just use partname
        if code_col and label_col != code_col:
            agg_dict["__partcodes"] = (code_col, lambda s: ", ".join(dict.fromkeys([x for x in s.tolist() if x])))
        
        work_df = (
            work_df.groupby(label_col, as_index=False)
            .agg(**agg_dict)
        )
        
        # If we created a __partcodes column, use it for hover; otherwise use partname
        if "__partcodes" in work_df.columns:
            code_col = "__partcodes"
        else:
            code_col = None

    # Sort by total claim count (descending); we will reverse later for horizontal top-to-bottom display
    work_df = work_df.sort_values(by=value_col, ascending=False)

    labels = work_df[label_col].astype(str).tolist() if label_col else work_df.index.astype(str).tolist()
    values = work_df[value_col].tolist()
    bar_text = [str(int(v)) if float(v).is_integer() else str(v) for v in values]  # Display values on bars
    partcodes = work_df[code_col].astype(str).tolist() if code_col else labels  # For hover
    hover_label = "Partcode(s)" if code_col else "Part Name"
    
    # Reverse for horizontal bar chart (top to bottom display)
    labels = labels[::-1]
    values = values[::-1]
    bar_text = bar_text[::-1]
    partcodes = partcodes[::-1]
    hover_data = partcodes
    hover_template = f'<b>{hover_label}: %{{customdata}}</b><br>Total Claim Count: %{{x}}<extra></extra>'
    if qty_col:
        quantities = work_df[qty_col].tolist()[::-1]
        hover_data = [
            [part, "Unavailable" if pd.isna(qty) else f"{qty:g}"]
            for part, qty in zip(partcodes, quantities)
        ]
        hover_template = (
            f'<b>{hover_label}: %{{customdata[0]}}</b><br>'
            'Total Claim Count: %{x}<br>Total Qty: %{customdata[1]}<extra></extra>'
        )
    
    # Gradient colors based on claim count:
    # low -> green, mid -> yellow, high -> red
    def _clamp01(x: float) -> float:
        return 0.0 if x < 0 else 1.0 if x > 1 else x

    def _lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _rgb_to_hex(r: float, g: float, b: float) -> str:
        return "#{:02x}{:02x}{:02x}".format(int(round(r)), int(round(g)), int(round(b)))

    def _mix_hex(c1: str, c2: str, t: float) -> str:
        t = _clamp01(t)
        r1, g1, b1 = _hex_to_rgb(c1)
        r2, g2, b2 = _hex_to_rgb(c2)
        return _rgb_to_hex(_lerp(r1, r2, t), _lerp(g1, g2, t), _lerp(b1, b2, t))

    def _relative_luminance(hex_color: str) -> float:
        # WCAG-ish luminance estimate for contrast choice
        r, g, b = _hex_to_rgb(hex_color)
        rs, gs, bs = r / 255.0, g / 255.0, b / 255.0
        return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs

    try:
        numeric_values = [float(v) for v in values]
    except Exception:
        numeric_values = [0.0 for _ in values]

    vmin = min(numeric_values) if numeric_values else 0.0
    vmax = max(numeric_values) if numeric_values else 1.0
    denom = (vmax - vmin) if (vmax - vmin) != 0 else 1.0

    green = "#22c55e"
    yellow = "#facc15"
    red = "#ef4444"

    bar_colors: list[str] = []
    text_colors: list[str] = []
    for v in numeric_values:
        t = _clamp01((v - vmin) / denom)
        if t <= 0.5:
            c = _mix_hex(green, yellow, t * 2.0)
        else:
            c = _mix_hex(yellow, red, (t - 0.5) * 2.0)
        bar_colors.append(c)
        text_colors.append("#0b1220" if _relative_luminance(c) > 0.62 else "#ffffff")
    
    # Create horizontal bar chart
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=labels,
        x=values,
        orientation='h',
        marker=dict(
            color=bar_colors,
            line=dict(color='rgba(255,255,255,0.3)', width=1)
        ),
        text=bar_text,
        textposition='inside',
        insidetextanchor='end',
        textfont=dict(color=text_colors, size=12, family='Outfit, sans-serif'),
        customdata=hover_data,
        hovertemplate=hover_template
    ))
    
    # Get the title from column names
    value_title = value_col.replace('_', ' ').title() if value_col else "Count"
    
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=18, color='#1e293b'),
            x=0.5,
            xanchor='center'
        ),
        paper_bgcolor='#ffffff',
        plot_bgcolor='#ffffff',
        font=dict(color='#1e293b', family='Outfit, sans-serif'),
        height=max(400, len(labels) * 50),  # Dynamic height based on data
        margin=dict(l=20, r=80, t=60, b=40),
        xaxis=dict(
            showgrid=True,
            gridcolor='#e2e8f0',
            gridwidth=1,
            zeroline=False,
            tickfont=dict(color='#64748b', size=12),
            title=dict(text=value_title, font=dict(color='#64748b', size=12))
        ),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(color='#1e293b', size=13),
            ticksuffix='  ',
        ),
        bargap=0.3,
        showlegend=False
    )
    
    return fig


def create_empty_figure(message="No data available", height=400):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=18, color="#64748b")
    )
    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        height=height
    )
    return fig


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def normalize_prediction_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize prediction columns to expected names."""
    if df is None or df.empty:
        return df

    normalized = {_normalize_key(col): col for col in df.columns}
    mapping = {
        "date": "date",
        "productname": "ProductName",
        "bikemodel": "BikeModel",
        "regionname": "RegionName",
        "predictedclaimcount": "PredictedClaimCount",
    }

    for key, target in mapping.items():
        source = normalized.get(key)
        if source and target not in df.columns:
            df[target] = df[source]

    return df


def load_historical_monthly_data(resolved_path: str | None = None) -> pd.DataFrame:
    """Load historical monthly claim counts from df_monthly_enhanced_filled.csv."""
    if not resolved_path:
        resolved_path = ENHANCED_DATA_PATH
        if not os.path.exists(resolved_path):
            resolved_path = resolve_enhanced_data_path()

    if not os.path.exists(resolved_path):
        return pd.DataFrame()

    print(f"Loading historical monthly data from {resolved_path}")
    df = pd.read_csv(resolved_path)
    if df.empty:
        return df

    if "date" not in df.columns:
        if "year" in df.columns and "month" in df.columns:
            df["date"] = pd.to_datetime(
                df["year"].astype(str) + "-" + df["month"].astype(str) + "-01",
                errors="coerce"
            )

    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")

    if "ClaimCount" not in df.columns:
        alt = next((c for c in df.columns if c.lower() == "claimcount"), None)
        if alt:
            df["ClaimCount"] = df[alt]

    df["ClaimCount"] = pd.to_numeric(df.get("ClaimCount", 0), errors="coerce").fillna(0)

    return df[["date", "ClaimCount"]].dropna(subset=["date"])


def create_prediction_line_chart(history_df: pd.DataFrame, pred_df: pd.DataFrame):
    if (history_df is None or history_df.empty) and (pred_df is None or pred_df.empty):
        return create_empty_figure("No historical or predicted data available", height=420)

    fig = go.Figure()

    if history_df is not None and not history_df.empty:
        fig.add_trace(
            go.Scatter(
                x=history_df["month"],
                y=history_df["count"],
                mode="lines+markers",
                name="Historical (Actual)",
                line=dict(color="#3b82f6", width=3),
                marker=dict(size=8),
                fill="tozeroy",
                fillcolor="rgba(59, 130, 246, 0.20)",
            )
        )

    if pred_df is not None and not pred_df.empty:
        fig.add_trace(
            go.Scatter(
                x=pred_df["month"],
                y=pred_df["count"],
                mode="lines+markers",
                name="Predicted (Next 6 Months)",
                line=dict(color="#ef4444", width=3, dash="dash"),
                marker=dict(size=8, symbol="square"),
                fill="tozeroy",
                fillcolor="rgba(239, 68, 68, 0.20)",
            )
        )

        if history_df is not None and not history_df.empty:
            boundary = pred_df["month"].min()
            if pd.notna(boundary):
                fig.add_vline(x=boundary, line_width=1, line_dash="dot", line_color="#94a3b8")

    fig.update_layout(
        title=dict(
            text="<b>11-Month Warranty Parts Forecast (5 Months Historical + 6 Months Predicted)</b>",
            font=dict(size=18, color="#1e293b"),
            x=0.5,
            xanchor="center",
        ),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#1e293b", family="Outfit, sans-serif"),
        height=460,
        margin=dict(l=30, r=30, t=70, b=50),
        xaxis=dict(
            title=dict(text="Month", font=dict(color="#64748b", size=12)),
            tickformat="%b %Y",
            showgrid=True,
            gridcolor="#e2e8f0",
        ),
        yaxis=dict(
            title=dict(text="Total Failed Parts (Claim Count)", font=dict(color="#64748b", size=12)),
            showgrid=True,
            gridcolor="#e2e8f0",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    return fig


def create_predicted_parts_bar_chart(df: pd.DataFrame, top_n: int = 10):
    if df is None or df.empty:
        return create_empty_figure("No predicted parts data available", height=420)

    agg = (
        df.groupby("ProductName", as_index=False)["PredictedClaimCount"]
        .sum()
        .sort_values("PredictedClaimCount", ascending=False)
        .head(top_n)
    )

    if agg.empty:
        return create_empty_figure("No predicted parts data available", height=420)

    agg = agg.sort_values("PredictedClaimCount", ascending=True)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=agg["PredictedClaimCount"],
            y=agg["ProductName"],
            orientation="h",
            marker=dict(color="#ef4444"),
            text=agg["PredictedClaimCount"].round(2),
            textposition="outside",
        )
    )
    fig.update_layout(
        title=dict(
            text=f"<b>Top {len(agg)} Parts Predicted to Fail (Next 6 Months)</b>",
            font=dict(size=16, color="#1e293b"),
            x=0.5,
            xanchor="center",
        ),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#1e293b", family="Outfit, sans-serif"),
        height=max(420, len(agg) * 45),
        margin=dict(l=20, r=40, t=60, b=40),
        xaxis=dict(
            title=dict(text="Predicted Claim Count (6 Months)", font=dict(color="#64748b", size=12)),
            showgrid=True,
            gridcolor="#e2e8f0",
        ),
        yaxis=dict(showgrid=False),
        showlegend=False,
    )
    return fig


def create_bike_model_pie_chart(df: pd.DataFrame, top_n: int = 8):
    if df is None or df.empty:
        return create_empty_figure("No bike model distribution available", height=420)

    agg = (
        df.groupby("BikeModel", as_index=False)["PredictedClaimCount"]
        .sum()
        .sort_values("PredictedClaimCount", ascending=False)
    )

    if agg.empty:
        return create_empty_figure("No bike model distribution available", height=420)

    top = agg.head(top_n).copy()
    rest = agg.iloc[top_n:]
    if not rest.empty:
        top = pd.concat(
            [
                top,
                pd.DataFrame(
                    [{"BikeModel": "Other", "PredictedClaimCount": rest["PredictedClaimCount"].sum()}]
                ),
            ],
            ignore_index=True,
        )

    fig = go.Figure(
        data=[
            go.Pie(
                labels=top["BikeModel"],
                values=top["PredictedClaimCount"],
                hole=0.2,
                textinfo="percent+label",
            )
        ]
    )
    fig.update_layout(
        title=dict(
            text="<b>Predicted Failures by Bike Model (Next 6 Months)</b>",
            font=dict(size=16, color="#1e293b"),
            x=0.5,
            xanchor="center",
        ),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#1e293b", family="Outfit, sans-serif"),
        height=420,
        margin=dict(l=20, r=20, t=60, b=40),
        showlegend=True,
    )
    return fig


def fetch_prediction_dashboard(top_n_parts):
    """Fetch predictions and build the forecast dashboard."""
    try:
        if top_n_parts is None or top_n_parts == "" or top_n_parts == 0:
            top_n_parts = 10
        top_n_parts = max(1, int(top_n_parts))

        response = requests.get(API_URL_PREDICTION_DETAILED, timeout=60)
        response.raise_for_status()
        payload = response.json()

        df_pred = pd.DataFrame()
        historical_block = None
        if isinstance(payload, dict) and "data" in payload:
            data_block = payload["data"]
            if isinstance(data_block, dict) and "columns" in data_block and "data" in data_block:
                df_pred = pd.DataFrame(data_block["data"], columns=data_block["columns"])
                historical_block = data_block.get("historical")
            elif isinstance(data_block, list):
                df_pred = pd.DataFrame(data_block)
        elif isinstance(payload, list):
            df_pred = pd.DataFrame(payload)

        df_pred = normalize_prediction_columns(df_pred)

        required_cols = ["date", "ProductName", "BikeModel", "PredictedClaimCount"]
        missing = [col for col in required_cols if col not in df_pred.columns]
        if missing:
            empty = create_empty_figure("Prediction response missing columns", height=420)
            return empty, empty, empty, f"❌ Missing prediction columns: {', '.join(missing)}"

        df_pred["date"] = pd.to_datetime(df_pred["date"], errors="coerce")
        df_pred["PredictedClaimCount"] = pd.to_numeric(
            df_pred["PredictedClaimCount"], errors="coerce"
        ).fillna(0)

        df_pred = df_pred.dropna(subset=["date"])

        if df_pred.empty:
            empty = create_empty_figure("No predicted data returned", height=420)
            return empty, empty, empty, "No prediction data returned."

        df_pred["month"] = df_pred["date"].dt.to_period("M").dt.to_timestamp()

        pred_start = df_pred["month"].min()
        pred_end = df_pred["month"].max()
        pred_range_df = df_pred[(df_pred["month"] >= pred_start) & (df_pred["month"] <= pred_end)]

        pred_monthly = (
            pred_range_df.groupby("month", as_index=False)["PredictedClaimCount"].sum()
        )
        month_index = pd.date_range(pred_start, pred_end, freq="MS")
        pred_monthly = (
            pred_monthly.set_index("month")
            .reindex(month_index, fill_value=0)
            .reset_index()
            .rename(columns={"index": "month", "PredictedClaimCount": "count"})
        )

        historical_df = pd.DataFrame()
        if isinstance(historical_block, dict):
            if "columns" in historical_block and "data" in historical_block:
                historical_df = pd.DataFrame(
                    historical_block["data"],
                    columns=historical_block["columns"],
                )
            elif isinstance(historical_block.get("data"), list):
                historical_df = pd.DataFrame(historical_block["data"])

        history_monthly = pd.DataFrame()
        history_note = ""
        if historical_df is not None and not historical_df.empty:
            if "date" not in historical_df.columns:
                history_note = "⚠️ Historical query response is missing its date column."
                historical_df = pd.DataFrame()
            else:
                historical_df["date"] = pd.to_datetime(historical_df["date"], errors="coerce")
                historical_df = historical_df.dropna(subset=["date"])
            if not historical_df.empty:
                claim_count_col = next(
                    (col for col in historical_df.columns if col.lower() == "claimcount"),
                    None,
                )
                if claim_count_col is None:
                    history_note = "⚠️ Historical query response is missing ClaimCount."
                    historical_df = pd.DataFrame()
                else:
                    historical_df["ClaimCount"] = pd.to_numeric(
                        historical_df[claim_count_col], errors="coerce"
                    ).fillna(0)

        hist_start = pred_start - pd.DateOffset(months=5)
        hist_end = pred_start - pd.DateOffset(months=1)
        history_index = pd.date_range(hist_start, hist_end, freq="MS")
        if historical_df is not None and not historical_df.empty:
            historical_df["month"] = historical_df["date"].dt.to_period("M").dt.to_timestamp()
            historical_range = historical_df[
                (historical_df["month"] >= hist_start) & (historical_df["month"] <= hist_end)
            ]
            history_monthly = (
                historical_range.groupby("month", as_index=False)["ClaimCount"].sum()
            )
            history_monthly = (
                history_monthly.set_index("month")
                .reindex(history_index, fill_value=0)
                .reset_index()
                .rename(columns={"index": "month", "ClaimCount": "count"})
            )
            if historical_range.empty and not history_note:
                history_note = "⚠️ No historical monthly claims were returned for this period."
        else:
            history_monthly = pd.DataFrame({"month": history_index, "count": 0})
            if not history_note:
                history_note = "⚠️ No historical monthly data was returned by the database query."

        line_chart = create_prediction_line_chart(history_monthly, pred_monthly)
        bar_chart = create_predicted_parts_bar_chart(pred_range_df, top_n=top_n_parts)
        pie_chart = create_bike_model_pie_chart(pred_range_df)

        status = (
            f"✅ Loaded {len(df_pred)} prediction rows. Top N parts = {top_n_parts}. "
            f"History: {hist_start:%b %Y}–{hist_end:%b %Y}; "
            f"prediction: {pred_start:%b %Y}–{pred_end:%b %Y}."
        )
        if history_note:
            status = f"{status} {history_note}"

        return line_chart, bar_chart, pie_chart, status

    except requests.exceptions.ConnectionError:
        empty = create_empty_figure("Connection error", height=420)
        return empty, empty, empty, "❌ Connection Error: Could not connect to the API."
    except requests.exceptions.Timeout:
        empty = create_empty_figure("Request timeout", height=420)
        return empty, empty, empty, "❌ Timeout: The request took too long to complete."
    except requests.exceptions.HTTPError as e:
        empty = create_empty_figure("HTTP error", height=420)
        return empty, empty, empty, f"❌ HTTP Error: {e}"
    except Exception as e:
        empty = create_empty_figure("Unexpected error", height=420)
        return empty, empty, empty, f"❌ Error: {str(e)}"


def convert_date_to_string(date_value):
    """Convert date to YYYY-MM-DD string format."""
    from datetime import datetime
    
    if date_value is None or date_value == "":
        return None
    
    # If it's already a string in date format
    if isinstance(date_value, str):
        date_str = date_value.strip()
        if date_str:
            return date_str
        return None
    
    # If it's a datetime object
    if hasattr(date_value, 'strftime'):
        return date_value.strftime("%Y-%m-%d")
    
    # If it's a timestamp (number) - Gradio DateTime returns timestamp
    if isinstance(date_value, (int, float)):
        try:
            dt = datetime.fromtimestamp(date_value)
            return dt.strftime("%Y-%m-%d")
        except:
            pass
    
    # Try to convert to string as fallback
    try:
        return str(date_value)
    except:
        return None


def aggregate_parts_by_name(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate part counts across bike models by part name."""
    if df is None or df.empty:
        return df

    columns = df.columns.tolist()
    columns_lower = [c.lower() for c in columns]

    label_col = None
    value_col = None
    code_col = None

    for i, col in enumerate(columns_lower):
        if "claimcount" in col or "claim_count" in col or "count" in col:
            value_col = columns[i]
            break

    for i, col in enumerate(columns_lower):
        if "partname" in col or "part_name" in col or (col == "name"):
            label_col = columns[i]
            break

    for i, col in enumerate(columns_lower):
        if "partcode" in col or "part_code" in col or col == "code":
            code_col = columns[i]
            break

    if not label_col or not value_col:
        return df

    work_df = df.copy()
    work_df[label_col] = work_df[label_col].astype(str)
    work_df[value_col] = pd.to_numeric(work_df[value_col], errors="coerce").fillna(0)
    if code_col:
        work_df[code_col] = work_df[code_col].astype(str)

    def _join_unique(values):
        cleaned = [str(v).strip() for v in values if str(v).strip()]
        return ", ".join(dict.fromkeys(cleaned))

    agg_map = {value_col: (value_col, "sum")}
    if code_col:
        agg_map["__partcodes"] = (code_col, _join_unique)

    aggregated = work_df.groupby(label_col, as_index=False).agg(**agg_map)
    if "__partcodes" in aggregated.columns:
        aggregated[code_col] = aggregated["__partcodes"]
        aggregated = aggregated.drop(columns=["__partcodes"])

    return aggregated


def fetch_top_parts(limit, from_date, to_date):
    """Fetch top warranty parts for the results table and status message."""
    empty_table = pd.DataFrame(columns=["Part Name", "Claim Count", "Total Qty"])
    try:
        # Convert dates to string format YYYY-MM-DD
        from_date_str = convert_date_to_string(from_date)
        to_date_str = convert_date_to_string(to_date)
        print(from_date_str,type(from_date_str))
        print(to_date_str,type(to_date_str))
        # from_date is REQUIRED by the API
        if not from_date_str:
            return "⚠️ Please select a From Date (required)", empty_table
        
        # Build params - send only string values
        params = {}
        if limit is not None and limit != "" and limit != 0:
            params["limit"] = int(limit)
        
        # Add dates as strings (YYYY-MM-DD format)
        params["from_date"] = from_date_str
        
        # to_date is optional (API defaults to today)
        if to_date_str:
            params["to_date"] = to_date_str
        
        response = requests.get(API_URL_TOP_PARTS, params=params, timeout=30)
        response.raise_for_status()
        print(API_URL_TOP_PARTS)
        data = response.json()
        print(data)
        
        # Handle different response formats
        if isinstance(data, list):
            if len(data) == 0:
                return "No data found for the given parameters.", empty_table
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            if "data" in data:
                df = pd.DataFrame(data["data"])
            elif "results" in data:
                df = pd.DataFrame(data["results"])
            else:
                df = pd.DataFrame([data])
        else:
            return f"Unexpected response format: {type(data)}", empty_table
        
        # If the API returns a partcode column for top parts, ignore it and render by PartName only.
        if not df.empty:
            columns_lower = [c.lower() for c in df.columns]
            code_col = next(
                (col for col in df.columns if "partcode" in col.lower() or "part_code" in col.lower() or col.lower() == "code"),
                None,
            )
            if code_col:
                df = df.drop(columns=[code_col])

        if df.empty:
            return "No data found for the given parameters.", empty_table

        # Accept the API's camelCase keys and SQL-style column names.
        column_map = {col.lower().replace("_", ""): col for col in df.columns}
        table = pd.DataFrame(index=df.index)
        for key, label in (
            ("partname", "Part Name"),
            ("claimcount", "Claim Count"),
            ("totalqty", "Total Qty"),
        ):
            source = column_map.get(key)
            table[label] = df[source] if source else None

        # Bar chart disabled; display claim count and quantity in the table.
        # fig = create_bar_chart(df, "Warranty Exposure Dashboard")
        
        status = f"✅ Top {len(df)} Warranty Claimed Parts"
        if "totalqty" not in column_map:
            status += " — Total Qty unavailable in the API response."
        return status, table
        
    except requests.exceptions.ConnectionError:
        return "❌ Connection Error: Could not connect to the API. Make sure the server is running.", empty_table
    except requests.exceptions.Timeout:
        return "❌ Timeout: The request took too long to complete.", empty_table
    except requests.exceptions.HTTPError as e:
        return f"❌ HTTP Error: {e}", empty_table
    except Exception as e:
        return f"❌ Error: {str(e)}", empty_table


def fetch_parts_for_bike_model(limit, bike_model: str, from_date, to_date):
    """Fetch top warranty parts for a specific bike model from the API."""
    try:
        # Check if bike_model is provided (required)
        if not bike_model:
            fig = create_bar_chart(pd.DataFrame())
            return fig, "⚠️ Please select a bike model first"

        # Convert dates to string format YYYY-MM-DD
        from_date_str = convert_date_to_string(from_date)
        to_date_str = convert_date_to_string(to_date)

        # from_date is REQUIRED by the API
        if not from_date_str:
            fig = create_bar_chart(pd.DataFrame())
            return fig, "⚠️ Please select a From Date (required)"
        
        params = {"bike_model": bike_model.strip()}
        if limit is not None and limit != "" and limit != 0:
            params["limit"] = int(limit)
        params["from_date"] = from_date_str
        if to_date_str:
            params["to_date"] = to_date_str

        response = requests.get(API_URL_BIKE_MODEL, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Handle different response formats
        if isinstance(data, list):
            if len(data) == 0:
                fig = create_bar_chart(pd.DataFrame())
                return fig, "No data found for the given parameters."
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            if "data" in data:
                df = pd.DataFrame(data["data"])
            elif "results" in data:
                df = pd.DataFrame(data["results"])
            else:
                df = pd.DataFrame([data])
        else:
            fig = create_bar_chart(pd.DataFrame())
            return fig, f"Unexpected response format: {type(data)}"

        # If the API returns a partcode column for parts-by-bike-model, ignore it and render by PartName only.
        if not df.empty:
            code_col = next(
                (col for col in df.columns if "partcode" in col.lower() or "part_code" in col.lower() or col.lower() == "code"),
                None,
            )
            if code_col:
                df = df.drop(columns=[code_col])
        
        # Create the chart with bike model in title
        display_label = bike_model
        chart_title = f"Top Parts for {display_label}" if display_label else "Top Parts by Bike Model"
        fig = create_bar_chart(df, chart_title)

        status = f"✅ Parts for {display_label}"

        return fig, status
        
    except requests.exceptions.ConnectionError:
        fig = create_bar_chart(pd.DataFrame())
        return fig, "❌ Connection Error: Could not connect to the API. Make sure the server is running."
    except requests.exceptions.Timeout:
        fig = create_bar_chart(pd.DataFrame())
        return fig, "❌ Timeout: The request took too long to complete."
    except requests.exceptions.HTTPError as e:
        fig = create_bar_chart(pd.DataFrame())
        return fig, f"❌ HTTP Error: {e}"
    except Exception as e:
        fig = create_bar_chart(pd.DataFrame())
        return fig, f"❌ Error: {str(e)}"


def create_failure_ratio_chart(df: pd.DataFrame, title: str = "Bike Model Failure Ratio"):
    """Create a horizontal bar chart for bike model failure ratios with hover details."""
    if df is None or df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20, color="#64748b"),
        )
        fig.update_layout(paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", height=400)
        return fig

    # Normalize expected columns (API returns camelCase)
    work_df = df.copy()
    for col in ["bikeName", "bikeCode", "totalBikeSold", "totalFailedChassis", "totalPartsClaimed", "partsFailureRatio"]:
        if col not in work_df.columns:
            # Allow some flexibility if keys differ
            alt = next((c for c in work_df.columns if c.lower() == col.lower()), None)
            if alt:
                work_df[col] = work_df[alt]

    if "partsFailureRatio" not in work_df.columns or "bikeName" not in work_df.columns:
        return create_bar_chart(df, title)

    work_df["partsFailureRatio"] = pd.to_numeric(work_df["partsFailureRatio"], errors="coerce").fillna(0.0)
    work_df["totalBikeSold"] = pd.to_numeric(work_df.get("totalBikeSold", 0), errors="coerce").fillna(0).astype(int)
    # Prefer new numerator if present; otherwise fall back to old field.
    if "totalFailedChassis" in work_df.columns:
        work_df["totalFailedChassis"] = (
            pd.to_numeric(work_df.get("totalFailedChassis", 0), errors="coerce").fillna(0).astype(int)
        )
    else:
        work_df["totalFailedChassis"] = (
            pd.to_numeric(work_df.get("totalPartsClaimed", 0), errors="coerce").fillna(0).astype(int)
        )

    # Sort by failure ratio (descending); we will reverse later for horizontal top-to-bottom display.
    work_df = work_df.sort_values(by="partsFailureRatio", ascending=False)

    labels = work_df["bikeName"].astype(str).tolist()
    values = work_df["partsFailureRatio"].astype(float).tolist()

    # Put highest at top in a horizontal bar chart
    labels = labels[::-1]
    values = values[::-1]

    # Hover details (aligned with reversed labels/values)
    bike_codes = work_df.get("bikeCode", pd.Series([""] * len(work_df))).astype(str).tolist()[::-1]
    sold = work_df.get("totalBikeSold", pd.Series([0] * len(work_df))).astype(int).tolist()[::-1]
    failed_chassis = work_df.get("totalFailedChassis", pd.Series([0] * len(work_df))).astype(int).tolist()[::-1]

    # Gradient colors top-to-bottom: red -> yellow -> green
    # Since we sort desc (top = highest ratio), mapping by value gives the desired visual.
    def _clamp01(x: float) -> float:
        return 0.0 if x < 0 else 1.0 if x > 1 else x

    def _lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _rgb_to_hex(r: float, g: float, b: float) -> str:
        return "#{:02x}{:02x}{:02x}".format(int(round(r)), int(round(g)), int(round(b)))

    def _mix_hex(c1: str, c2: str, t: float) -> str:
        t = _clamp01(t)
        r1, g1, b1 = _hex_to_rgb(c1)
        r2, g2, b2 = _hex_to_rgb(c2)
        return _rgb_to_hex(_lerp(r1, r2, t), _lerp(g1, g2, t), _lerp(b1, b2, t))

    try:
        numeric_values = [float(v) for v in values]
    except Exception:
        numeric_values = [0.0 for _ in values]

    vmin = min(numeric_values) if numeric_values else 0.0
    vmax = max(numeric_values) if numeric_values else 1.0
    denom = (vmax - vmin) if (vmax - vmin) != 0 else 1.0

    green = "#22c55e"
    yellow = "#facc15"
    red = "#ef4444"

    bar_colors: list[str] = []
    for v in numeric_values:
        t = _clamp01((v - vmin) / denom)
        if t <= 0.5:
            c = _mix_hex(green, yellow, t * 2.0)
        else:
            c = _mix_hex(yellow, red, (t - 0.5) * 2.0)
        bar_colors.append(c)

    # Display as percentage for readability
    bar_text = [f"{(v * 100.0):.2f}%" for v in values]

    customdata = list(zip(bike_codes, sold, failed_chassis))

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=labels,
            x=values,
            orientation="h",
            marker=dict(color=bar_colors, line=dict(color="rgba(255,255,255,0.3)", width=1)),
            text=bar_text,
            textposition="inside",
            insidetextanchor="end",
            textfont=dict(color="#0b1220", size=12, family="Outfit, sans-serif"),
            customdata=customdata,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Bike Code: %{customdata[0]}<br>"
                "Failure Ratio: %{x:.4f}<br>"
                "Total Bike Sold: %{customdata[1]}<br>"
                "Total Failed Chassis: %{customdata[2]}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=18, color="#1e293b"), x=0.5, xanchor="center"),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#1e293b", family="Outfit, sans-serif"),
        height=max(450, len(labels) * 42),
        margin=dict(l=20, r=80, t=60, b=40),
        xaxis=dict(
            showgrid=True,
            gridcolor="#e2e8f0",
            gridwidth=1,
            zeroline=False,
            tickfont=dict(color="#64748b", size=12),
            title=dict(text="Parts Failure Ratio", font=dict(color="#64748b", size=12)),
            tickformat=".2%",
        ),
        yaxis=dict(showgrid=False, tickfont=dict(color="#1e293b", size=13), ticksuffix="  "),
        bargap=0.3,
        showlegend=False,
    )

    return fig


def fetch_failure_ratio():
    """Fetch bike model failure ratios from the API."""
    try:
        limit = 100
        params = {}
        if limit is not None and limit != "" and limit != 0:
            params["limit"] = int(limit)

        response = requests.get(API_URL_FAILURE_RATIO, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            if "data" in data:
                df = pd.DataFrame(data["data"])
            elif "results" in data:
                df = pd.DataFrame(data["results"])
            else:
                df = pd.DataFrame([data])
        else:
            fig = create_failure_ratio_chart(pd.DataFrame())
            return fig, f"Unexpected response format: {type(data)}"

        if df.empty:
            fig = create_failure_ratio_chart(pd.DataFrame())
            return fig, "No data found."

        aggregated_df = aggregate_failure_ratio_by_group(df)
        fig = create_failure_ratio_chart(
            aggregated_df,
            "Bike Model Failure Ratio (Unique Failed Chassis / Bikes Sold)",
        )
        return fig, f""

    except requests.exceptions.ConnectionError:
        fig = create_failure_ratio_chart(pd.DataFrame())
        return fig, "❌ Connection Error: Could not connect to the API. Make sure the server is running."
    except requests.exceptions.Timeout:
        fig = create_failure_ratio_chart(pd.DataFrame())
        return fig, "❌ Timeout: The request took too long to complete."
    except requests.exceptions.HTTPError as e:
        fig = create_failure_ratio_chart(pd.DataFrame())
        return fig, f"❌ HTTP Error: {e}"
    except Exception as e:
        fig = create_failure_ratio_chart(pd.DataFrame())
        return fig, f"❌ Error: {str(e)}"


# Custom CSS for a modern look
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Outfit:wght@400;500;600;700&display=swap');

:root {
    --primary-color: #0ea5e9;
    --primary-hover: #0284c7;
    --bg-light: #ffffff;
    --bg-card: #f8fafc;
    --text-primary: #1e293b;
    --text-secondary: #64748b;
    --accent-green: #22c55e;
    --accent-red: #ef4444;
    --border-color: #e2e8f0;
    /* Inputs: slightly warmer white to stand out from card background */
    --field-bg: #ffffff;
    --field-border: #94a3b8;
    --field-focus: #0ea5e9;
    /* Status: calm info tone */
    --status-bg: #f0f9ff;
    --status-border: #7dd3fc;

    /* Dropdown (bike model): subtle tint so it doesn't blend with card */
    --dropdown-bg: #ffffff;
}

/* Fallback: ensure vars available even if :root scoping differs */
.gradio-container {
    --field-bg: var(--field-bg);
    --field-border: var(--field-border);
    --field-focus: var(--field-focus);
    --status-bg: var(--status-bg);
    --status-border: var(--status-border);
}

.gradio-container {
    font-family: 'Outfit', sans-serif !important;
    background: #ffffff !important;
    min-height: 100vh;
    color-scheme: light;
}

.main-header {
    text-align: center;
    padding: 2rem 0;
    margin-bottom: 1rem;
}

.main-header h1 {
    font-family: 'Outfit', sans-serif !important;
    font-size: 2.5rem !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, #0ea5e9 0%, #8b5cf6 50%, #ec4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.5rem;
}

.main-header p {
    color: var(--text-secondary);
    font-size: 1.1rem;
}

.gr-panel, .gr-box {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 12px !important;
}

/* Inputs: ensure consistent, eye-soothing contrast across browsers */
.gradio-container .gr-input input,
.gradio-container .gr-input textarea,
.gradio-container .gr-input select,
.gradio-container .gr-number input,
.gradio-container .gr-textbox input,
.gradio-container .gr-textbox textarea,
.gradio-container .gr-dropdown select {
    background: var(--field-bg) !important;
    border: 1px solid var(--field-border) !important;
    color: var(--text-primary) !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}

/* Bike model dropdown: slightly tinted background for better visibility */
.gradio-container .gr-dropdown select {
    background: var(--dropdown-bg) !important;
}

/* Gradio 6 Dropdown is a combobox (input), not a native <select>.
   Target the specific bike dropdown via elem_id for reliable styling. */
#bike-model-dropdown input,
#bike-model-dropdown textarea,
#bike-model-dropdown [role="combobox"],
#bike-model-dropdown [role="textbox"] {
    background: var(--dropdown-bg) !important;
}

#bike-model-dropdown input:focus,
#bike-model-dropdown textarea:focus,
#bike-model-dropdown [role="combobox"]:focus,
#bike-model-dropdown [role="textbox"]:focus {
    background: var(--dropdown-bg) !important;
}

/* Gradio theme-driven styling: set the local theme variables so the entire
   dropdown control (container + arrow button) uses our dropdown background. */
#bike-model-dropdown {
    --input-background-fill: var(--dropdown-bg);
    --input-background-fill-focus: var(--dropdown-bg);
    --input-border-color: var(--field-border);
    --input-border-color-focus: var(--field-focus);
    --input-placeholder-color: #94a3b8;
    --input-shadow-focus: 0 0 0 3px rgba(14, 165, 233, 0.20);
}

/* Make the visible dropdown "box" white (not just the text input) */
#bike-model-dropdown .gradio-style,
#bike-model-dropdown .gradio-style > div,
#bike-model-dropdown .gradio-style > label,
#bike-model-dropdown .gradio-style > span {
    background: #ffffff !important;
}

#bike-model-dropdown .gradio-style,
#bike-model-dropdown .gradio-style * {
    --input-background-fill: var(--dropdown-bg);
    --input-background-fill-focus: var(--dropdown-bg);
}

/* Try common button/icon areas inside the dropdown (arrow area) */
#bike-model-dropdown button,
#bike-model-dropdown [role="button"] {
    background: var(--dropdown-bg) !important;
}

/* Dropdown popup menu (the expanded list of options) */
.gradio-container [role="listbox"] {
    background: #ffffff !important;
    border: 1px solid var(--field-border) !important;
}

.gradio-container [role="option"] {
    background: transparent !important;
    color: var(--text-primary) !important;
}

.gradio-container [role="option"][aria-selected="true"] {
    background: #e0f2fe !important;
}

.gradio-container [role="option"]:hover,
.gradio-container [role="option"]:focus {
    background: #f1f5f9 !important;
}

/* Extra-wide net for Gradio v4 DOM changes */
.gradio-container input:not([type="checkbox"]):not([type="radio"]),
.gradio-container textarea,
.gradio-container select {
    background: var(--field-bg) !important;
    border-color: var(--field-border) !important;
    color: var(--text-primary) !important;
}

.gradio-container .gr-input input::placeholder,
.gradio-container .gr-input textarea::placeholder {
    color: #94a3b8 !important;
    opacity: 1 !important;
}

.gradio-container .gr-input input:focus,
.gradio-container .gr-input textarea:focus,
.gradio-container .gr-input select:focus,
.gradio-container .gr-number input:focus,
.gradio-container .gr-textbox input:focus,
.gradio-container .gr-textbox textarea:focus,
.gradio-container .gr-dropdown select:focus {
    outline: none !important;
    border-color: var(--field-focus) !important;
    background: var(--dropdown-bg) !important;
    box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.20) !important;
}

/* Disabled/read-only fields (e.g., Status output) shouldn't fade into the card */
.gradio-container input:disabled,
.gradio-container textarea:disabled,
.gradio-container select:disabled,
.gradio-container input[readonly],
.gradio-container textarea[readonly] {
    opacity: 1 !important;
    color: #0f172a !important;
}

/* Chrome autofill */
.gradio-container input:-webkit-autofill,
.gradio-container textarea:-webkit-autofill {
    -webkit-text-fill-color: var(--text-primary) !important;
    box-shadow: 0 0 0px 1000px var(--field-bg) inset !important;
    transition: background-color 9999s ease-in-out 0s;
}

/* Number spinners: normalize Chrome/Firefox look */
.gradio-container input[type="number"]::-webkit-outer-spin-button,
.gradio-container input[type="number"]::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
.gradio-container input[type="number"] {
    -moz-appearance: textfield;
    appearance: textfield;
}

/* Status bars (Textbox outputs): subtle blue background, clear border */
.status-output textarea,
.status-output input {
    background: var(--status-bg) !important;
    border-color: var(--status-border) !important;
}

/* DateTime (calendar) inputs: force white background instead of dark */
.date-input input,
.date-input textarea,
.date-input [role="textbox"],
.date-input [role="combobox"] {
    background: #ffffff !important;
    color: var(--text-primary) !important;
}

/* Calendar button area */
.date-input button,
.date-input [role="button"] {
    background: #ffffff !important;
    color: var(--text-primary) !important;
}

.date-input button svg,
.date-input [role="button"] svg {
    color: var(--text-primary) !important;
    fill: currentColor !important;
}

/* Tabs + headings text colors */
.gradio-container h1,
.gradio-container h2,
.gradio-container h3,
.gradio-container h4 {
    color: var(--text-primary) !important;
}

.gradio-container [role="tablist"] button,
.gradio-container button[role="tab"],
.gradio-container .tab-nav button {
    color: var(--text-primary) !important;
}

.gradio-container button[role="tab"][aria-selected="true"],
.gradio-container .tab-nav button.selected {
    color: var(--primary-hover) !important;
    font-weight: 600 !important;
}

.gr-button-primary {
    background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%) !important;
    border: none !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    padding: 12px 24px !important;
    border-radius: 10px !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(14, 165, 233, 0.3) !important;
}

.gr-button-primary:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(14, 165, 233, 0.4) !important;
}

.status-box {
    padding: 1rem;
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.9rem;
}

label {
    color: var(--text-primary) !important;
    font-weight: 500 !important;
}

footer {
    visibility: hidden;
}
"""

# Build the Gradio interface
with gr.Blocks() as app:
    
    gr.HTML("""
        <div class="main-header">
            <h1>🔧 Motors Job Card</h1>
            <p>Analyze top warranty parts data from the API</p>
        </div>
    """)
    
    with gr.Tabs():
        # Tab 1: Top Parts
        with gr.TabItem("📊 Top Parts"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Query Parameters")

                    from_date_input_1 = gr.DateTime(
                        label="📅 From Date (Required)",
                        include_time=False,
                        info="Start date - REQUIRED",
                        elem_classes=["date-input"]
                    )

                    to_date_input_1 = gr.DateTime(
                        label="📅 To Date (Optional)",
                        include_time=False,
                        info="End date - defaults to today if empty",
                        elem_classes=["date-input"]
                    )

                    limit_input_1 = gr.Number(
                        label="📊 Limit",
                        value=None,
                        # minimum=1,
                        # maximum=1000,
                        step=1,
                        info="Number of records to fetch"
                    )
                    
                    fetch_btn_1 = gr.Button("🚀 Fetch Data", variant="primary", size="lg")
                
                with gr.Column(scale=3):
                    gr.Markdown("### 📋 Results")
                    status_output_1 = gr.Textbox(
                        label="Status",
                        interactive=False,
                        lines=1,
                        elem_classes=["status-output"]
                    )
                    # results_chart_1 = gr.Plot(
                    #     label="Top Parts Chart"
                    # )
                    results_table_1 = gr.Dataframe(
                        headers=["Part Name", "Claim Count", "Total Qty"],
                        datatype=["str", "number", "number"],
                        label="Top Parts — Claim Count and Total Qty",
                        interactive=False,
                    )
            
            # Connect the button to the function
            fetch_btn_1.click(
                fn=fetch_top_parts,
                inputs=[limit_input_1, from_date_input_1, to_date_input_1],
                outputs=[status_output_1, results_table_1]
            )
            
            # Also trigger on Enter key for limit input
            limit_input_1.submit(
                fn=fetch_top_parts,
                inputs=[limit_input_1, from_date_input_1, to_date_input_1],
                outputs=[status_output_1, results_table_1]
            )
        
        # Tab 2: Top Parts by Bike Model
        with gr.TabItem("🏍️ By Bike Model"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Query Parameters")

                    from_date_input_2 = gr.DateTime(
                        label="📅 From Date (Required)",
                        include_time=False,
                        info="Start date - REQUIRED",
                        elem_classes=["date-input"]
                    )

                    to_date_input_2 = gr.DateTime(
                        label="📅 To Date (Optional)",
                        include_time=False,
                        info="End date - defaults to today if empty",
                        elem_classes=["date-input"]
                    )

                    limit_input_2 = gr.Number(
                        label="📊 Limit (optional)",
                        value=None,
                        step=1,
                        info="Number of records to fetch (leave empty for default)"
                    )

                    bike_model_choices = get_bike_model_choices()
                    bike_dropdown = gr.Dropdown(
                        choices=bike_model_choices,
                        value=bike_model_choices[0] if bike_model_choices else None,
                        label="🏍️ Select Bike Model",
                        info="Type to filter bikes",
                        interactive=True,
                        filterable=True,
                        elem_id="bike-model-dropdown"
                    )
                    # gr.Markdown(
                    #     f"Loaded **{len(bike_model_choices)}** bike models from `app/config/bike_model_groups.json`."
                    #     if bike_model_choices
                    #     else f"⚠️ No bike models loaded from `{BIKE_MODEL_GROUPS_PATH}` (check server logs)."
                    # )
                    
                    fetch_btn_2 = gr.Button("🚀 Fetch Data", variant="primary", size="lg")
                
                with gr.Column(scale=3):
                    gr.Markdown("### 📊 Visualization")
                    status_output_2 = gr.Textbox(
                        label="Status",
                        interactive=False,
                        lines=1,
                        elem_classes=["status-output"]
                    )
                    results_chart_2 = gr.Plot(
                        label="Top Parts by Bike Model Chart"
                    )
            
            # Connect the button to the function
            fetch_btn_2.click(
                fn=fetch_parts_for_bike_model,
                inputs=[limit_input_2, bike_dropdown, from_date_input_2, to_date_input_2],
                outputs=[results_chart_2, status_output_2]
            )
            
            # Also trigger on Enter key for limit input
            limit_input_2.submit(
                fn=fetch_parts_for_bike_model,
                inputs=[limit_input_2, bike_dropdown, from_date_input_2, to_date_input_2],
                outputs=[results_chart_2, status_output_2]
            )

        # Tab 3: Failure Ratio by Bike Model
        with gr.TabItem("📉 Failure Ratio"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Query Parameters")

                    # limit_input_3 = gr.Number(
                    #     label="📊 Limit (optional)",
                    #     value=None,
                    #     step=1,
                    #     info="Number of bike models to fetch (leave empty for default)",
                    # )

                    fetch_btn_3 = gr.Button("🚀 Fetch Data", variant="primary", size="lg")

                with gr.Column(scale=3):
                    gr.Markdown("### 📊 Visualization")
                    status_output_3 = gr.Textbox(
                        label="Status",
                        interactive=False,
                        lines=1,
                        elem_classes=["status-output"],
                    )
                    results_chart_3 = gr.Plot(label="Failure Ratio by Bike Model")

            fetch_btn_3.click(
                fn=fetch_failure_ratio,
                inputs=[],
                outputs=[results_chart_3, status_output_3],
            )

            # limit_input_3.submit(
            #     fn=fetch_failure_ratio,
            #     inputs=[limit_input_3],
            #     outputs=[results_chart_3, status_output_3],
            # )

        # Tab 4: Prediction Dashboard (6 Months)
        with gr.TabItem("🔮 Prediction (6 Months)"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Actions")
                    top_n_parts_input = gr.Number(
                        label="🔢 Top N Parts (Prediction)",
                        value=10,
                        step=1,
                        info="Number of parts to show in the bar chart",
                    )
                    fetch_btn_4 = gr.Button("🚀 Fetch Predictions", variant="primary", size="lg")

                with gr.Column(scale=3):
                    gr.Markdown("### 📊 Visualization")
                    status_output_4 = gr.Textbox(
                        label="Status",
                        interactive=False,
                        lines=1,
                        elem_classes=["status-output"],
                    )
                    prediction_line_chart = gr.Plot(label="Forecast (Historical + Predicted)")

                    with gr.Row():
                        prediction_bar_chart = gr.Plot(label="Top Predicted Parts")
                        prediction_pie_chart = gr.Plot(label="Bike Model Share")

            fetch_btn_4.click(
                fn=fetch_prediction_dashboard,
                inputs=[top_n_parts_input],
                outputs=[prediction_line_chart, prediction_bar_chart, prediction_pie_chart, status_output_4],
            )


if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=9002,
        share=False,
        show_error=True,
        css=custom_css,
        theme=gr.themes.Soft(primary_hue="sky", neutral_hue="slate").set(
            body_background_fill="white",
            body_background_fill_dark="white",
            block_background_fill="#f8fafc",
            block_background_fill_dark="#f8fafc",
        )
    )
