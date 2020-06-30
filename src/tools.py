"""Module containing helper tools for SMT"""

import sys
import os
import logging
import logging.config
import glob
import netCDF4
from datetime import datetime, timedelta
import time # for timezone information 
import shutil

global logger 

# create logger
def init_logger(): 
    head,_ = os.path.split(__file__)
    logging.config.fileConfig(os.path.join(head,'logging.conf'))
    logger = logging.getLogger('SMT')
    return logger

logger = init_logger()

def copy(src, trgt):
    """Recursive copy function from source location to target location"""
    # check that directory exists and otherwise make it
    guaranteedir(os.path.dirname(trgt))
    logger.info('Copying ' + src + ' to ' + trgt + ' ...')
    shutil.copy(src,trgt)

def move(src, trgt):
    """Recursive move function from source location to target location"""
    logger.info('Moving ' + src + ' to ' + trgt + ' ...')
    if os.name == 'nt':
        os.system('move /Y ' + src + ' ' + trgt)
    elif os.name == 'posix':
        os.system('mv ' + src + ' ' + trgt)
    else:
        logger.error('Move statement not implemented for OS "' + os.name + '"')

def remove(pattern):
    """Recursive delete function according to specified pattern"""
    logger.info('Removing ' + pattern)
    for name in glob.glob(pattern, recursive=True):
        if os.path.exists(name):
            os.remove(name)

def guaranteedir(mydir):
    """Make a directory and exit if this is not possible"""
    if not os.path.exists(mydir) and mydir != '':
        logger.info('Creating subdirectory ' + mydir + ' ...')
        os.mkdir(mydir)
        if not os.path.isdir(mydir):
            logging.error('Cannot create subdirectory ' + mydir)

def logger_assert(condition, error_message):
    try:
        assert(condition)
    except AssertionError as err:
        logger.error(error_message)
        raise err

def netcdf_copy(src_netcdf, dst_netcdf, exclude_list): 
    """ copies src_netcdf to dst_netcdf excluding variables in exclude list """

    logger.info('netCDF copy ' + src_netcdf + ' to ' + dst_netcdf + ' ...')
    logger.info('excluding variables '+ ' '.join(exclude_list))
    
    # check that directory exists and otherwise make it
    guaranteedir(os.path.dirname(dst_netcdf))

    # open files for reading and writing 
    with netCDF4.Dataset(src_netcdf, 'r') as src:
        with netCDF4.Dataset(dst_netcdf, 'w') as dst:
            
            # Copy attributes 
            for attribute in src.ncattrs(): 
                dst.setncattr(attribute,getattr(src, attribute))
            
            # Update attributes with time information 
            now = datetime.now()
            dst.setncattr('history', 'Created on '+ now.strftime('%Y-%m-%dT%H:%M:%S') + time.strftime('%z', time.gmtime()) + ', Simulation Management Tool')
            dst.setncattr('date_created', now.strftime('%Y-%m-%dT%H:%M:%S') + time.strftime('%z', time.gmtime()))
            dst.setncattr('date_modified', now.strftime('%Y-%m-%dT%H:%M:%S') + time.strftime('%z', time.gmtime()))

            # copy dimensions 
            for name, dimension in src.dimensions.items():
                dst.createDimension(name, len(dimension) if not dimension.isunlimited() else None)

            # copy variables
            for name, variable in src.variables.items():
                if name in exclude_list: 
                    continue
                x = dst.createVariable(name, variable.datatype, variable.dimensions)
                dst.variables[name][:] = src.variables[name][:]

def netcdf_append(src_netcdf, dst_netcdf, append_list): 
    """ appends variables in exclude list from src_netcdf to dst_netcdf """

    logger.info('netCDF append ' + src_netcdf + ' to ' + dst_netcdf + ' ...')
    logger.info('for variables '+ ' '.join(append_list))

    # open files for reading and appending 
    with netCDF4.Dataset(src_netcdf, 'r') as src:
        with netCDF4.Dataset(dst_netcdf, 'a') as dst:
            
            # Update date_modified attribute
            now = datetime.now()
            dst.setncattr('date_modified', now.strftime('%Y-%m-%dT%H:%M:%S') + time.strftime('%z', time.gmtime()))

            # copy variables
            for name, variable in src.variables.items():
                if name in append_list: 
                    dst_dimension_names = [dim[0] for dim in dst.dimensions.items()]
                    for dim_name in variable.dimensions: 
                        if dim_name not in dst_dimension_names: 
                            # copy dimensions 
                            dimension2 = src.dimensions[dim_name]
                            dst.createDimension(dim_name, len(dimension2) if not dimension2.isunlimited() else None)

                    x = dst.createVariable(name, variable.datatype, variable.dimensions)
                    dst.variables[name][:] = src.variables[name][:]                
                continue
