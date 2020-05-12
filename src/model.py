"""Module for model adaption"""

import os
import glob
from mako.template import Template
from collections import OrderedDict
import yaml
import tools
from datetime import datetime, timedelta
import pandas as pd 
import numpy as np

global logger 

# create logger
logger = tools.init_logger()

def read(settings):
    # Read yaml settings file and return dictionary with SMT settings
    logger.info('Initialising run')
    logger.info(f'Reading {settings} ...')

    try:
        smt_settings = yaml.safe_load(open(settings, 'r'))
        logger.info(f'Parsed settings file: {settings}\n#---start of file ---\n {yaml.dump(smt_settings)}#---end of file ---')
    except yaml.YAMLError as exc:
        logger.error(f'Error in SMT settings file: {exc}')
        logger.info('')
        raise exc

    logger.info('')
    logger.info(f'Parsed settings file: {settings}\n#---start of file ---\n {yaml.dump(smt_settings)}#---end of file ---')
    return smt_settings

def validate(smt_settings):
    # Validate SMT settings dictionary
    logger.info('')
    logger.info('Found the following automatic variables:')
    auto_vars = []
    if smt_settings['variables']['automatic'] != None:
        for var in smt_settings['variables']['automatic']: 
            logger.info(var)
            auto_vars.append(var)
    user_vars = []
    logger.info('Found the following user defined variables:')
    for var in smt_settings['variables']['user']: 
        logger.info(var)
        user_vars.append(var)
    all_vars = user_vars.copy() + auto_vars

    # Assertion checks for uniqueness of variables
    tools.logger_assert(len(set(auto_vars))==len(auto_vars), 'Duplicate automatic variable found')
    tools.logger_assert(len(set(user_vars))==len(user_vars), 'Duplicate user variable found')
    tools.logger_assert(len(set(all_vars))==len(all_vars), 'Variable found in both user defined and automatic variables')
    logger.info('')

    # TODO: Assertion checks for cyclic definitions

    # Assertion checks for simulation type
    simulation_types = ['quasi-steady-hydrograph', 'simulation-list']
    tools.logger_assert(smt_settings['model']['simulation_type'] in simulation_types, f'simulation_type should be one of {simulation_types}')

def set_input(smt_settings, time_index):
    smt_user = smt_settings['variables']['user']
    user_vars = []
    for var in smt_user: 
        user_vars.append(var)

    if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
        dependance_map = {} 
        model_settings = {}
        prev_key = ''
        for key in user_vars: 
            value = smt_user[key]
            if key in list(model_settings.keys()):
                prev_key = key
                continue
            if prev_key == key: 
                logger.critical(f'Error setting variable: {key}')
                raise KeyError
            if type(value) == dict: 
                if 'TimeDuration' in value.keys():
                    try: 
                        value = list(smt_user[key]['TimeDuration'][time_index].keys())[0]
                        model_settings['TimeDuration'] = value
                        value = smt_user[key]['TimeDuration'][time_index][model_settings['TimeDuration']]
                        model_settings[key] = value
                        dependance_map['TimeDuration'] = ''
                    except IndexError:
                        model_settings = None
                        return model_settings
                else:     
                    try: 
                        value = smt_user[key][list(value.keys())[0]][model_settings[list(value.keys())[0]]]
                        model_settings[key] = value 
                        dependance_map[key] = list(smt_user[key].keys())[0]
                    except KeyError:
                        user_vars.append(key)
                        
            else: 
                model_settings[key] = value
                dependance_map[key] = ''
            prev_key = key    
    elif smt_settings['model']['simulation_type'] == 'simulation-list':
        model_settings = {}
        dependance_map = {} 
        if 'fromfile' not in user_vars:
            logger.critical(f'User variable `fromfile` not found')
            raise ValueError
        df = pd.read_csv(smt_user['fromfile'])
        if time_index in df.index: 
            for key in df.keys(): 
                model_settings[key] = df[key][time_index]
        else: 
            return None
    else: 
        logger.error('simulation_type not implemented')
        raise NotImplementedError

    if smt_settings['variables']['automatic'] != None: 
        reserved_keys = list(smt_settings['variables']['automatic'].keys())
    else: 
        reserved_keys = []
    
    filename_settings = model_settings.copy()
    for key in reserved_keys: 
        filename_settings.pop(key, None)

    for key in dependance_map.keys(): 
        if dependance_map[key] in filename_settings.keys():
            filename_settings.pop(key, None)
        elif dependance_map[key] == '': 
            # ignore constant values and TimeDuration
            filename_settings.pop(key, None)
            
    file_append = '_' + '_'.join(str(k) for k in (filename_settings.values()))
    model_settings['FileAppendix'] = file_append

    return model_settings

def get_input(smt_settings):
    """Generator for model input"""

    time_index = 0
    time_start = 0
    model_settings = []
    while True and model_settings != None: 
        model_settings = set_input(smt_settings, time_index)

        if model_settings != None: 
            logger.debug('Variables updated ...')
            for key in model_settings.keys():   
                logger.debug(f'{key}: {model_settings[key]}')
    
            model_settings['TimeIndex'] = time_index

            if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
                head, _ = os.path.splitext(smt_settings['model']['input'])
                file_append = model_settings['FileAppendix']
                restart_file = f'{head}{file_append}_rst.nc'
                model_settings['RestartFileBackup'] = os.path.join('local_database',restart_file)                            
                model_settings['RestartFileName'] = restart_file
                if os.path.exists(os.path.join('local_database',restart_file)):
                    logger.info('Restart file found in local_database')
                    model_settings['RestartFile'] = restart_file
                    model_settings['RestartFileLocation'] = os.path.join('local_database',restart_file)
                    restart_level = 0
                else: 
                    logger.info('Restart file not found in local_database')
                    if os.path.exists(os.path.join('central_database',restart_file)):
                        logger.info('Restart file found in central_database')
                        model_settings['RestartFile'] = restart_file
                        model_settings['RestartFileLocation'] = os.path.join('central_database',restart_file)
                        restart_level = 1
                    else: 
                        logger.info('Restart file not found in central_database')
                        if time_index > 0:
                            logger.info('Starting from final result of last simulation')
                            model_settings['RestartFile'] = restart_file
                            model_settings['RestartFileLocation'] = '' 
                            restart_level = 2
                        else:
                            logger.info('Cold startup')
                            model_settings['RestartFile'] = ''
                            model_settings['RestartFileLocation'] = '' 
                            restart_level = 3
                model_settings['RestartLevel'] = restart_level        
                model_settings['SpinupTime'] = model_settings['SpinupTime'][restart_level]
                model_settings['MorStt'] = model_settings['SpinupTime']

                model_settings['TStart'] = time_start
                model_settings['TStop'] = time_start + model_settings['TimeDuration'] + model_settings['SpinupTime'] 
                if model_settings['TUnit'] == 'S':
                    tunit_in_seconds = 1
                    time_delta_start = timedelta(seconds = time_start)
                elif model_settings['TUnit'] == 'M':
                    tunit_in_seconds = 60
                    time_delta_start = timedelta(minutes = time_start)
                elif model_settings['TUnit'] == 'H':
                    tunit_in_seconds = 3600
                    time_delta_start = timedelta(hours = time_start)
                elif model_settings['TUnit'] == 'D':
                    tunit_in_seconds = 86400
                    time_delta_start = timedelta(days = time_start)
                refdate = datetime.strptime(model_settings['ReferenceDate'], '%Y%m%d')
                model_settings['MapInterval'] = (model_settings['TimeDuration'] + model_settings['SpinupTime'])*tunit_in_seconds
                model_settings['RstInterval'] = (model_settings['TimeDuration'] + model_settings['SpinupTime'])*tunit_in_seconds
                model_settings['RestartDateTime'] = datetime.strftime(refdate + time_delta_start, '%Y%m%d%H%M%S')
                time_start = model_settings['TStop']

            yield model_settings

        # increase counter 
        time_index += 1

def adapt(model_settings, smt_settings):
    
    logger.info('Starting adaptation of source folder')
    
    for item in glob.glob('**', recursive=True):
        if os.path.isfile(item): 
            head, tail = os.path.split(item)
            if (tail.find('.template') > 0) and not (head.find('source') > -1): 
                filename = tail.replace('.template','')
                file_head, file_ext = os.path.splitext(filename)
                if file_ext not in smt_settings['application']['input']: 
                    if file_ext == '.tim':
                        # TODO: remove this special case
                        filename_new = ''.join([file_head[:-5], model_settings['FileAppendix'], file_head[-5:]+file_ext])
                    else: 
                        filename_new = ''.join([file_head, model_settings['FileAppendix'], file_ext])
                else:
                    filename_new = filename
                full_filename_new = os.path.join(head,filename_new)
                if os.path.isfile(full_filename_new): 
                    logger.debug(f'Skipping {full_filename_new}')
                else: 
                    logger.debug(f'Rendering {full_filename_new}')
                    with open(full_filename_new, 'w') as f:                         
                        mytemplate = Template(filename=item, strict_undefined=True)
                        f.write(mytemplate.render(**model_settings).replace('\r',''))

    if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
        if model_settings['RestartLevel'] < 2: 
            tools.netcdf_copy(model_settings['RestartFileLocation'], os.path.join('work',model_settings['RestartFile']), smt_settings['model']['exclude_from_database'])
            if model_settings['TimeIndex'] > 0: 
                last_output_restart_file = [rst for rst in glob.glob('output/'+str(model_settings['TimeIndex'] - 1)+'/**/**/**_rst.nc', recursive=True)][-1]
                tools.netcdf_append(last_output_restart_file, os.path.join('work',model_settings['RestartFile']), smt_settings['model']['exclude_from_database'])
        elif model_settings['RestartLevel'] == 2: 
            last_output_restart_file = [rst for rst in glob.glob('output/'+str(model_settings['TimeIndex'] - 1)+'/**/**/**_rst.nc', recursive=True)][-1]
            tools.netcdf_copy(last_output_restart_file, os.path.join('work',model_settings['RestartFile']), [])   # copy all data

def finalize(model_settings, smt_settings):
    """Finalize model output"""
    
    if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
        # backup restart file to local database
        try: 
            restart_file = [rst for rst in glob.glob('output/'+str(model_settings['TimeIndex'])+'/**/**/**_rst.nc', recursive=True)][-1]
        except: 
            logger.error('Check .dia file')
            raise IndexError
        tools.netcdf_copy(restart_file, model_settings['RestartFileBackup'], smt_settings['model']['exclude_from_database'])


