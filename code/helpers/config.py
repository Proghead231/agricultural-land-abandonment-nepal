import ee
ee.Initialize(project = "ee-joshisur231")
SCALE = 30
PROJ = "EPSG:32645"
test_roi =     ee.Geometry.MultiPolygon(
        [[[[85.5601951765166, 27.828610555873862],
           [85.5601951765166, 27.79938350748526],
           [85.5931541608916, 27.79938350748526],
           [85.5931541608916, 27.828610555873862]]],
         [[[85.06820455283122, 27.634291724500947],
           [85.06820455283122, 27.623189372513107],
           [85.08545652121501, 27.623189372513107],
           [85.08545652121501, 27.634291724500947]]],
         [[[87.42522897237968, 26.659095546659827],
           [87.42522897237968, 26.622577559243478],
           [87.47398080343437, 26.622577559243478],
           [87.47398080343437, 26.659095546659827]]]], None, False)
test_roi2 =     ee.Geometry.Polygon(
        [[[85.04481417876723, 27.890669285959213],
          [85.04481417876723, 27.6835236717276],
          [85.29475314361098, 27.6835236717276],
          [85.29475314361098, 27.890669285959213]]], None, False)
test_class =ee.Geometry.Polygon(
        [[[85.66603677368612, 27.93590111149637],
          [85.66603677368612, 26.568593636200408],
          [86.30873696899862, 26.568593636200408],
          [86.30873696899862, 27.93590111149637]]], None, False)
test_class2 = ee.Geometry.Polygon(
        [[[82.58121523790525, 29.534087675244226],
          [82.58121523790525, 27.49248984292568],
          [83.32828555040525, 27.49248984292568],
          [83.32828555040525, 29.534087675244226]]], None, False)

east_terai = ee.FeatureCollection(
        [ee.Feature(
            ee.Geometry.Polygon(
                [[[87.46004060330993, 26.66466152353658],
                  [87.46004060330993, 26.574884387894166],
                  [87.56063417020447, 26.574884387894166],
                  [87.56063417020447, 26.66466152353658]]], None, False),
            {
              "loc": "east_terai",
              "geoCode": 1,
              "system:index": "1"
            })])
east_mount = ee.FeatureCollection(
        [ee.Feature(
            ee.Geometry.Polygon(
                [[[87.55800345681718, 27.167696201346097],
                  [87.55800345681718, 27.077247807402074],
                  [87.66031363748124, 27.077247807402074],
                  [87.66031363748124, 27.167696201346097]]], None, False),
            {
              "loc": "east_mount",
              "geoCode": 2,
              "system:index": "2"
            })])
central_terai =  ee.FeatureCollection(
        [ee.Feature(
            ee.Geometry.Polygon(
                [[[84.3660186586482, 27.717162029130552],
                  [84.3660186586482, 27.626249733206926],
                  [84.46832883931226, 27.626249733206926],
                  [84.46832883931226, 27.717162029130552]]], None, False),
            {
              "loc": "central_terai",
              "geoCode": 3,
              "system:index": "3"
            })])
central_mount = ee.FeatureCollection(
        [ee.Feature(
            ee.Geometry.Polygon(
                [[[84.73388512351926, 28.043305621113884],
                  [84.73388512351926, 27.95205973834884],
                  [84.83825524070676, 27.95205973834884],
                  [84.83825524070676, 28.043305621113884]]], None, False),
            {
              "loc": "central_mount",
              "geoCode": 4,
              "system:index": "4"
            })])
west_terai = ee.FeatureCollection(
        [ee.Feature(
            ee.Geometry.Polygon(
                [[[80.18459462060123, 28.949404739402418],
                  [80.18459462060123, 28.858937756082078],
                  [80.28930806054264, 28.858937756082078],
                  [80.28930806054264, 28.949404739402418]]], None, False),
            {
              "loc": "west_terai",
              "geoCode": 5,
              "system:index": "5"
            })])
west_mount = ee.FeatureCollection(
        [ee.Feature(
            ee.Geometry.Polygon(
                [[[82.23306166435877, 28.737571748753187],
                  [82.23306166435877, 28.64692063360459],
                  [82.33537184502283, 28.64692063360459],
                  [82.33537184502283, 28.737571748753187]]], None, False),
            {
              "loc": "west_mount",
              "geoCode": 6,
              "system:index": "6"
            })])
west_him = ee.FeatureCollection(
        [ee.Feature(
            ee.Geometry.Polygon(
                [[[82.27763191221172, 29.369348407754917],
                  [82.27763191221172, 29.276854386066354],
                  [82.38234535215312, 29.276854386066354],
                  [82.38234535215312, 29.369348407754917]]], None, False),
            {
              "loc": "west_him",
              "geoCode": 7,
              "system:index": "7"
            })])
central_him = ee.FeatureCollection(
        [ee.Feature(
            ee.Geometry.Polygon(
                [[[85.72453813237863, 27.976655527759867],
                  [85.72453813237863, 27.885960165290857],
                  [85.8275349585505, 27.885960165290857],
                  [85.8275349585505, 27.976655527759867]]], None, False),
            {
              "loc": "central_him",
              "geoCode": 8,
              "system:index": "8"
            })])
east_him = ee.FeatureCollection(
        [ee.Feature(
            ee.Geometry.Polygon(
                [[[87.74972061721513, 27.59672846389902],
                  [87.74972061721513, 27.506934175049263],
                  [87.8520307978792, 27.506934175049263],
                  [87.8520307978792, 27.59672846389902]]], None, False),
            {
              "loc": "east_him",
              "geoCode": 9,
              "system:index": "9"
            })])
test_geo = east_terai.merge(east_mount).merge(east_him).merge(central_terai).merge(central_mount).merge(central_him).merge(west_terai).merge(west_mount).merge(west_him)

ROI = ee.FeatureCollection("projects/ee-joshisur231/assets/pa_effectiveness/nepal_boundary").geometry()


L75_ORIGINAL_BAND_NAMES = ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"]
L75_NEW_BAND_NAMES      = ["blue", "green", "red", "nir", "swir1", "swir2"]
L8_ORIGINAL_BAND_NAMES  = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
L8_NEW_BAND_NAMES       = ["blue", "green", "red", "nir", "swir1", "swir2"]
L_FINAL_BANDS = ["blue", "green", "red", "nir", "swir1", "swir2"]

LANDSAT_DATES = {
    "2000": ["2000-11-01", "2001-02-28"],
    "2010": ["2010-11-01", "2011-02-28"],
    "2020": ["2020-11-01", "2021-02-28"]
}