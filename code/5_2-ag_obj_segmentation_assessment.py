import os
os.environ["PROJ_LIB"] = r"E:\Software\conda_envs\gee\Library\share\proj"
os.environ["GDAL_DATA"] = r"E:\Software\conda_envs\gee\Library\share\gdal"
import glob
import pandas as pd
import geopandas as gpd
from libpysal.weights import Queen
from esda.moran import Moran_Local
import numpy as np
import concurrent.futures

geojson_dir = r"code\outputs\obia_results\parameter_tuning_inputs"
target_bands = ['blue_2002', 'green_2002', 'red_2002',  'nir_2002',  'swir1_2002', 'swir2_2002',
 'ndvi_2002', 'ndmi_2002', 'ndvi_shade_2002', 'ndvi_savg_2002', 
 'blue_2010', 'green_2010', 'red_2010', 'nir_2010', 'swir1_2010', 'swir2_2010',
 'ndvi_2010', 'ndmi_2010', 'ndvi_shade_2010', 'ndvi_savg_2010', 
 'blue_2017', 'green_2017', 'red_2017', 'nir_2017', 'swir1_2017', 'swir2_2017',
 'ndvi_2017', 'ndmi_2017', 'ndvi_shade_2017', 'ndvi_savg_2017', 
 'slope', 'northness', 'eastness']

def calculate_metrics(filepath):
    print(f"Reading {filepath}")
    gdf = gpd.read_file(filepath)

    if gdf.crs.to_epsg() != 32645:
        gdf = gdf.to_crs("EPSG:32645")
        
    if gdf.empty:
        return []
        
    gdf["area"] = gdf.geometry.area
    
    results_list = []
    if 'geoReg' not in gdf.columns:
        print(f"'geoReg' column not found in {filepath}")
        return []

    for geo_reg, group_gdf in gdf.groupby('geoReg'):
        group_gdf = group_gdf.reset_index(drop=True)
        if len(group_gdf) < 2:
            continue
            
        w = None
        try:
            temp_w = Queen.from_dataframe(group_gdf, use_index=False, silence_warnings=True)
            print(f"Islands found: {len(temp_w.islands)}")
            if temp_w.islands:
                non_islands = [i for i in range(len(group_gdf)) if i not in temp_w.islands]
                if len(non_islands) >= 2:
                    group_gdf = group_gdf.iloc[non_islands].reset_index(drop=True)
                    w = Queen.from_dataframe(group_gdf, use_index=False, silence_warnings=True)
            else:
                w = temp_w
                
            if w is not None:
                w.transform = "r"
        except Exception:
            w = None

        # if 'active_crop_mean' in group_gdf.columns:
        #     group_gdf_ag = group_gdf[group_gdf['active_crop_mean'] > 0.5].copy()
        # else:
        group_gdf_ag = group_gdf.copy()
            
        if group_gdf_ag.empty:
            continue

        alv_list = []
        mi_list = []
        for band in target_bands:
            mean_col = f"{band}_mean"
            var_col = f"{band}_variance"
            if mean_col not in group_gdf.columns or var_col not in group_gdf.columns:
                print(f"Band {mean_col} or {var_col} not found!")
                continue
            
            if np.sum(group_gdf_ag["area"]) > 0:
                alv_band = np.sum(group_gdf_ag[var_col] * group_gdf_ag["area"]) / np.sum(group_gdf_ag["area"])
                alv_list.append(alv_band)

            if w is not None:
                try:
                    m_local = Moran_Local(group_gdf[mean_col], w, permutations=0, n_jobs=-1)
                    ag_indices = group_gdf_ag.index
                    ag_local_mi = m_local.Is[ag_indices]
                    mi_list.append(np.nanmean(ag_local_mi))
                except Exception:
                    pass
            
        final_alv = np.nanmean(alv_list) if alv_list else np.nan
        final_mi = np.nanmean(mi_list) if mi_list else np.nan

        results_list.append({
            "filename": os.path.basename(filepath),
            "geoReg": geo_reg,
            "ALV": final_alv,
            "MoranI": final_mi
        })

    return results_list

def main():
    results = []
    file_list = glob.glob(os.path.join(geojson_dir, "*.geojson"))
    
    with concurrent.futures.ProcessPoolExecutor() as executor:
        for metrics_list in executor.map(calculate_metrics, file_list):
            if metrics_list:
                results.extend(metrics_list)
                
    if not results:
        print("No results generated.")
        return
    
    df = pd.DataFrame(results)
    
    final_dfs = []
    for geo_reg, group in df.groupby('geoReg'):
        group = group.copy()
        
        alv_min, alv_max = group['ALV'].min(), group['ALV'].max()
        if alv_max != alv_min and not pd.isna(alv_min):
            group['ALV_norm'] = (group['ALV'] - alv_min) / (alv_max - alv_min)
        else:
            group['ALV_norm'] = 0.0
            
        mi_min, mi_max = group['MoranI'].min(), group['MoranI'].max()
        if mi_max != mi_min and not pd.isna(mi_min):
            group['MoranI_norm'] = (group['MoranI'] - mi_min) / (mi_max - mi_min)
        else:
            group['MoranI_norm'] = 0.0
            
        group['Global_Score'] = group['ALV_norm'] + group['MoranI_norm']
        group = group.sort_values(by='Global_Score', ascending=True).reset_index(drop=True)
        
        print(f"\n--- TOP 5 OPTIMAL PARAMETER SETS FOR {geo_reg} ---")
        print(group[['filename', 'ALV', 'MoranI', 'Global_Score']].head(5))
        final_dfs.append(group)
        
    final_df = pd.concat(final_dfs, ignore_index=True)
    os.makedirs(r"code\outputs\obia_results", exist_ok=True)
    final_df.to_csv(r"code\outputs\obia_results\seg_optimization_results2_without_crop_filtering.csv", index=False)
    print("Done!")

if __name__ == "__main__":
    main()
