import ee
import numpy as np
ee.Initialize(project = "ee-joshisur231")
print("loaded utils!")
def mask_clouds_landsat75(image):
  dilatedCloudBitMask = (1 << 1)
  cloudBitMask = (1 << 3)
  cloudShadowBitMask = (1 << 4)
  snowBitMask = (1 << 5)
  
  qa = image.select('QA_PIXEL')

  mask = qa.bitwiseAnd(dilatedCloudBitMask).eq(0)\
    .And(qa.bitwiseAnd(cloudBitMask).eq(0))\
    .And(qa.bitwiseAnd(cloudShadowBitMask).eq(0))\
    .And(qa.bitwiseAnd(snowBitMask).eq(0))

  return image.updateMask(mask)

def mask_clouds_landsat8(image):
  dilatedCloudBitMask = (1 << 1)
  cirrusBitMask = (1 << 2)
  cloudBitMask = (1 << 3)
  cloudShadowBitMask = (1 << 4)
  snowBitMask = (1 << 5)

  qa = image.select('QA_PIXEL')

  mask = qa.bitwiseAnd(dilatedCloudBitMask).eq(0)\
    .And(qa.bitwiseAnd(cirrusBitMask).eq(0))\
    .And(qa.bitwiseAnd(cloudBitMask).eq(0))\
    .And(qa.bitwiseAnd(cloudShadowBitMask).eq(0))\
    .And(qa.bitwiseAnd(snowBitMask).eq(0))

  return image.updateMask(mask)

def apply_scale_factors(image):
  optical_bands = image.select('SR_B.').multiply(0.0000275).add(-0.2)
  # thermalBand = image.select('ST_B6').multiply(0.00341802).add(149.0) #dont need thermal
  
  return image.addBands(optical_bands, None, True)#.addBands(thermalBand, None, True)

def get_processed_landsat_collection(col_id, roi, date_range, cmask_func, scale_func):
    '''
    Preprocess landsat SR collection
    
    Args:
        col_id: landsat SR collection id
        roi: region of interest
        date_range: [start_date, end_date]
        cmask_func: cloud masking function (optional)
        scale_func: values scaling function
    
    Returns:
        pre-processed landsat collection
    '''
    return ee.ImageCollection(col_id)\
        .filterBounds(roi)\
        .filterDate(date_range[0], date_range[1])\
        .map(cmask_func)\
        .map(scale_func)

def scale_image01(image, roi, scale):
    minMax_values = image.reduceRegion(reducer = ee.Reducer.minMax(), geometry = roi, scale = scale)
    min_value = minMax_values.get(ee.String(image.bandNames().first()).cat("_min"))
    max_value = minMax_values.get(ee.String(image.bandNames().first()).cat("_max"))

    rescaled_image = image.expression('(image - min) / (max - min)', {
        'image': image,
        'min': min_value,
        'max': max_value
    })

    return rescaled_image.addBands(image.bandNames(), None, True)

def calc_image_stats(image, roi, scale):
    stats = image.reduceRegion(
        geometry=roi, 
        maxPixels = 1e13,
        scale=scale, 
        reducer=ee.Reducer.mean().combine(
            reducer2=ee.Reducer.stdDev(), 
            sharedInputs=True
        )
    )

    def add_3sd_bands(current_band, accum_dict):
        band = ee.String(current_band)
        dict_obj = ee.Dictionary(accum_dict)
        
        mean = ee.Number(dict_obj.get(band.cat("_mean")))
        std = ee.Number(dict_obj.get(band.cat("_stdDev")))
        
        minus3sd = mean.subtract(std.multiply(3))
        plus3sd = mean.add(std.multiply(3))
        
        return dict_obj \
            .set(band.cat("_minus3sd"), minus3sd) \
            .set(band.cat("_plus3sd"), plus3sd)

    stats_final = ee.Dictionary(image.bandNames().iterate(add_3sd_bands, stats))
    
    image_bands = image.bandNames()
    plus3sd_keys = image_bands.map(lambda b: ee.String(b).cat('_plus3sd'))
    minus3sd_keys = image_bands.map(lambda b: ee.String(b).cat('_minus3sd'))

    plus3sd_values = stats_final.select(plus3sd_keys).values()
    minus3sd_values = stats_final.select(minus3sd_keys).values()

    low = ee.Number(minus3sd_values.reduce(ee.Reducer.mean())).max(0)
    high = plus3sd_values.reduce(ee.Reducer.mean())

    low_high_values = ee.Dictionary({"low": low, "high": high})

    return low_high_values

def add_scaled_glcm(image, roi, scale, high_val):
    #Here reproject is critical to force the glcm to be calculated at 30 because the composite are in wgs84 by default
    glcm_image = image.select("nir")\
        .reproject(crs="EPSG:32645", scale=30)\
        .multiply(100).int32()\
        .glcmTexture(size=1, average=True).select(["nir_savg", "nir_shade"])
    min_max_val = glcm_image.reduceRegion(geometry = roi, reducer = ee.Reducer.minMax(), scale = scale, maxPixels = 1e13)
    rescaled_savg = glcm_image.select("nir_savg").unitScale(ee.Number(min_max_val.get("nir_savg_min")), ee.Number(min_max_val.get("nir_savg_max"))).clamp(0, 1).multiply(high_val)
    rescaled_shade = glcm_image.select("nir_shade").unitScale(ee.Number(min_max_val.get("nir_shade_min")), ee.Number(min_max_val.get("nir_shade_max"))).clamp(0, 1).multiply(high_val)

    return image.addBands(rescaled_savg).addBands(rescaled_shade)

def prepare_terrain_seg(terrain_image, roi, scale, high_val):
    terrain_minMax = terrain_image.select('slope')\
        .reduceRegion(ee.Reducer.minMax(), geometry = roi, scale = scale, maxPixels = 1e13)
    slope_norm = terrain_image.select('slope')\
        .unitScale(ee.Number(terrain_minMax.get("slope_min")), ee.Number(terrain_minMax.get("slope_max"))).clamp(0, 1)\
        .multiply(high_val)

    #Degree to radians
    aspect_rad = terrain_image.select('aspect').multiply(3.14159).divide(180)
    
    # Northness: Cosine (1=North, -1=South)
    # Scaled to 0-1 range: (val + 1) / 2
    northness = aspect_rad.cos().add(1).divide(2).multiply(high_val).rename('northness')
    
    # Eastness: Sine (1=East, -1=West)
    # Scaled to 0-1 range: (val + 1) / 2
    eastness = aspect_rad.sin().add(1).divide(2).multiply(high_val).rename('eastness')

    return slope_norm.addBands(northness).addBands(eastness)


#Function prepared by Gemini Pro (Check before using)
def riley_tri(dem):
    """
    Calculates Riley's Terrain Ruggedness Index (TRI) using the
    algebraic expansion method.
    
    The standard formula for TRI is:
       TRI = sqrt( Sum of (pixel - neighbor)^2 )
       
    Expanding the square term (a-b)^2 = a^2 - 2ab + b^2 allows us to use
    fast 'Focal Sum' reducers instead of slow iterations.
    
    Expanded Formula:
       TRI^2 = 8*E^2 - 2*E*(Sum of Neighbors) + (Sum of Squared Neighbors)
       
    Args:
        dem (ee.Image): Digital Elevation Model (single band)
        
    Returns:
        ee.Image: The Terrain Ruggedness Index
    """
    
    # ---------------------------------------------------------
    # STEP 1: DEFINE THE NEIGHBORHOOD KERNEL
    # ---------------------------------------------------------
    # We need a 3x3 window to find the 8 neighbors around a center pixel.
    # The weight '1' means "include this pixel".
    # The weight '0' in the center means "exclude the center pixel itself"
    # because we are calculating the difference BETWEEN center and neighbors.
    kernel_weights = [
        [1, 1, 1],
        [1, 0, 1],
        [1, 1, 1]
    ]
    
    # Create the kernel object from the weights
    kernel = ee.Kernel.fixed(3, 3, kernel_weights)

    # ---------------------------------------------------------
    # STEP 2: PRE-CALCULATE THE PIXEL TERMS
    # ---------------------------------------------------------
    
    # "E" is our Center Pixel (The Elevation itself)
    E = dem
    
    # "E_sq" is the Center Pixel Squared (E^2)
    # We need this for the first part of the expanded formula.
    E_sq = E.pow(2)
    
    # ---------------------------------------------------------
    # STEP 3: CALCULATE NEIGHBORHOOD SUMS (FOCAL REDUCERS)
    # ---------------------------------------------------------
    
    # "FS" (Focal Sum) = Sum of all 8 neighbors (Sum of x_i)
    # This corresponds to the middle term: -2 * E * Sum(x_i)
    FS = E.reduceNeighborhood(
        reducer=ee.Reducer.sum(),
        kernel=kernel
    )
    
    # "FSDEMsq" (Focal Sum of Squares) = Sum of all 8 neighbors SQUARED (Sum of x_i^2)
    # This corresponds to the final term: + Sum(x_i^2)
    FSDEMsq = E_sq.reduceNeighborhood(
        reducer=ee.Reducer.sum(),
        kernel=kernel
    )

    # ---------------------------------------------------------
    # STEP 4: COMBINE TERMS USING THE ALGEBRAIC FORMULA
    # ---------------------------------------------------------
    # Formula: TRI^2 = (N * E^2) - (2 * E * Sum_Neighbors) + (Sum_Neighbor_Squares)
    
    # Term 1: 8 * E^2
    # Note: We use 8 because there are 8 neighbors in a 3x3 window.
    # (To be safer at image edges, you could dynamically count neighbors, but 8 is standard).
    term_1 = E_sq.multiply(8)
    
    # Term 2: 2 * E * Sum_Neighbors
    term_2 = E.multiply(2).multiply(FS)
    
    # Term 3: Sum_Neighbor_Squares (already calculated as FSDEMsq)
    term_3 = FSDEMsq
    
    # Combine them: (8E^2 - 2E*FS + FSDEMsq)
    # We subtract term 2 and add term 3.
    TRI_sq = term_1.subtract(term_2).add(term_3)
    
    # ---------------------------------------------------------
    # STEP 5: FINAL SQUARE ROOT
    # ---------------------------------------------------------
    # The result above is TRI squared. We need the square root for the final index.
    # We also apply .abs() before sqrt to ensure no tiny negative floating-point errors.
    TRI = TRI_sq.abs().sqrt().rename('TRI')
    
    return TRI
    