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

    # check if output exists from previous run
    model_settings['ContinuationRun'] = False
    model_settings['OutputFolder'] = os.path.join('output', str(model_settings['TimeIndex']))
    if os.path.exists(model_settings['OutputFolder']): 
        model_settings['ContinuationRun'] = True
        return model_settings

    if 'NODES' in os.environ.keys() and 'TASKS_PER_NODE' in os.environ.keys():
        model_settings['nNodes'] = os.environ['NODES']
        model_settings['nProc'] = os.environ['TASKS_PER_NODE']
    else:
        logger.info(f'Setting NODES=1 and TASKS_PER_NODE=1')
        logger.info(f'For different settings, set these as environment variables e.g.:')
        logger.info(f'$ export NODES=1 (on linux)')
        logger.info(f'$ set NODES=1 (on Windows)')
        model_settings['nNodes'] = 1
        model_settings['nProc'] = 1
    if 'nNodesManual' in model_settings.keys(): 
        if model_settings['nNodesManual'] is not None: 
            model_settings['nNodes'] = model_settings['nNodesManual']
    if 'nProcManual' in model_settings.keys(): 
        if model_settings['nProcManual'] is not None: 
            model_settings['nProc'] = model_settings['nProcManual']
    model_settings['Partitions'] = int(model_settings['nNodes'])*int(model_settings['nProc'])

    processes_string, partition_string = get_partition_total(model_settings['Partitions'])
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
        if model_settings is None:
            continue
        if model_settings['ContinuationRun']: 
            logger.info(f'Output folder output/{model_settings["TimeIndex"]} exists, skipping ...')
            # increase counter 
            time_index += 1

            # Read tstart from qsh.yml if it exists
            qsh_file = os.path.join('output', str(model_settings["TimeIndex"]), 'qsh.yml')
            if os.path.exists(qsh_file):
                with open(qsh_file, 'r') as f:
                    qsh_data = yaml.load(f, Loader=yaml.SafeLoader)
                    if qsh_data and 'TStop' in qsh_data:
                        time_start = qsh_data['TStop']
                        logger.info(f'Loaded TStart from {qsh_file}: {time_start}')            
            continue

        if model_settings != None: 
            processes_string, partition_string = get_partition_total(model_settings['Partitions'])
            logger.debug('Variables updated ...')
            for key in model_settings.keys():   
                logger.debug(f'{key}: {model_settings[key]}')

            if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
                head, _ = os.path.splitext(smt_settings['model']['input'])
                file_append = model_settings['FileAppendix']

                # Set default names
                restart_file_database = f'{head}{file_append}_rst.nc'
                model_settings['RstIgnoreBl'] = 0
                if 'DIMR_dflowfm_workdir' in smt_settings['model']:
                    restart_file_database = os.path.join(smt_settings['model']['DIMR_dflowfm_workdir'],
                                                         restart_file_database)
                if 'DIMR_rtc_workdir' in smt_settings['model']:
                    if 'RTC_input_file' not in model_settings.keys():
                        model_settings['RTC_input_file'] = 'state_import.xml'
                    if 'RTC_output_file' not in model_settings.keys():
                        model_settings['RTC_output_file'] = 'state_export.xml'
                    rtc_file_base, rtc_file_ext = os.path.splitext(model_settings['RTC_input_file'])
                    rtc_file = f'{rtc_file_base}{file_append}{rtc_file_ext}'
                    rtc_file_location = os.path.join(smt_settings['model']['DIMR_rtc_workdir'],
                                                     rtc_file)
                # Ignore database option
                if smt_settings['model']['load_from_database'] == False: 
                    logger.info('Cold startup - (neglecting restart information)')
                    model_settings['RestartFileFromBackupLocation'] = '' # None ?
                    model_settings['RestartFileToBackupLocation'] = os.path.join('local_database',
                                                                                 restart_file_database)
                    if 'DIMR_rtc_workdir' in smt_settings['model']:
                        model_settings['RTCFileLocation'] = rtc_file_location
                        model_settings['RTCFileFromBackupLocation'] = model_settings['RTC_initial_state']
                        model_settings['RTCFileToBackupLocation'] = os.path.join('local_database',
                                                                                 rtc_file_location)
                    restart_level = 3
                
                # Local database information exists/
                elif partition_path_exists(os.path.join('local_database',restart_file_database), head, model_settings['Partitions']):
                    logger.info('Restart file found in local_database')
                    model_settings['RestartFileFromBackupLocation'] = os.path.join('local_database',
                                                                                   restart_file_database)
                    model_settings['RestartFileToBackupLocation'] = os.path.join('local_database',
                                                                                 restart_file_database)
                    if time_index == 0: 
                        model_settings['RstIgnoreBl'] = 1
                    if 'DIMR_rtc_workdir' in smt_settings['model']:
                        model_settings['RTCFileLocation'] = rtc_file_location
                        model_settings['RTCFileFromBackupLocation'] = os.path.join('local_database',
                                                                                   rtc_file_location)
                        model_settings['RTCFileToBackupLocation'] = os.path.join('local_database',
                                                                                 rtc_file_location)
                    restart_level = 0
                else: 
                    # Local database does not exist and central database does
                    if partition_path_exists(os.path.join('central_database',restart_file_database), head, model_settings['Partitions']):
                        logger.info('Restart file found in central_database')
                        model_settings['RestartFileFromBackupLocation'] = os.path.join('central_database',
                                                                                       restart_file_database)
                        model_settings['RestartFileToBackupLocation'] = os.path.join('local_database',
                                                                                     restart_file_database)
                        if time_index == 0: 
                            model_settings['RstIgnoreBl'] = 1
                        if 'DIMR_rtc_workdir' in smt_settings['model']:
                            model_settings['RTCFileLocation'] = rtc_file_location
                            model_settings['RTCFileFromBackupLocation'] = os.path.join('central_database',
                                                                                       rtc_file_location)
                            model_settings['RTCFileToBackupLocation'] = os.path.join('local_database',
                                                                                     rtc_file_location)
                        restart_level = 1
                    else: 
                        # Local database and central database do not exist
                        logger.info('Restart file not found in central_database')
                        if time_index > 0:
                            # If this is not the first step, restart from the previous result
                            logger.info('Starting from final result of last simulation')
                            model_settings['RestartFileFromBackupLocation'] = '' 
                            model_settings['RestartFileToBackupLocation'] = os.path.join('local_database',
                                                                                         restart_file_database)
                            if 'DIMR_rtc_workdir' in smt_settings['model']:
                                model_settings['RTCFileLocation'] = rtc_file_location
                                model_settings['RTCFileFromBackupLocation'] = ''
                                model_settings['RTCFileToBackupLocation'] = os.path.join('local_database',
                                                                                         rtc_file_location)
                            restart_level = 2
                            # All Initial field information follows from previous restart, so do not use IniFieldFile
                            if 'IniFieldFile' in model_settings.keys(): 
                                model_settings['IniFieldFile'] = ''                             
                        else:
                            # If this is the first step, do not restart from any database. 
                            logger.info('Cold startup')
                            model_settings['RestartFileFromBackupLocation'] = '' # None ?
                            model_settings['RestartFileToBackupLocation'] = os.path.join('local_database',
                                                                                         restart_file_database)
                            if 'DIMR_rtc_workdir' in smt_settings['model']:
                                model_settings['RTCFileLocation'] = rtc_file_location
                                model_settings['RTCFileFromBackupLocation'] = model_settings['RTC_initial_state'] 
                                model_settings['RTCFileToBackupLocation'] = os.path.join('local_database',
                                                                                         rtc_file_location)
                            restart_level = 3
                model_settings['RestartLevel'] = restart_level        
                model_settings['SpinupTime'] = model_settings['SpinupTime'][restart_level]
                model_settings['TStart'] = time_start
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
                if 'MapOutputCount' not in model_settings.keys():
                    model_settings['MapOutputCount'] = 1
                if 'Dtfacmax' not in model_settings.keys():
                    model_settings['Dtfacmax'] = 1.1     
                if 'TStartTlfsmo' not in model_settings.keys():
                    model_settings['TStartTlfsmo'] = time_start
                if 'Tlfsmo' not in model_settings.keys():
                    model_settings['Tlfsmo'] = 0.0
                if 'UseTlfsmo' not in model_settings.keys():
                    model_settings['UseTlfsmo'] = 2
                if 'morphopol' not in model_settings.keys():
                    model_settings['morphopol'] = '' 
                if 'InMorphoPol' not in model_settings.keys():
                    model_settings['InMorphoPol'] = '1'
                if 'cstbnd' not in model_settings.keys():
                    model_settings['cstbnd'] = '0' 
                if 'AngLat' not in model_settings.keys():
                    model_settings['AngLat'] = '52.' 
                if 'OLA_Discharge' not in model_settings.keys():
                    model_settings['OLA_Discharge'] = '-999' 
                if 'UpdateRefplane' not in model_settings.keys():
                    model_settings['UpdateRefplane'] = '0' 
                if 'RefplaneFile' not in model_settings.keys():
                    model_settings['RefplaneFile'] = '' 
                if 'MapFormat' not in model_settings.keys():
                    model_settings['MapFormat'] = '4'                    # Map file format, 1: netCDF, 2: Tecplot, 3: netCFD and Tecplot, 4: NetCDF-UGRID
                if 'NcFormat' not in model_settings.keys():
                    model_settings['NcFormat'] = '3'                     # Format for all NetCDF output files (3: classic, 4: NetCDF4+HDF5)
                if 'NcMapDataPrecision' not in model_settings.keys():
                    model_settings['NcMapDataPrecision'] = 'double'      # Precision for NetCDF data in map files (double or single)
                if 'NcHisDataPrecision' not in model_settings.keys():
                    model_settings['NcHisDataPrecision'] = 'double'      # Precision for NetCDF data in his files (double or single)
                if 'NcCompression' not in model_settings.keys():
                    model_settings['NcCompression'] = '0'                # Whether or not (1/0) to apply compression to NetCDF output files - NOTE: only works when NcFormat = 4
                if 'ExtForceFile' not in model_settings.keys(): 
                    model_settings['ExtForceFile'] = ''        
                if 'IALDiff' not in model_settings.keys(): 
                    model_settings['IALDiff'] = '0'                      # [ - ] Whether or not (1/0) to apply diffusion in the active layer model
                if 'ALDiff' not in model_settings.keys(): 
                    model_settings['ALDiff'] = ''                        # [ - ] Whether or not (1/0) to apply diffusion in the active layer model
                if 'UseCaching' not in model_settings.keys(): 
                    model_settings['UseCaching'] = '1'        
                if 'Wrishp_crs' not in model_settings.keys():  # cross sections 
                    model_settings['Wrishp_crs'] = '0'
                if 'Wrishp_obs' not in model_settings.keys():  # observation stations 
                    model_settings['Wrishp_obs'] = '0'
                if 'Wrishp_weir' not in model_settings.keys():  # weirs 
                    model_settings['Wrishp_weir'] = '0'
                if 'Wrishp_thd' not in model_settings.keys():  # thin dams 
                    model_settings['Wrishp_thd'] = '0'
                if 'Wrishp_gate' not in model_settings.keys():  # gates 
                    model_settings['Wrishp_gate'] = '0'
                if 'Wrishp_fxw' not in model_settings.keys():  # fixed weirs 
                    model_settings['Wrishp_fxw'] = '0'
                if 'Wrishp_src' not in model_settings.keys():  # source-sinks 
                    model_settings['Wrishp_src'] = '0'
                if 'Wrishp_pump' not in model_settings.keys():  # pumps 
                    model_settings['Wrishp_pump'] = '0'
                if 'Wrishp_dryarea' not in model_settings.keys():  # dry areas 
                    model_settings['Wrishp_dryarea'] = '0'
                if 'Wrishp_genstruc' not in model_settings.keys():  # general structures 
                    model_settings['Wrishp_genstruc'] = '0'
                if 'WriteDFMinterpretedvalues' not in model_settings.keys():  # interpreted values 
                    model_settings['WriteDFMinterpretedvalues'] = '0'
                if 'Wrimap_waterlevel_s0' not in model_settings.keys():  # output options
                    model_settings['Wrimap_waterlevel_s0'] = '0'
                if 'circumcenterMethod' not in model_settings.keys():  # geometry options - MAASMOR-217
                    model_settings['circumcenterMethod'] = 'internalNetlinksEdge' 
                if 'circumcenterTolerance' not in model_settings.keys():  # geometry options - MAASMOR-217
                    model_settings['circumcenterTolerance'] = '1.0e-3'
                # At this point we have read the desired SpinupTime and TimeDuration of the morphodynamic activity. 
                # Now we have to find a DtUserModel which is close to the desired DtUser and allows for the setting of different DtUser related outputs
                #
                # The TimeDuration should not be altered. The total simulation time TStop-Start should be a multiple of DtUserModel
                #   DtUserModel x N = TStop-TStart
                #
                # In addition the MapIntervalStep should also be a multiple of DtUserModel
                #   DtUserModel x M = MapIntervalStep
                #
                # This implies that the TimeDuration should also be a multiple of DtUserModel
                #   DtUserModel x M x P = TimeDuration
                #
                # As a consequence the SpinUpTimeModel should be a multiple of the DtUserModel as well. 
                #   DtUserModel x Q = SpinUpTimeModel
                #
                # To obtain the DtUserModel we search for a DtUserModel which is close to the proposed DtUser in the input file. 
                maximum_DtUser = model_settings['TimeDuration']*tunit_in_seconds/model_settings['MapOutputCount']
                model_settings['DtUserModel'] = maximum_DtUser/np.ceil(maximum_DtUser/model_settings['DtUser'])
                #  
                # Next the SpinupTimeModel is increased to be a multiple of the DtUserModel
                spinup_time_seconds = np.ceil(model_settings['SpinupTime']/model_settings['DtUserModel'])*model_settings['DtUserModel']
                if model_settings['UseTlfsmo'] == 2:
                    model_settings['Tlfsmo'] = spinup_time_seconds*0.5
                if model_settings['UseTlfsmo'] == 0:
                    model_settings['Tlfsmo'] = 0.0
                model_settings['SpinupTimeModel'] = spinup_time_seconds/tunit_in_seconds
                model_settings['HisIntervalStepModel'] = np.ceil(model_settings['HisIntervalStep']/model_settings['DtUserModel'])*model_settings['DtUserModel']
                model_settings['TrtDtModel'] = model_settings['DtUserModel']

                model_settings['MorStt'] = model_settings['SpinupTimeModel']
                time_stop = time_start + model_settings['TimeDuration'] + model_settings['SpinupTimeModel']
                model_settings['TStop'] = time_stop
                refdate = datetime.strptime(model_settings['ReferenceDate'], '%Y%m%d')
                time_start_seconds = time_start*tunit_in_seconds
                time_start_post_spinup_seconds = np.round((time_start+model_settings['SpinupTimeModel'])*tunit_in_seconds,decimals=16)
                time_stop_seconds = time_stop*tunit_in_seconds
                rst_time_duration_post_spinup_seconds = np.round(float(model_settings['TimeDuration'])*tunit_in_seconds,decimals=16)
                map_time_duration_post_spinup_seconds = np.round(float(model_settings['TimeDuration'])*tunit_in_seconds/float(model_settings['MapOutputCount']),decimals=16)
                his_time_near_start = time_stop_seconds-np.floor((time_stop_seconds-time_start_seconds)/model_settings['HisIntervalStepModel'])*model_settings['HisIntervalStepModel']
                validate_output_time(map_time_duration_post_spinup_seconds, model_settings['DtUserModel'], 'MapIntervalStepModel', 'DtUserModel')
                validate_output_time(time_start_post_spinup_seconds, model_settings['DtUserModel'], 'MapIntervalStart', 'DtUserModel')
                validate_output_time(time_stop_seconds, model_settings['DtUserModel'], 'MapIntervalStop', 'DtUserModel')
                model_settings['MapInterval'] = f"{map_time_duration_post_spinup_seconds:.16f} {time_start_post_spinup_seconds:.16f} {time_stop_seconds:.16f}"
                model_settings['RstInterval'] = f"{rst_time_duration_post_spinup_seconds:.16f} {time_start_post_spinup_seconds:.16f} {time_stop_seconds:.16f}"
                model_settings['RestartDateTime'] = datetime.strftime(refdate + timedelta(seconds = np.round(time_delta_start.total_seconds())), '%Y%m%d%H%M%S')
                model_settings['RestartDateTimeStop'] = datetime.strftime(refdate + timedelta(seconds = np.round(time_stop_seconds)), '%Y%m%d_%H%M%S')
                validate_output_time(his_time_near_start, model_settings['DtUserModel'], 'HisIntervalStart', 'DtUserModel')
                model_settings['HisInterval'] = f"{model_settings['HisIntervalStepModel']:.16f} {his_time_near_start:.16f} {time_stop_seconds:.16f}"

                model_settings['RestartFile'] = ''
                model_settings['RestartFileLocation'] = '' # restart_file_database
                if restart_level < 3: 
                    restart_file_date_time_string = datetime.strftime(refdate + timedelta(seconds = np.round(time_delta_start.total_seconds())), '%Y%m%d_%H%M%S')
                    model_settings['RestartFile'] = f'{head}_{restart_file_date_time_string}_rst.nc'
                    model_settings['RestartFileLocation'] = model_settings['RestartFile']
                if 'DIMR_dflowfm_workdir' in smt_settings['model']:
                    model_settings['DIMR_dflowfm_workdir'] = smt_settings['model']['DIMR_dflowfm_workdir']
                if 'DIMR_rtc_workdir' in smt_settings['model']:
                    model_settings['DIMR_rtc_workdir'] = smt_settings['model']['DIMR_rtc_workdir']
                if 'OutputDir' in smt_settings['model']:
                    model_settings['OutputDir'] = smt_settings['model']['OutputDir']
                model_settings['FileBase'] = head

                # At the end of the loop, save time_start such that Tstart can be updated in the next iteration.
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
                logger.debug(f'Rendering {full_filename_new}')
                with open(full_filename_new, 'w') as f:                         
                    mytemplate = Template(filename=item, strict_undefined=True, input_encoding='utf-8')
                    f.write(mytemplate.render(**model_settings).replace('\r',''))
                if file_ext == '.sh': 
                    os.chmod(full_filename_new, 0o0777)
    if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
        if 'DIMR_rtc_workdir' in smt_settings['model']:
            rtc_new_file = os.path.join('output','work',smt_settings['model']['DIMR_rtc_workdir'],model_settings['RTC_input_file'])

        head, _ = os.path.splitext(smt_settings['model']['input'])
        processes_string, partition_string = get_partition_total(model_settings['Partitions'])

        with open(os.path.join('output','work','qsh.yml'), 'w') as f:
            model_settings['TStart'] = float(model_settings['TStart'])
            model_settings['TStop'] = float(model_settings['TStop'])
            yaml.dump({k: model_settings[k] for k in ['RestartLevel',
                                                      'ReferenceDate',
                                                      'TStart',
                                                      'TStop',
                                                      'RestartDateTime',
                                                      'RestartDateTimeStop']}, f)
        for partition_number in range(model_settings['Partitions']): 
            if model_settings['Partitions'] == 1: 
                partition_string = '' 
            else: 
                partition_string = f'_{partition_number:04}'

            if model_settings['RestartLevel'] < 2: 
                if 'DIMR_dflowfm_workdir' in smt_settings['model']:
                    new_restart_file = os.path.join('output',
                                                    'work',
                                                    f'{model_settings['DIMR_dflowfm_workdir']}',
                                                    f"{model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}')}")
                else:
                    new_restart_file = os.path.join('output',
                                                    'work',
                                                    f"{model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}')}")
                tools.netcdf_copy(model_settings['RestartFileFromBackupLocation'].replace(head, f'{head}{partition_string}'), 
                                  new_restart_file,
                                  smt_settings['model']['exclude_from_database'])
                if model_settings['TimeIndex'] > 0: 
                    restart_file_name = model_settings["RestartFile"].replace(head, f'{head}{partition_string}')
                    if 'DIMR_dflowfm_workdir' in smt_settings['model']:
                        last_output_restart_file = os.path.join('output', 
                                                                f'{model_settings["TimeIndex"] - 1}', 
                                                                f'{model_settings['DIMR_dflowfm_workdir']}',
                                                                f'{model_settings['OutputDir']}',
                                                                f'{restart_file_name}')
                        new_restart_file = os.path.join('output',
                                                        'work',
                                                        f'{model_settings['DIMR_dflowfm_workdir']}',
                                                        f"{model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}')}")
                    else:
                        last_output_restart_file = os.path.join('output', 
                                                                f'{model_settings["TimeIndex"] - 1}', 
                                                                f'{model_settings["OutputDir"]}',
                                                                f'{restart_file_name}')
                        new_restart_file = os.path.join('output',
                                                        'work',
                                                        f"{model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}')}")
                    tools.netcdf_append(last_output_restart_file, 
                                        new_restart_file,
                                        smt_settings['model']['exclude_from_database'])
                    # if 'DIMR_rtc_workdir' in smt_settings['model']:
                    #     last_output_rtc_file = [rtc for rtc in glob.glob('output/'+str(model_settings['TimeIndex'] - 1)+'/**/**/state_export.xml', recursive=True)][-1]
                    #     tools.remove(rtc_new_file)
                    #     tools.copy(last_output_rtc_file, rtc_new_file)                
            elif model_settings['RestartLevel'] == 2: 
                restart_file_name = model_settings["RestartFile"].replace(head, f'{head}{partition_string}')
                if 'DIMR_dflowfm_workdir' in smt_settings['model']:
                    last_output_restart_file = os.path.join('output',
                                                            f'{model_settings["TimeIndex"] - 1}',
                                                            model_settings['DIMR_dflowfm_workdir'],
                                                            model_settings['OutputDir'],
                                                            model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}')) 
                    new_restart_file = os.path.join('output',
                                                    'work', 
                                                    model_settings['DIMR_dflowfm_workdir'],
                                                    model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}'))
                else:
                    last_output_restart_file = os.path.join('output', f'{model_settings["TimeIndex"] - 1}',
                                                            model_settings['OutputDir'],
                                                            model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}')) 
                    new_restart_file = os.path.join('output',
                                                    'work', 
                                                    model_settings['RestartFileLocation'].replace(head, f'{head}{partition_string}'))

                tools.netcdf_copy(last_output_restart_file, new_restart_file, [])   # copy all data
                if 'DIMR_rtc_workdir' in smt_settings['model']:
                    last_output_rtc_file = [rtc for rtc in glob.glob('output/'+str(model_settings['TimeIndex'] - 1)+'/**/**/state_export.xml', recursive=True)][-1]
                    model_settings['RTCFileFromBackupLocation'] = last_output_rtc_file
            # Copy RTC to correct location.
            if 'DIMR_rtc_workdir' in smt_settings['model']:
                tools.remove(rtc_new_file)
                tools.copy(model_settings['RTCFileFromBackupLocation'], rtc_new_file)                            


def finalize(model_settings, smt_settings):
    """Finalize model output"""
    
    if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
        head, _ = os.path.splitext(smt_settings['model']['input'])
        processes_string, partition_string = get_partition_total(model_settings['Partitions'])

        for partition_number in range(model_settings['Partitions']): 
            if model_settings['Partitions'] == 1: 
                partition_string = '' 
            else: 
                partition_string = f'_{partition_number:04}'

            # backup restart file to local database
            if 'DIMR_dflowfm_workdir' in model_settings.keys():
                rst_file = os.path.join('output',
                                        'work',
                                        f'{model_settings["DIMR_dflowfm_workdir"]}',
                                        f'{model_settings["OutputDir"]}',
                                        f'{head}{partition_string}_{model_settings["RestartDateTimeStop"]}_rst.nc')
            else: 
                rst_file = os.path.join('output',
                                        'work',
                                        f'{model_settings["OutputDir"]}',
                                        f'{head}{partition_string}_{model_settings["RestartDateTimeStop"]}_rst.nc')

            try: 
                files = glob.glob(rst_file, recursive=True)
                #files.sort(key=os.path.getmtime)
                restart_file_database = files[0] 
            except: 
                logger.error(f'Check output/work: Cannot find restartfile {rst_file}')
                raise IndexError
            tools.netcdf_copy(restart_file_database, model_settings['RestartFileToBackupLocation'].replace(head, f'{head}{partition_string}'),  
                smt_settings['model']['exclude_from_database'])
            if 'DIMR_rtc_workdir' in smt_settings['model']:
                rtc_file = [rtc for rtc in glob.glob('output/work/**/**/state_export.xml', recursive=True)][-1]
                tools.copy(rtc_file, model_settings['RTCFileToBackupLocation'])

def get_partition_total(partition_total): 
    # get total number of partitions
    if partition_total > 1:
        processes_string = ' '.join([str(j) for j in range(partition_total)])
        partition_string = '_merged'
    else: 
        partition_total = 1
        processes_string = '0'
        partition_string = '' 
    return processes_string, partition_string


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
        
def validate_output_time(number, factor, number_description, factor_description):
    if not tools.is_multiple(number, factor):
        logger.debug(f'{number_description} = {number}')
        logger.debug(f'{factor_description} = {factor}')
        logger.debug(f'{number_description} is not a multple of {factor_description}')
        #raise ValueError(f'{number_description} is not a multple of {factor_description}')