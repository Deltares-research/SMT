"""Module for model adaption"""

import os
import glob
from mako.template import Template
from collections import OrderedDict
import yaml
import tools

global logger 

# create logger
logger = tools.init_logger()

def read(settings):
    # Read yaml settings file and return dictionary with SMT settings
    logger.info('Initialising run')
    logger.info(f'Reading {settings} ...')

    try:
        smt_settings = yaml.load(open(settings, 'r'))
    except yaml.YAMLError as exc:
        logging.error(f'Error in SMT settings file: {exc}')
        logger.info('')
        logger.info(f'Parsed settings file: {settings}\n#---start of file ---\n {yaml.dump(smt_settings)}#---end of file ---')
        raise exc

    logger.info('')
    logger.info(f'Parsed settings file: {settings}\n#---start of file ---\n {yaml.dump(smt_settings)}#---end of file ---')
    return smt_settings

def validate(smt_settings):
    # Validate SMT settings dictionary
    logger.info('')
    logger.info('Found the following automatic variables:')
    auto_vars = []
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
    #logger.info('')

    simulation_types = ['quasi-steady-hydrograph']
    tools.logger_assert(smt_settings['model']['simulation_type'] in simulation_types, f'simulation_type should be one of {simulation_types}')


    #logger.critical('ending here')
    #sys.exit(0)

def set_input(smt_settings, time_index):
    smt_user = smt_settings['variables']['user']
    user_vars = []
    for var in smt_user: 
        user_vars.append(var)

    if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
        dependance_map = {} 
        model_settings = {}
        for key in user_vars: 
            value = smt_user[key]
            if key in list(model_settings.keys()):
                continue
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
    else: 
        logger.error('simulation_type not implemented')
        raise NotImplementedError

    reserved_keys = list(smt_settings['variables']['automatic'].keys())
    
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

        #try: 
        #except: 
        #    logger.info(f'{key}: not set')
        #    pass     
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
    
            model_settings['TStart'] = time_start
            model_settings['TStop'] = time_start + model_settings['TimeDuration']
            model_settings['MapInterval'] = model_settings['TimeDuration']
            model_settings['RstInterval'] = model_settings['TimeDuration']
        
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
