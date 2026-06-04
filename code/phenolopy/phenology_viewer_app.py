import streamlit as st
import pandas as pd
import numpy as np
# from scipy.signal import savgol_filter, find_peaks
# import plotly.graph_objects as go
import ast
import ee
import geemap.foliumap as geemap 
import utils # Ensure your utils.py is in the same folder
import folium

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & EARTH ENGINE INIT
# ---------------------------------------------------------
st.set_page_config(page_title="Phenology Viewer", layout="wide")
st.title("🛰️ Dynamic Agricultural Phenology Viewer")

# Initialize Earth Engine
@st.cache_resource
def init_ee():
    try:
        ee.Initialize(project="ee-joshisur231")
    except Exception as e:
        ee.Authenticate()
        ee.Initialize(project="ee-joshisur231")
init_ee()

# ---------------------------------------------------------
# 2. HELPER FUNCTIONS
# ---------------------------------------------------------
def parse_coordinates(geo_val):
    """
    Safely extracts [lon, lat] exclusively from a list, tuple, 
    or a string representation of a list/tuple. 
    Strictly ignores dictionaries/GeoJSON.
    """
    try:
        # If it's a string, safely evaluate it into a python list/tuple
        if isinstance(geo_val, str):
            geo_val = geo_val.strip()
            # Ensure it looks like a list or tuple before evaluating
            if (geo_val.startswith('[') and geo_val.endswith(']')) or \
               (geo_val.startswith('(') and geo_val.endswith(')')):
                parsed = ast.literal_eval(geo_val)
            else:
                return None
        else:
            parsed = geo_val
            
        # Verify the parsed object is strictly a list or tuple with at least 2 numbers
        if isinstance(parsed, (list, tuple)) and len(parsed) >= 2:
            return [float(parsed[0]), float(parsed[1])]
            
    except Exception:
        pass
    
    return None

# ---------------------------------------------------------
# 3. SIDEBAR CONTROLS (Upload & Column Mapping)
# ---------------------------------------------------------
st.sidebar.header("1. Upload Data")
uploaded_file = st.sidebar.file_uploader("Upload Time-Series CSV", type=["csv"])

if uploaded_file:
    # Load the uploaded file
    df = pd.read_csv(uploaded_file)
    
    st.sidebar.header("2. Map Data Columns")
    # Setting index=None forces the dropdown to be empty by default
    id_col = st.sidebar.selectbox("Point ID Column:", df.columns, index=None, placeholder="Select ID Column...")
    geo_col = st.sidebar.selectbox("Coordinates Column (List/Tuple):", df.columns, index=None, placeholder="Select Coordinates...")
    # time_col = st.sidebar.selectbox("Time/Date Column:", df.columns, index=None, placeholder="Select Time Column...")
    # ndvi_col = st.sidebar.selectbox("NDVI/Index Column:", df.columns, index=None, placeholder="Select NDVI Column...")
    
    # Checkbox to handle Earth Engine's raw millisecond timestamps
    # is_ms = st.sidebar.checkbox("Time is in milliseconds?", value=True)

    # Halt the app until the user explicitly selects all 4 columns
    if not all([id_col, geo_col]):#, time_col, ndvi_col]):
        st.info("👈 Please map all data columns in the sidebar to proceed.")
        st.stop()

    st.sidebar.header("3. Select Point")
    # Get unique points and create the main selection dropdown
    available_points = df[id_col].unique()
    selected_point_id = st.sidebar.selectbox("Select Point to Analyze:", available_points)

    # ---------------------------------------------------------
    # 4. DATA PROCESSING FOR SELECTED POINT
    # ---------------------------------------------------------
    # Isolate the data for the selected point
    group = df[df[id_col] == selected_point_id].copy()
    
    # Process Dates
    # try:
    #     if is_ms:
    #         group["date"] = pd.to_datetime(group[time_col], unit="ms")
    #     else:
    #         group["date"] = pd.to_datetime(group[time_col])
    # except Exception as e:
    #     st.error(f"Error parsing dates: {e}. Please check your Time Column.")
    #     st.stop()

    # Extract Coordinates from the first row of this point's data
    raw_geo = group.iloc[0][geo_col]
    coords = parse_coordinates(raw_geo)
    
    if not coords:
        st.error(f"Could not parse coordinates from value: `{raw_geo}`.")
        st.warning("Ensure the column contains lists `[lon, lat]` or strings like `'[86.70, 27.49]'`. GeoJSON is not supported.")
        st.stop()

    # Create UI Columns for Map and Chart
    # col1, col2 = st.columns([1, 1])
    # col1 = st.columns([1])
    # ---------------------------------------------------------
    # 5. THE MAP (Left Column)
    # ---------------------------------------------------------
    # with col1:
    st.subheader(f"Landsat Annual Composites")
    
    ee_point = ee.FeatureCollection([ee.Feature(ee.Geometry.Point(coords), {"point_id": str(selected_point_id)})])
    Map = geemap.Map(center=[coords[1], coords[0]], zoom=14, basemap=None, plugin_Draw=False, Draw_export=False)
    
    # NEW: Toggle for composite mode
    composite_mode = st.radio(
        "🔍 Select Composite Mode:", 
        ["Median", "Greenest Pixel (Max NDVI)"], 
        horizontal=True
    )

    years_l7 = ee.List.sequence(2000, 2012)
    years_l8 = ee.List.sequence(2013, 2022)

    # Helper functions for NDVI calculation
    def add_ndvi_l7(img):
        return img.addBands(img.normalizedDifference(['SR_B4', 'SR_B3']).rename('NDVI'))

    def add_ndvi_l8(img):
        return img.addBands(img.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI'))

    def get_annual_image_l7(year):
        start_date = ee.Date.fromYMD(year, 1, 1)
        end_date = start_date.advance(1, 'year')
        
        col = utils.get_processed_landsat_collection(
            "LANDSAT/LE07/C02/T1_L2", ee_point, [start_date, end_date], 
            utils.mask_clouds_landsat75, utils.apply_scale_factors)
            
        # Apply the logic based on the Streamlit toggle
        if composite_mode == "Greenest Pixel (Max NDVI)":
            year_image = col.map(add_ndvi_l7).qualityMosaic('NDVI')\
                .select(["SR_B3", "SR_B2", "SR_B1"]).rename(["r", "g", "b"])
        else:
            year_image = col.median()\
                .select(["SR_B3", "SR_B2", "SR_B1"]).rename(["r", "g", "b"])
                
        return year_image.set("year", ee.String(ee.Number(year).int()))

    def get_annual_image_l8(year):
        start_date = ee.Date.fromYMD(year, 1, 1)
        end_date = start_date.advance(1, 'year')
        
        col = utils.get_processed_landsat_collection(
            "LANDSAT/LC08/C02/T1_L2", ee_point, [start_date, end_date], 
            utils.mask_clouds_landsat8, utils.apply_scale_factors)
            
        # Apply the logic based on the Streamlit toggle
        if composite_mode == "Greenest Pixel (Max NDVI)":
            year_image = col.map(add_ndvi_l8).qualityMosaic('NDVI')\
                .select(["SR_B4", "SR_B3", "SR_B2"]).rename(["r", "g", "b"])
        else:
            year_image = col.median()\
                .select(["SR_B4", "SR_B3", "SR_B2"]).rename(["r", "g", "b"])
                
        return year_image.set("year", ee.String(ee.Number(year).int()))

    images_2000_2012 = ee.ImageCollection(years_l7.map(get_annual_image_l7))
    images_2013_2022 = ee.ImageCollection(years_l8.map(get_annual_image_l8))
    images_2000_2022 = images_2000_2012.merge(images_2013_2022).sort("year").toList(23)

    vis_params_l = {'min': 0.0, 'max': 0.3, 'bands': ['r', 'g', 'b']}

    # ---------------------------------------------------------
    # NEW SLIDER LOGIC
    # ---------------------------------------------------------
    # Max value is 2018 because 2018 + 4 gives us the final year (2022)
    start_year = st.slider(
        "📅 Slide to load a 5-Year Window:", 
        min_value=2000, 
        max_value=2018, 
        value=2000, # Defaults to the most recent window (2018-2022)
        step=1
    )
    
    # Calculate the Earth Engine list index (2000 = index 0)
    start_idx = start_year - 2000

    with st.spinner(f'Loading Landsat layers for {start_year} - {start_year + 4}...'):
        
        # Loop exactly 5 times starting from the slider's index
        for i in range(start_idx, start_idx + 5): 
            
            # Cast i to int to ensure Earth Engine accepts it
            image = ee.Image(images_2000_2022.get(int(i)))
            year = image.get("year").getInfo()
            
            # Make ONLY the most recent year in the 5-year chunk visible by default
            is_visible = True if i == start_idx else False
            
            Map.addLayer(image, vis_params_l, str(year), is_visible)

        # Add the point, the layer control, and render the map
        Map.addLayer(ee_point, {'color': 'red'}, 'Selected Point')
        Map.addLayerControl() 
        Map.to_streamlit(height=600)

    # ---------------------------------------------------------
    # 6. THE CHART (Right Column)
    # ---------------------------------------------------------
    # with col2:
    #     st.subheader("Phenology Profile (2000-2022)")
        
    #     ts_raw = group.set_index('date')[ndvi_col].resample("16D").mean()
    #     total_valid_obs = ts_raw.count()

    #     if total_valid_obs < 200:
    #         st.error(f"DISCARDED: Insufficient valid observations ({total_valid_obs}/525). Try another point.")
    #     else:
    #         ts_interp = ts_raw.interpolate(method="linear").bfill().ffill()
    #         window = 11
    #         smoothed_ndvi = savgol_filter(ts_interp.values, window_length=window, polyorder=2)
            
    #         peaks, properties = find_peaks(
    #             smoothed_ndvi, height=0.35, distance=5, width=(5, 15), prominence=0.10
    #         )
    #         peak_dates = ts_interp.index[peaks]

    #         yearly_classification = {}
    #         for year in range(2000, 2023):
    #             year_mask = ts_interp.index.year == year
    #             smoothed_year = smoothed_ndvi[year_mask]

    #             if len(smoothed_year) == 0:
    #                 yearly_classification[year] = "insufficient_data"
    #                 continue
    #             peaks_in_year = (peak_dates.year == year).sum()
    #             yearly_classification[year] = "crop" if peaks_in_year >= 1 else "non_crop"
            
    #         total_non_crop = 0
    #         consecutive_non_crop = 0
    #         max_consecutive_non_crop = 0

    #         for year in range(2000, 2023):
    #             if yearly_classification.get(year) == "non_crop":
    #                 total_non_crop += 1
    #                 consecutive_non_crop += 1
    #                 if consecutive_non_crop > max_consecutive_non_crop:
    #                     max_consecutive_non_crop = consecutive_non_crop
    #             else:
    #                 consecutive_non_crop = 0
            
    #         status = "STABLE" if (total_non_crop < 4 and max_consecutive_non_crop < 2) else "DISCARDED"

    #         # Build Plotly Figure
    #         fig = go.Figure()
    #         fig.add_trace(go.Scatter(x=ts_raw.index, y=ts_raw.values, mode='markers', name='Raw', marker=dict(color='grey', opacity=0.5)))
    #         fig.add_trace(go.Scatter(x=ts_raw.index, y=ts_raw.values, mode='lines', name='Raw (Line)', line=dict(color='black', width=1, dash='dash'), opacity=0.6, showlegend=False))
    #         fig.add_trace(go.Scatter(x=ts_interp.index, y=smoothed_ndvi, mode='lines', name='Smoothed', line=dict(color='green', width=1.5), opacity=0.7))
            
    #         if len(peaks) > 0:
    #             fig.add_trace(go.Scatter(x=ts_interp.index[peaks], y=smoothed_ndvi[peaks], mode='markers', name='Peaks', marker=dict(symbol='x', color='red', size=10, line=dict(width=2, color='red'))))

    #         info_text = (
    #             f"Final Status: <b>{status}</b><br>"
    #             f"Total Non-Crop Years: {total_non_crop}<br>"
    #             f"Max Consecutive Non-Crop: {max_consecutive_non_crop}<br>"
    #             f"Total Peaks: {len(peaks)}"
    #         )

    #         fig.add_annotation(
    #             x=0.02, y=0.05, xref="paper", yref="paper", text=info_text, showarrow=False,
    #             align="left", bgcolor="rgba(255, 255, 255, 0.8)", bordercolor="gray", borderwidth=1,
    #             font=dict(size=12), xanchor="left", yanchor="bottom"
    #         )

    #         fig.update_layout(
    #             height=600, plot_bgcolor='white', margin=dict(t=10, b=10, l=10, r=10),
    #             yaxis=dict(range=[-0.1, 1.0], gridcolor='rgba(128,128,128,0.2)'),
    #             xaxis=dict(dtick="M12", tickformat="%Y", tickangle=45, gridcolor='rgba(128,128,128,0.2)'),
    #             legend=dict(x=0.99, y=0.99, xanchor="right", yanchor="top", bgcolor="rgba(255,255,255,0.7)")
    #         )

    #         st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Please upload a CSV file in the sidebar to begin.")