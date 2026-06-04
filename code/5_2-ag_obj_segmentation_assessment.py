import os
os.environ["PROJ_LIB"] = r"E:\Software\conda_envs\gee\Library\share\proj"
os.environ["GDAL_DATA"] = r"E:\Software\conda_envs\gee\Library\share\gdal"
import glob
import pandas as pd
import geopandas as gpd
from libpysal.weights import Queen
from esda.moran import Moran
import numpy as np
import concurrent.futures

geojson_dir = r"code\outputs\obia_results"
target_bands = ['g_2000', 'g_2010',  'g_2020', 'r_2000', 'r_2010', 'r_2020','nir_2000', 'nir_2010', 'nir_2020',
 'nir_savg_2000', 'nir_savg_2010', 'nir_savg_2020', 'nir_shade_2000', 'nir_shade_2010', 'nir_shade_2020',
 'swir1_2000', 'swir1_2010', 'swir1_2020', 'swir2_2000', 'swir2_2010', 'swir2_2020',
 'ndvi_2000', 'ndvi_2010', 'ndvi_2020', 
 'eastness_2000', 'northness_2000', 'slope_2000']

def calculate_metrics(filepath):
    gdf = gpd.read_file(filepath)

    if gdf.crs.to_epsg() != 32645:
        gdf = gdf.to_crs("EPSG:32645")
    gdf["area"] = gdf.geometry.area
    
    w = Queen.from_dataframe(gdf, use_index=False, silence_warnings=True)
    w.transform = "r"

    alv_list = []
    mi_list = []
    for band in target_bands:
        mean_col = f"{band}_mean"
        var_col = f"{band}_variance"
        if mean_col not in gdf.columns or var_col not in gdf.columns:
            print(f"{mean_col}/{var_col} not in the df")
            continue
        
        alv_band = np.sum(gdf[var_col] * gdf["area"]) / np.sum(gdf["area"])
        alv_list.append(alv_band)

        mi_band = Moran(gdf[mean_col], w).I
        mi_list.append(mi_band)
        
    final_alv = np.nanmean(alv_list)
    final_mi = np.nanmean(mi_list)

    return {
        "filename": os.path.basename(filepath),
        "ALV": final_alv,
        "MoranI": final_mi
    }

def main():
    results = []
    file_list = glob.glob(os.path.join(geojson_dir, "*.geojson"))
    if len(file_list) != 80:
        print(f"Something is wrong! There are only {len(file_list)} geojson files found in the directory.")
    
    with concurrent.futures.ProcessPoolExecutor() as executor:
        for metrics in executor.map(calculate_metrics, file_list):
            results.append(metrics)
    
    df = pd.DataFrame(results)
    
    df['ALV_norm'] = (df['ALV'] - df['ALV'].min()) / (df['ALV'].max() - df['ALV'].min())
    df['MoranI_norm'] = (df['MoranI'] - df['MoranI'].min()) / (df['MoranI'].max() - df['MoranI'].min())
    df['Global_Score'] = df['ALV_norm'] + df['MoranI_norm']
    df = df.sort_values(by='Global_Score', ascending=True).reset_index(drop=True)
    
    print("\n--- TOP 5 OPTIMAL PARAMETER SETS ---")
    print(df[['filename', 'ALV', 'MoranI', 'Global_Score']].head(5))
    os.makedirs(r"code\outputs\obia_results", exist_ok=True)
    df.to_csv(r"code\outputs\obia_results\yin_esp_optimization_results.csv", index=False)
    print("Done!")

if __name__ == "__main__":
    main()

