"""Module containing helper tools for reference plance updating"""


import numpy as np
import netCDF4
from pathlib import Path
import shutil

def read_model_refplane(model_refplane_file,nPart):
    model_refplane_file = Path(model_refplane_file)
    model_refplane_first_file = model_refplane_file.parents[0].joinpath(model_refplane_file.name+'.first')
    model_refplane_dir = model_refplane_file.parents[0]
    if not model_refplane_dir.is_dir():
        model_refplane_dir.mkdir()

    for k in range(0,nPart):
        src_netcdf = Path(f'results/RIJN_{k:04d}_map.nc')
        with netCDF4.Dataset(src_netcdf,'r') as src:
            x = src['mesh2d_face_x'][:]
            y = src['mesh2d_face_y'][:]
            s1 = src['mesh2d_s1'][-1,:].flatten()
            bl = src['mesh2d_mor_bl'][-1,:].flatten()
            s1[s1.mask]=bl[s1.mask]
            
            A = np.stack([x,y,s1]).transpose()
            if k==0: 
                file_permission = 'w'
            else:
                file_permission = 'a'
            
            with open(model_refplane_file, file_permission) as f:
                #s = str(k)  # convert the tuple to string
                #f.write(s)
                np.savetxt(f, A)

    # Store the first model reference plane
    if not model_refplane_first_file.is_file():
        shutil.copy(model_refplane_file,model_refplane_first_file)

def update_refplane(model_refplane_file, refplane_original_file):
    from scipy.interpolate import LinearNDInterpolator
    model_refplane_file = Path(model_refplane_file)
    model_refplane_first_file = model_refplane_file.parents[0].joinpath(model_refplane_file.name+'.first')
    refplane_file = model_refplane_file.parents[0].joinpath('refplane.xyz')
    
    refplane_original = np.loadtxt(refplane_original_file)
    model_refplane = np.loadtxt(model_refplane_file)
    model_refplane_first = np.loadtxt(model_refplane_first_file)
    x_model_refplane = model_refplane[:,0]
    y_model_refplane = model_refplane[:,1]
    z_model_refplane = model_refplane[:,2]
    x_model_refplane_first = model_refplane_first[:,0]
    y_model_refplane_first = model_refplane_first[:,1]
    z_model_refplane_first = model_refplane_first[:,2]
    x_refplane_original = refplane_original[:,0]
    y_refplane_original = refplane_original[:,1]
    z_refplane_original = refplane_original[:,2]
    interp_refplane_original = LinearNDInterpolator(list(zip(x_refplane_original, y_refplane_original)), z_refplane_original) # NearestNDInterpolator ? 
    interp_model_refplane_first = LinearNDInterpolator(list(zip(x_model_refplane_first, y_model_refplane_first)), z_model_refplane_first)
    z_refplane = interp_refplane_original(x_model_refplane, y_model_refplane) + z_model_refplane - interp_model_refplane_first(x_model_refplane, y_model_refplane)
    A = np.stack([x_model_refplane,y_model_refplane,z_refplane]).transpose()
    with open(refplane_file, 'w') as f:
        np.savetxt(f, A)
    return refplane_file

if __name__ == "__main__":
    import sys 
    model_refplane_file = Path(sys.argv[1])  
    refplane_original_file = Path(sys.argv[2]) 
    nPart = int(sys.argv[3])
    
    print(f'Reading model refplane {model_refplane_file} for {nPart} partitions')
    read_model_refplane(model_refplane_file,nPart)
    
    print(f'Updating refplane {refplane_original_file} based on {model_refplane_file}')
    refplane_file = update_refplane(model_refplane_file, refplane_original_file)

    print(f'Resulting replane is available here: {refplane_file}')

#np.savetxt('test.out', A, fmt='%1.4e')