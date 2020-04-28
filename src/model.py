"""Module for model adaption"""

import os
import glob
import logging
import logging.config
from mako.template import Template
from collections import OrderedDict

# create logger
head, tail = os.path.split(__file__)
logging.config.fileConfig(os.path.join(head,'logging.conf'))
logger = logging.getLogger('SMT')

def adapt(model_settings):
    reserved_keys = ['TStart', 'TStop', 'MapInterval', 'RstInterval', 'MorStt', 'Tlfsmo']
    
    filename_settings = model_settings.copy()
    for key in reserved_keys: 
        filename_settings.pop(key, None)
    file_append = '_' + '_'.join(filename_settings.values())
    model_settings['FileAppendix'] = file_append
    
    logger.info('Starting adaptation of source folder')
    
    for item in glob.glob('**', recursive=True):
        if os.path.isfile(item): 
            head, tail = os.path.split(item)
            if (tail.find('.template') > 0) and not (head.find('source') > -1): 
                filename = tail.replace('.template','')
                file_head, file_ext = os.path.splitext(filename)
                if not file_ext == '.mdu': 
                    filename_new = ''.join([file_head, file_append, file_ext])
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
