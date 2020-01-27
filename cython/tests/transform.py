from fct.lib import terrain_analysis as ta
import rasterio as rio
import numpy as np
import os

# root = '/Volumes/Backup/TESTS/SubGrid/'
root = 'cython/tests/data'
ds = rio.open(os.path.join(root, 'short.tif'))

grid = np.mgrid[0:ds.height, 0:ds.width]
grid = np.int32(grid.reshape((2, ds.height*ds.width)).T)

xy = ta.pixeltoworld(grid, ds.transform, gdal=False)
# xy = np.float32(xy)

for current, (i, j) in enumerate(grid):
    xr, yr = ds.xy(i, j)
    assert(xy[current, 0] == xr)
    assert(xy[current, 1] == yr)

back = ta.worldtopixel(xy, ds.transform, gdal=False)

for current, (i, j) in enumerate(back): 
    assert(grid[current, 0] == i) 
    assert(grid[current, 1] == j)

for current, (x, y) in enumerate(xy):
    ir, jr = ds.index(x, y)
    assert(back[current, 0] == ir)
    assert(back[current, 1] == jr)