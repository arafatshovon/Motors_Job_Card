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
    
    labels = df[label_col].astype(str).tolist() if label_col else df.index.astype(str).tolist()
    values = df[value_col].tolist()
    bar_text = [str(v) for v in values]  # Display claimcount values on bars
    partcodes = df[code_col].astype(str).tolist() if code_col else labels  # For hover
    
    # Reverse for horizontal bar chart (top to bottom display)
    labels = labels[::-1]
    values = values[::-1]
    bar_text = bar_text[::-1]
    partcodes = partcodes[::-1]
    
    # Color palette for different partcodes
    color_palette = [
        '#4ade80',  # Green
        '#f472b6',  # Pink
        '#60a5fa',  # Blue
        '#fbbf24',  # Yellow
        '#a78bfa',  # Purple
        '#fb923c',  # Orange
        '#2dd4bf',  # Teal
        '#f87171',  # Red
        '#34d399',  # Emerald
        '#818cf8',  # Indigo
        '#e879f9',  # Fuchsia
        '#38bdf8',  # Sky
        '#facc15',  # Amber
        '#4ade80',  # Lime
        '#f97316',  # Deep Orange
        '#c084fc',  # Violet
        '#22d3ee',  # Cyan
        '#fb7185',  # Rose
        '#a3e635',  # Lime Green
        '#fcd34d',  # Gold
    ]
    
    # Assign colors based on partcode
    unique_codes = list(dict.fromkeys(partcodes))  # Preserve order, remove duplicates
    code_to_color = {code: color_palette[i % len(color_palette)] for i, code in enumerate(unique_codes)}
    bar_colors = [code_to_color[code] for code in partcodes]
    
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
        textfont=dict(color='#0f172a', size=12, family='Outfit, sans-serif'),
        customdata=partcodes,
        hovertemplate='<b>Partcode: %{customdata}</b><br>Claim Count: %{x}<extra></extra>'
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


def fetch_top_parts(limit: int, months: int, years: int):
    """Fetch top warranty parts from the API."""
    try:
        params = {
            "limit": int(limit),
            "months": int(months),
            "years": int(years)
        }
        
        response = requests.get(API_URL_TOP_PARTS, params=params, timeout=30)
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
        
        # Create the chart
        fig = create_bar_chart(df, "Warranty Exposure Dashboard")
        
        return fig, f"✅ Successfully fetched {len(df)} records"
        
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


def fetch_parts_by_bike_model(limit, months, years, bike_model: str):
    """Fetch top warranty parts for a specific bike model from the API."""
    try:
        # Check if bike_model is provided (required)
        if not bike_model:
            fig = create_bar_chart(pd.DataFrame())
            return fig, "⚠️ Please select a bike model first"
        
        # Start with required parameter
        params = {"bike_model": bike_model.strip()}
        
        # Add optional parameters only if they have valid values (not None, not empty, not 0)
        if limit is not None and limit != "" and limit > 0:
            params["limit"] = int(limit)
        if months is not None and months != "" and months > 0:
            params["months"] = int(months)
        if years is not None and years != "" and years > 0:
            params["years"] = int(years)
        
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
        
        return fig, f"✅ Successfully fetched {len(df)} records for {bike_model}"
        
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
}

.gradio-container {
    font-family: 'Outfit', sans-serif !important;
    background: #ffffff !important;
    min-height: 100vh;
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

.gr-input, .gr-number input, .gr-textbox input {
    background: #ffffff !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 8px !important;
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
                    
                    limit_input_1 = gr.Number(
                        label="📊 Limit",
                        value=10,
                        minimum=1,
                        maximum=1000,
                        step=1,
                        info="Number of records to fetch"
                    )
                    
                    months_input_1 = gr.Number(
                        label="📅 Months",
                        value=1,
                        minimum=1,
                        maximum=12,
                        step=1,
                        info="Month filter (1-12)"
                    )
                    
                    years_input_1 = gr.Number(
                        label="📆 Last X Years (example: 1)",
                        value=1,
                        minimum=1,
                        maximum=200,
                        step=1,
                        info="Year filter"
                    )
                    
                    fetch_btn_1 = gr.Button("🚀 Fetch Data", variant="primary", size="lg")
                
                with gr.Column(scale=3):
                    gr.Markdown("### 📊 Visualization")
                    status_output_1 = gr.Textbox(
                        label="Status",
                        interactive=False,
                        lines=1
                    )
                    results_chart_1 = gr.Plot(
                        label="Top Parts Chart"
                    )
            
            # Connect the button to the function
            fetch_btn_1.click(
                fn=fetch_top_parts,
                inputs=[limit_input_1, months_input_1, years_input_1],
                outputs=[results_chart_1, status_output_1]
            )
            
            # Also trigger on Enter key for any input
            for input_component in [limit_input_1, months_input_1, years_input_1]:
                input_component.submit(
                    fn=fetch_top_parts,
                    inputs=[limit_input_1, months_input_1, years_input_1],
                    outputs=[results_chart_1, status_output_1]
                )
        
        # Tab 2: Top Parts by Bike Model
        with gr.TabItem("🏍️ By Bike Model"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Query Parameters")
                    
                    limit_input_2 = gr.Number(
                        label="📊 Limit (optional)",
                        value=None,
                        step=1,
                        info="Number of records to fetch (leave empty for default)"
                    )
                    
                    months_input_2 = gr.Number(
                        label="📅 Months (optional)",
                        value=None,
                        step=1,
                        info="Month filter 1-12 (leave empty for default)"
                    )
                    
                    years_input_2 = gr.Number(
                        label="📆 Years (optional)",
                        value=None,
                        step=1,
                        info="Last X years (leave empty for default)"
                    )
                    
                    bike_dropdown = gr.Dropdown(
                        choices=ALL_BIKE_NAMES,
                        label="🏍️ Select Bike Model",
                        info="Type to filter bikes",
                        interactive=True,
                        filterable=True
                    )
                    
                    fetch_btn_2 = gr.Button("🚀 Fetch Data", variant="primary", size="lg")
                
                with gr.Column(scale=3):
                    gr.Markdown("### 📊 Visualization")
                    status_output_2 = gr.Textbox(
                        label="Status",
                        interactive=False,
                        lines=1
                    )
                    results_chart_2 = gr.Plot(
                        label="Top Parts by Bike Model Chart"
                    )
            
            # Connect the button to the function
            fetch_btn_2.click(
                fn=fetch_parts_by_bike_model,
                inputs=[limit_input_2, months_input_2, years_input_2, bike_dropdown],
                outputs=[results_chart_2, status_output_2]
            )
            
            # Also trigger on Enter key for number inputs
            for input_component in [limit_input_2, months_input_2, years_input_2]:
                input_component.submit(
                    fn=fetch_parts_by_bike_model,
                    inputs=[limit_input_2, months_input_2, years_input_2, bike_dropdown],
                    outputs=[results_chart_2, status_output_2]
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
