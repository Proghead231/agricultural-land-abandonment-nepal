from retry import retry
import ee
ee.Initialize(project="ee-joshisur231", opt_url='https://earthengine-highvolume.googleapis.com')
import geemap
from multiprocessing.dummy import Pool as ThreadPool
import logging
import time
from datetime import datetime
import os
from colorama import Fore, Back, Style
import re
import config
import utils

# Globals
OUTPUT_DIR = r"outputs/new_output/point_timeseries_batches"
os.makedirs(OUTPUT_DIR, exist_ok=True)

grid_fc = ee.FeatureCollection("projects/ee-joshisur231/assets/grids_nepal_5000m")

def apply_spatial_thinning(points, distance_meters):
    points_with_random = points.randomColumn('random')
    dist_filter = ee.Filter.withinDistance(distance=distance_meters, leftField='.geo', rightField='.geo', maxError=10)
    join = ee.Join.saveAll(matchesKey='neighbors', measureKey='distance')
    joined_points = join.apply(points_with_random, points_with_random, dist_filter)

    def check_if_max(feature):
        neighbors = ee.List(feature.get('neighbors'))
        neighbor_randoms = neighbors.map(lambda f: ee.Feature(f).get('random'))
        max_random = neighbor_randoms.reduce(ee.Reducer.max())
        is_max = ee.Number(feature.get('random')).eq(max_random)
        return feature.set('keep', is_max)

    thinned_points = joined_points.map(check_if_max).filter(ee.Filter.eq('keep', 1))

    def cleanup(f):
        return f.set('keep', None).set('neighbors', None).set('random', None)
        
    return thinned_points.map(cleanup)


dem = ee.Image("USGS/SRTMGL1_003")
geo_region = ee.Image("projects/ee-joshisur231/assets/pa_effectiveness/geoReg_nepal").rename("geoReg")
slope_mask = ee.Terrain.slope(dem).lte(30)

frtc_lc_ic = ee.ImageCollection("projects/ee-joshisur231/assets/landcover_frtc_2000-2022_nepal")
frtc_ag_ic = frtc_lc_ic.map(lambda image: image.eq(7).rename("ag"))
frtc_stable_ag_mask = frtc_ag_ic.sum().eq(22)

stable_ag_mask = frtc_stable_ag_mask.updateMask(slope_mask) #Using Frtc only because sample of combined approach did not represent hilly areas adequately
stable_ag_eroded_mask = stable_ag_mask.focalMin(radius=2, units='pixels') #Removing ag field boundary by 2 pixel
patch_size = stable_ag_eroded_mask.connectedPixelCount(maxSize=10, eightConnected=True)
stable_ag_final_mask = stable_ag_eroded_mask.updateMask(patch_size.gte(10))

start_date, end_date = "2000-01-01", "2022-12-31"
landsat_ndvi_col = ee.ImageCollection("LANDSAT/COMPOSITES/C02/T1_L2_8DAY_NDVI").filterDate(start_date, end_date)

@retry(tries=1, delay=1, backoff=2)
def process_grid(grid_id):
    csv_path = os.path.join(OUTPUT_DIR, f"grid_{grid_id:04d}.csv")
    if os.path.exists(csv_path):
        print(Fore.YELLOW + f"Skipping grid {grid_id}, already exists.")
        return

    try:
        grid_geom = grid_fc.filter(ee.Filter.eq("grid_id", grid_id)).first().geometry()
        grid_points = stable_ag_final_mask.selfMask().rename('ag').stratifiedSample(
            numPoints=35,     
            classBand='ag', 
            region=grid_geom, 
            scale=30, 
            geometries=True,
            dropNulls=True
        )

        grid_points_thinned = apply_spatial_thinning(grid_points, 2000)\
                    .map(lambda feat: feat.set(
                        "point_id", 
                        ee.String(str(grid_id)).cat("_").cat(ee.String(feat.id()))
                    ))

        grid_points_with_geoReg = geo_region.sampleRegions(collection = grid_points_thinned, scale = 1000, projection="EPSG:32645", geometries=True)
        
        def extract_values(image):
            img_with_time = image.addBands(image.metadata("system:time_start").rename("time"))
            return img_with_time.sampleRegions(
                collection=grid_points_with_geoReg,
                scale=30,
                geometries=True,
                tileScale=4
            )
        grid_points_with_ndvi = landsat_ndvi_col.filterBounds(grid_geom).map(extract_values).flatten()
        
        print(Fore.BLUE + f"Starting for Grid {grid_id}" + Style.RESET_ALL)
        geemap.ee_export_vector(grid_points_with_ndvi, csv_path, verbose=True)

        # task_name = f"Grid_{grid_id:04d}_NDVI_Extraction"
        # geemap.ee_export_vector_to_drive(
        #     collection=grid_points_with_ndvi, 
        #     description=task_name, 
        #     fileFormat='CSV', 
        #     folder="Nepal_NDVI_Grids"
        # )
        print(Fore.GREEN + f"Successfully downloaded Grid {grid_id}" + Style.RESET_ALL)
    
    except Exception as e:
        msg = str(e)
        if "empty" in msg.lower() or "no features" in msg.lower():
            print(Fore.YELLOW + f"Grid {grid_id} skipped: No stable agriculture found." + Style.RESET_ALL)
        else:
            with open("error_log.txt", "a") as log:
                log.write(f"Failed Grid {grid_id} | Error: {e}\n")
            print(Fore.RED + f"Failed Grid {grid_id}. Check error_log.txt" + Style.RESET_ALL)
            raise e

if __name__ == "__main__":
    start_time = time.time()
    logging.basicConfig()
    total_grids = 6312
    grid_ids_list = list(range(1, total_grids + 1))
    print(Back.BLUE + f"Starting parallel extraction across {len(grid_ids_list)} grids..." + Style.RESET_ALL)
    
    with ThreadPool(processes=32) as pool:
        pool.map(process_grid, grid_ids_list)

    end_time = time.time()
    print(Back.GREEN + f"All {len(grid_ids_list)} grids processed in {end_time - start_time:.2f} seconds" + Style.RESET_ALL)