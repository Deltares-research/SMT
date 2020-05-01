"""Module containing helper tools for SMT"""

import sys
import os
import logging
import logging.config
import glob

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
    logger.info('Copying ' + src + ' to ' + trgt + ' ...')
    if os.name == 'nt':
        os.system('copy /Y ' + src + ' ' + trgt)
    elif os.name == 'posix':
        os.system('cp -R ' + src + ' ' + trgt)
    else:
        logger.error('Copy statement not implemented for OS "' + os.name + '"')
        #os._exit(1)

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
    if not os.path.exists(mydir):
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

