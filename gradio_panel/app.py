import gradio as gr
import requests
import pandas as pd
import plotly.graph_objects as go
import os


API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = os.environ.get("API_PORT", "9001")
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"

API_URL_TOP_PARTS = f"{API_BASE_URL}/api/warranty/top-parts"
API_URL_BIKE_MODEL = f"{API_BASE_URL}/api/warranty/top-parts/for-bike-model"
API_URL_FAILURE_RATIO = f"{API_BASE_URL}/api/warranty/failure-ratio/by-bike-model"
API_URL_BIKE_NAMES = f"{API_BASE_URL}/api/bikes/names"

# API_URL_TOP_PARTS = "http://0.0.0.0:9001/api/warranty/top-parts"
# API_URL_BIKE_MODEL = "http://0.0.0.0:9001/api/warranty/top-parts/for-bike-model"
# API_URL_BIKE_NAMES = "http://0.0.0.0:9001/api/bikes/names"

# Global list to store all bike names (fetched once at startup)
ALL_BIKE_NAMES = []


def fetch_all_bikes():
    """Fetch all bike names from API once at startup."""
    global ALL_BIKE_NAMES
    try:
        print("Fetching all bike names from API...")
        response = requests.get(API_URL_BIKE_NAMES, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        bike_names = []
        
        # Handle different response formats
        if isinstance(data, list):
            if data and isinstance(data[0], str):
                bike_names = data
            elif data and isinstance(data[0], dict):
                for field in ['bikeName', 'bike_name', 'name', 'model', 'title']:
                    if field in data[0]:
                        bike_names = [str(item[field]) for item in data if field in item]
                        break
        elif isinstance(data, dict):
            if data.get("ret") == True and "data" in data:
                inner_data = data["data"]
                if isinstance(inner_data, list):
                    if inner_data and isinstance(inner_data[0], str):
                        bike_names = inner_data
                    elif inner_data and isinstance(inner_data[0], dict):
                        for field in ['bikeName', 'bike_name', 'name', 'model']:
                            if field in inner_data[0]:
                                bike_names = [str(item[field]) for item in inner_data if field in item]
                                break
                elif isinstance(inner_data, dict) and "items" in inner_data:
                    items = inner_data["items"]
                    for field in ['bikeName', 'bike_name', 'name', 'model']:
                        if items and field in items[0]:
                            bike_names = [str(item[field]) for item in items if field in item]
                            break
            else:
                for key in ["data", "results", "items", "names", "bikes"]:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        if items and isinstance(items[0], str):
                            bike_names = items
                        elif items and isinstance(items[0], dict):
                            for field in ['bikeName', 'bike_name', 'name', 'model']:
                                if field in items[0]:
                                    bike_names = [str(item[field]) for item in items if field in item]
                                    break
                        break
        
        ALL_BIKE_NAMES = bike_names
        print(f"✅ Loaded {len(ALL_BIKE_NAMES)} bike names")
        return ALL_BIKE_NAMES
        
    except Exception as e:
        print(f"❌ Error fetching bike names: {e}")
        return []


# Fetch all bikes at startup with delay for Docker (API needs time to start)
import time
print("Waiting for API to be ready...")
time.sleep(5)  # Wait 5 seconds for API to be ready

# Try to fetch with retries
for attempt in range(3):
    result = fetch_all_bikes()
    if result:
        break
    print(f"Retry {attempt + 1}/3...")
    time.sleep(2)


def search_bikes(query: str):
    """Filter bikes locally from pre-loaded list."""
    if not query or len(query.strip()) < 2:
        return gr.update(choices=[])
    
    # Fast local search using pre-loaded list
    query_lower = query.strip().lower()
    
    # Use generator for faster filtering, limit early
    count = 0
    filtered_names = []
    for name in ALL_BIKE_NAMES:
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

    # If we have both a label and a code column, aggregate total claim count per label (part name)
    # and keep a comma-separated list of unique part codes for hover.
    if label_col and code_col and label_col != code_col:
        agg = (
            work_df.groupby(label_col, as_index=False)
            .agg(
                **{
                    value_col: (value_col, "sum"),
                    "__partcodes": (code_col, lambda s: ", ".join(dict.fromkeys([x for x in s.tolist() if x]))),
                }
            )
        )
        work_df = agg
        code_col = "__partcodes"

    # Sort by total claim count (descending); we will reverse later for horizontal top-to-bottom display
    work_df = work_df.sort_values(by=value_col, ascending=False)

    labels = work_df[label_col].astype(str).tolist() if label_col else work_df.index.astype(str).tolist()
    values = work_df[value_col].tolist()
    bar_text = [str(int(v)) if float(v).is_integer() else str(v) for v in values]  # Display values on bars
    partcodes = work_df[code_col].astype(str).tolist() if code_col else labels  # For hover
    
    # Reverse for horizontal bar chart (top to bottom display)
    labels = labels[::-1]
    values = values[::-1]
    bar_text = bar_text[::-1]
    partcodes = partcodes[::-1]
    
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
        customdata=partcodes,
        hovertemplate='<b>Partcode(s): %{customdata}</b><br>Total Claim Count: %{x}<extra></extra>'
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


def fetch_top_parts(limit, from_date, to_date):
    """Fetch top warranty parts from the API."""
    try:
        # Convert dates to string format YYYY-MM-DD
        from_date_str = convert_date_to_string(from_date)
        to_date_str = convert_date_to_string(to_date)
        print(from_date_str,type(from_date_str))
        print(to_date_str,type(to_date_str))
        # from_date is REQUIRED by the API
        if not from_date_str:
            fig = create_bar_chart(pd.DataFrame())
            return fig, "⚠️ Please select a From Date (required)"
        
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
        
        # Create the chart
        fig = create_bar_chart(df, "Warranty Exposure Dashboard")
        
        return fig, f"✅ Top {len(df)} Warranty Claimed Parts"
        
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


def fetch_parts_by_bike_model(limit, bike_model: str, from_date, to_date):
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
        
        # Start with required parameter
        params = {"bike_model": bike_model.strip()}
        
        # Add optional parameters only if they have valid values (not None, not empty, not 0)
        if limit is not None and limit != "" and limit != 0:
            params["limit"] = int(limit)

        # Add dates as strings (YYYY-MM-DD format)
        params["from_date"] = from_date_str

        # to_date is optional (API defaults to today)
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
        
        # Create the chart with bike model in title
        chart_title = f"Top Parts for {bike_model}" if bike_model else "Top Parts by Bike Model"
        fig = create_bar_chart(df, chart_title)
        
        return fig, f"✅ Top {len(df)} Warranty ClaimedParts for {bike_model}"
        
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
    for col in ["bikeName", "bikeCode", "totalBikeSold", "totalPartsClaimed", "partsFailureRatio"]:
        if col not in work_df.columns:
            # Allow some flexibility if keys differ
            alt = next((c for c in work_df.columns if c.lower() == col.lower()), None)
            if alt:
                work_df[col] = work_df[alt]

    if "partsFailureRatio" not in work_df.columns or "bikeName" not in work_df.columns:
        return create_bar_chart(df, title)

    work_df["partsFailureRatio"] = pd.to_numeric(work_df["partsFailureRatio"], errors="coerce").fillna(0.0)
    work_df["totalBikeSold"] = pd.to_numeric(work_df.get("totalBikeSold", 0), errors="coerce").fillna(0).astype(int)
    work_df["totalPartsClaimed"] = (
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
    claimed = work_df.get("totalPartsClaimed", pd.Series([0] * len(work_df))).astype(int).tolist()[::-1]

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

    customdata = list(zip(bike_codes, sold, claimed))

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
                "Total Parts Claimed: %{customdata[2]}<extra></extra>"
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


def fetch_failure_ratio(limit):
    """Fetch bike model failure ratios from the API."""
    try:
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

        fig = create_failure_ratio_chart(df, "Bike Model Failure Ratio (Parts Claimed / Bikes Sold)")
        return fig, f"✅ Loaded {len(df)} bike models"

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
                    gr.Markdown("### 📊 Visualization")
                    status_output_1 = gr.Textbox(
                        label="Status",
                        interactive=False,
                        lines=1,
                        elem_classes=["status-output"]
                    )
                    results_chart_1 = gr.Plot(
                        label="Top Parts Chart"
                    )
            
            # Connect the button to the function
            fetch_btn_1.click(
                fn=fetch_top_parts,
                inputs=[limit_input_1, from_date_input_1, to_date_input_1],
                outputs=[results_chart_1, status_output_1]
            )
            
            # Also trigger on Enter key for limit input
            limit_input_1.submit(
                fn=fetch_top_parts,
                inputs=[limit_input_1, from_date_input_1, to_date_input_1],
                outputs=[results_chart_1, status_output_1]
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

                    bike_dropdown = gr.Dropdown(
                        choices=ALL_BIKE_NAMES,
                        label="🏍️ Select Bike Model",
                        info="Type to filter bikes",
                        interactive=True,
                        filterable=True,
                        elem_id="bike-model-dropdown"
                    )
                    
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
                fn=fetch_parts_by_bike_model,
                inputs=[limit_input_2, bike_dropdown, from_date_input_2, to_date_input_2],
                outputs=[results_chart_2, status_output_2]
            )
            
            # Also trigger on Enter key for limit input
            limit_input_2.submit(
                fn=fetch_parts_by_bike_model,
                inputs=[limit_input_2, bike_dropdown, from_date_input_2, to_date_input_2],
                outputs=[results_chart_2, status_output_2]
            )

        # Tab 3: Failure Ratio by Bike Model
        with gr.TabItem("📉 Failure Ratio"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Query Parameters")

                    limit_input_3 = gr.Number(
                        label="📊 Limit (optional)",
                        value=None,
                        step=1,
                        info="Number of bike models to fetch (leave empty for default)",
                    )

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
                inputs=[limit_input_3],
                outputs=[results_chart_3, status_output_3],
            )

            limit_input_3.submit(
                fn=fetch_failure_ratio,
                inputs=[limit_input_3],
                outputs=[results_chart_3, status_output_3],
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
