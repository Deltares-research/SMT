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
    logger.info('')
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
        user_vars.append(var.strip())
    if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
        dependance_map = {} 
        model_settings = {}
        prev_key = ''
        if 'from_file' in user_vars:
            df = pd.read_csv(smt_user['from_file'])
            df.rename(columns = dict(zip(df.keys(),list(s.strip() for s  in df.keys()))), inplace=True)
            if time_index in df.index: 
                for key in df.keys(): 
                    model_settings[key] = df[key][time_index]
                    if key == 'TimeDuration': 
                        dependance_map[key] = ''
            else: 
                return None
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
                        if model_settings[list(value.keys())[0]] in smt_user[key][list(value.keys())[0]].keys():
                            value = smt_user[key][list(value.keys())[0]][model_settings[list(value.keys())[0]]]
                            model_settings[key] = value 
                            dependance_map[key] = list(smt_user[key].keys())[0]
                        else: 
                            logger.error(f'Error setting {key}, from {list(value.keys())[0]} = {model_settings[list(value.keys())[0]]}')
                            raise IndexError(f'Error setting {key}, from {list(value.keys())[0]} = {model_settings[list(value.keys())[0]]}')
                    except KeyError:
                        user_vars.append(key)
                        
            else: 
                model_settings[key] = value
                dependance_map[key] = ''
            prev_key = key    
            logger.info(f'Found {key}: {value}')
    elif smt_settings['model']['simulation_type'] == 'simulation-list':
        model_settings = {}
        dependance_map = {} 
        if 'from_file' not in user_vars:
            logger.critical(f'User variable `from_file` not found')
            raise ValueError
        df = pd.read_csv(smt_user['from_file'])
        df.rename(columns = dict(zip(df.keys(),list(s.strip() for s  in df.keys()))), inplace=True)
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
    model_settings['TimeIndex'] = time_index

    partition_total, processes_string = get_partition_total(smt_settings)
    model_settings['ProcessesString'] = processes_string

    for key in model_settings.keys(): 
        if type(model_settings[key])==str: 
            model_settings[key]=model_settings[key].replace(r'${FileAppendix}', model_settings['FileAppendix'])  

    return model_settings

def get_input(smt_settings):
    """Generator for model input"""

    time_index = 0
    time_start = 0.
    model_settings = []
    while True and model_settings != None: 
        model_settings = set_input(smt_settings, time_index)

        partition_total, _ = get_partition_total(smt_settings)

        if model_settings != None: 
            logger.debug('Variables updated ...')
            for key in model_settings.keys():   
                logger.debug(f'{key}: {model_settings[key]}')

            if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
                head, _ = os.path.splitext(smt_settings['model']['input'])
                file_append = model_settings['FileAppendix']

                restart_file_database = f'{head}{file_append}_rst.nc'
                model_settings['RstIgnoreBl'] = 0
                if 'DIMR_dflowfm_workdir' in smt_settings['model']:
                    restart_file_database = os.path.join(smt_settings['model']['DIMR_dflowfm_workdir'],restart_file_database)
                if 'DIMR_rtc_workdir' in smt_settings['model']:
                    rtc_file = f'state_import{file_append}.xml'
                    rtc_file_location = os.path.join(smt_settings['model']['DIMR_rtc_workdir'],rtc_file)
                if smt_settings['model']['load_from_database'] == False: 
                    logger.info('Cold startup - (neglecting restart information)')
                    model_settings['RestartFileFromBackupLocation'] = '' # None ?
                    model_settings['RestartFileToBackupLocation'] = os.path.join('local_database',restart_file_database)
                    if 'DIMR_rtc_workdir' in smt_settings['model']:
                        model_settings['RTCFile'] = model_settings['RTC_initial_state']
                        model_settings['RTCFileLocation'] = rtc_file_location
                        model_settings['RTCFileFromBackupLocation'] = ''
                        model_settings['RTCFileToBackupLocation'] = os.path.join('local_database',rtc_file_location)
                    restart_level = 3
                elif partition_path_exists(os.path.join('local_database',restart_file_database), head, partition_total):
                    logger.info('Restart file found in local_database')
                    model_settings['RestartFileFromBackupLocation'] = os.path.join('local_database',restart_file_database)
                    model_settings['RestartFileToBackupLocation'] = os.path.join('local_database',restart_file_database)
                    if time_index == 0: 
                        model_settings['RstIgnoreBl'] = 1
                    if 'DIMR_rtc_workdir' in smt_settings['model']:
                        model_settings['RTCFile'] = rtc_file
                        model_settings['RTCFileLocation'] = rtc_file_location
                        model_settings['RTCFileFromBackupLocation'] = os.path.join('local_database',rtc_file_location)
                        model_settings['RTCFileToBackupLocation'] = os.path.join('local_database',rtc_file_location)
                    restart_level = 0
                else: 
                    logger.info('Restart file not found in local_database')
                    if partition_path_exists(os.path.join('central_database',restart_file_database), head, partition_total):
                        logger.info('Restart file found in central_database')
                        model_settings['RestartFileFromBackupLocation'] = os.path.join('central_database',restart_file_database)
                        model_settings['RestartFileToBackupLocation'] = os.path.join('local_database',restart_file_database)
                        if time_index == 0: 
                            model_settings['RstIgnoreBl'] = 1
                        if 'DIMR_rtc_workdir' in smt_settings['model']:
                            model_settings['RTCFile'] = rtc_file
                            model_settings['RTCFileLocation'] = rtc_file_location
                            model_settings['RTCFileFromBackupLocation'] = os.path.join('central_database',rtc_file_location)
                            model_settings['RTCFileToBackupLocation'] = os.path.join('local_database',rtc_file_location)
                        restart_level = 1
                    else: 
                        logger.info('Restart file not found in central_database')
                        if time_index > 0:
                            logger.info('Starting from final result of last simulation')
                            model_settings['RestartFileFromBackupLocation'] = '' 
                            model_settings['RestartFileToBackupLocation'] = os.path.join('local_database',restart_file_database)
                            if 'DIMR_rtc_workdir' in smt_settings['model']:
                                model_settings['RTCFile'] = rtc_file
                                model_settings['RTCFileLocation'] = rtc_file_location
                                model_settings['RTCFileFromBackupLocation'] = ''
                                model_settings['RTCFileToBackupLocation'] = os.path.join('local_database',rtc_file_location)
                            restart_level = 2
                            # All Initial field information follows from previous restart, so do not use IniFieldFile
                            if 'IniFieldFile' in model_settings.keys(): 
                                model_settings['IniFieldFile'] = ''                             
                        else:
                            logger.info('Cold startup')
                            model_settings['RestartFileFromBackupLocation'] = '' # None ?
                            model_settings['RestartFileToBackupLocation'] = os.path.join('local_database',restart_file_database)
                            if 'DIMR_rtc_workdir' in smt_settings['model']:
                                model_settings['RTCFile'] = model_settings['RTC_initial_state'] # '../../initial/rtc/state_import.xml'
                                model_settings['RTCFileLocation'] = rtc_file_location
                                model_settings['RTCFileFromBackupLocation'] = ''
                                model_settings['RTCFileToBackupLocation'] = os.path.join('local_database',rtc_file_location)
                            restart_level = 3
                model_settings['RestartLevel'] = restart_level        
                model_settings['SpinupTime'] = model_settings['SpinupTime'][restart_level]
                model_settings['MorStt'] = model_settings['SpinupTime']

                model_settings['TStart'] = time_start
                time_stop = time_start + model_settings['TimeDuration'] + model_settings['SpinupTime']
                model_settings['TStop'] = time_stop
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
                time_start_seconds = time_start*tunit_in_seconds
                time_start_post_spinup_seconds = (time_start+model_settings['SpinupTime'])*tunit_in_seconds
                time_stop_seconds = time_stop*tunit_in_seconds
                time_duration_post_spinup_seconds = float(model_settings['TimeDuration'])*tunit_in_seconds
                model_settings['MapInterval'] = f"{time_duration_post_spinup_seconds} {time_start_post_spinup_seconds} {time_stop_seconds}"
                model_settings['RstInterval'] = f"{time_duration_post_spinup_seconds} {time_start_post_spinup_seconds} {time_stop_seconds}"
                model_settings['RestartDateTime'] = datetime.strftime(refdate + time_delta_start, '%Y%m%d%H%M%S')
                model_settings['RestartDateTimeStop'] = datetime.strftime(refdate + timedelta(seconds = time_stop_seconds), '%Y%m%d_%H%M%S')
                time_start = model_settings['TStop']

                model_settings['RestartFile'] = ''
                model_settings['RestartFileLocation'] = '' # restart_file_database
                if restart_level < 3: 
                    restart_file_date_time_string = datetime.strftime(refdate + time_delta_start, '%Y%m%d_%H%M%S')
                    model_settings['RestartFile'] = f'{head}_{restart_file_date_time_string}_rst.nc'
                    if 'DIMR_dflowfm_workdir' in smt_settings['model']:
                        model_settings['RestartFileLocation'] = os.path.join(smt_settings['model']['DIMR_dflowfm_workdir'],model_settings['RestartFile'])  
                    else:                   
                        model_settings['RestartFileLocation'] = model_settings['RestartFile']
                if 'DIMR_dflowfm_workdir' in smt_settings['model']:
                    model_settings['DIMR_dflowfm_workdir'] = smt_settings['model']['DIMR_dflowfm_workdir']
                if 'DIMR_rtc_workdir' in smt_settings['model']:
                    model_settings['DIMR_rtc_workdir'] = smt_settings['model']['DIMR_rtc_workdir']
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
                logger.debug(f'Rendering {full_filename_new}')
                with open(full_filename_new, 'w') as f:                         
                    mytemplate = Template(filename=item, strict_undefined=True, input_encoding='utf-8')
                    f.write(mytemplate.render(**model_settings).replace('\r',''))
                if file_ext == '.sh': 
                    os.chmod(full_filename_new, 0o0777)
    if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
        if 'DIMR_rtc_workdir' in smt_settings['model']:
            rtc_new_file = os.path.join('output','work',smt_settings['model']['DIMR_rtc_workdir'],'state_import.xml')

        head, _ = os.path.splitext(smt_settings['model']['input'])
        partition_total, _ = get_partition_total(smt_settings)

        for partition_number in range(partition_total): 
            if partition_total == 1: 
                partition_string = '' 
            else: 
                partition_string = f'_{partition_number:04}'
                            
            if model_settings['RestartLevel'] < 2: 
                tools.netcdf_copy(model_settings['RestartFileFromBackupLocation'].replace(head, f'{head}{partition_string}'), 
                                  os.path.join('output','work',model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}')), 
                                  smt_settings['model']['exclude_from_database'])
                if 'DIMR_rtc_workdir' in smt_settings['model']:
                    tools.remove(rtc_new_file)
                    tools.copy(model_settings['RTCFileFromBackupLocation'], rtc_new_file)
                if model_settings['TimeIndex'] > 0: 
                    files = [rst for rst in glob.glob(f'output/{model_settings["TimeIndex"] - 1}/**/**/{head}{partition_string}**_rst.nc', recursive=True)]
                    files.sort(key=os.path.getmtime)  
                    last_output_restart_file = files[-1]
                    tools.netcdf_append(last_output_restart_file, os.path.join('output','work',model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}')), 
                                        smt_settings['model']['exclude_from_database'])
                    # if 'DIMR_rtc_workdir' in smt_settings['model']:
                    #     last_output_rtc_file = [rtc for rtc in glob.glob('output/'+str(model_settings['TimeIndex'] - 1)+'/**/**/state_export.xml', recursive=True)][-1]
                    #     tools.remove(rtc_new_file)
                    #     tools.copy(last_output_rtc_file, rtc_new_file)                
            elif model_settings['RestartLevel'] == 2: 
                last_output_restart_file = [rst for rst in glob.glob(f'output/{model_settings["TimeIndex"] - 1}/**/**/{head}{partition_string}**_rst.nc', recursive=True)][-1]
                tools.netcdf_copy(last_output_restart_file, os.path.join('output','work',model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}')), [])   # copy all data
                if 'DIMR_rtc_workdir' in smt_settings['model']:
                    last_output_rtc_file = [rtc for rtc in glob.glob('output/'+str(model_settings['TimeIndex'] - 1)+'/**/**/state_export.xml', recursive=True)][-1]
                    tools.remove(rtc_new_file)
                    tools.copy(last_output_rtc_file, rtc_new_file)


def finalize(model_settings, smt_settings):
    """Finalize model output"""
    
    if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
        head, _ = os.path.splitext(smt_settings['model']['input'])
        partition_total, _ = get_partition_total(smt_settings)
        
        for partition_number in range(partition_total): 
            if partition_total == 1: 
                partition_string = '' 
            else: 
                partition_string = f'_{partition_number:04}'

            # backup restart file to local database
            try: 
                files = glob.glob(f'output/work/{model_settings["DIMR_dflowfm_workdir"]}/{model_settings["OutputDir"]}/{head}{partition_string}_{model_settings["RestartDateTimeStop"]}_rst.nc', recursive=True)
                #files.sort(key=os.path.getmtime)
                restart_file_database = files[0]  # get last restart time
            except: 
                logger.error('Check output/work folder for error message')
                raise IndexError
            tools.netcdf_copy(restart_file_database, model_settings['RestartFileToBackupLocation'].replace(head, f'{head}{partition_string}'),  
                smt_settings['model']['exclude_from_database'])
            if 'DIMR_rtc_workdir' in smt_settings['model']:
                rtc_file = [rtc for rtc in glob.glob('output/work/**/**/state_export.xml', recursive=True)][-1]
                tools.copy(rtc_file, model_settings['RTCFileToBackupLocation'])

def get_partition_total(smt_settings): 
    # get total number of partitions
    if 'nNodes' in smt_settings['variables']['user'].keys(): 
        if 'nProc' in smt_settings['variables']['user'].keys(): 
            partition_total = smt_settings['variables']['user']['nNodes']*smt_settings['variables']['user']['nProc']
            processes_string = ' '.join([str(j) for j in range(partition_total)])
    else: 
        partition_total = 1
        processes_string = '0'
    return partition_total, processes_string



def partition_path_exists(restartfile, head, partition_total): 
    path_exists_list = []
    for partition_number in range(partition_total): 
        if partition_total == 1: 
            partition_string = '' 
        else: 
            partition_string = f'_{partition_number:04}'
        if not os.path.exists(restartfile.replace(head, f'{head}{partition_string}')): 
            return False
    return True
        
