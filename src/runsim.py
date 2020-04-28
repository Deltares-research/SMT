# load libraries 
import click
import logging
import logging.config
import os
import sys 
import yaml

# optional, TODO: clean up
#import collections
#from collections import OrderedDict
#from pprint import pprint

#load modules
import tools
import model
from application import Application

# TODO: print module version info
def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo('SMT version 2.0.1')  #TODO set version number
    click.echo('')
    click.echo('Dependencies: ')
    click.echo(f'click : {click.__version__}')
    click.echo(f'logging: {logging.__version__}')
    #click.echo(f'os: {os.__version__}')
    click.echo(f'yaml: {yaml.__version__}')  
    ctx.exit()


@click.command()
@click.option('-v', '--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True, help='Print version information')
@click.option('-s', '--settings', default='smt.yml', help='SMT settings YAML file')
def runner(settings): 
    # create logger
    head, tail = os.path.split(__file__)
    logging.config.fileConfig(os.path.join(head,'logging.conf'))
    logger = logging.getLogger('SMT')
    
    logger.info('Initialising run')
    logger.info('Reading smt.yml ...')
    try:
        smt_settings = yaml.load(open(settings, 'r'))
    except yaml.YAMLError as exc:
        logging.error("Error in SMT settings file: " + exc)
    
    # TODO: Check uniqueness of variables
    
    logger.info('\n' + yaml.dump(smt_settings))
    #logger.critical('ending here')
    #sys.exit(0)
    
    model_settings = {}
    model_settings['Discharge'] = '7000'
    model_settings['TStart'] = '0'
    model_settings['TStop'] = '1200'
    model_settings['MapInterval'] = '1200'
    model_settings['RstInterval'] = '1200'
    
    tools.guaranteedir('work')
    tools.copy('source','work')
    model.adapt(model_settings)
    tools.remove('work/**.template')
    
    app = Application(run_script=r'd:\source\D-SMT-co\src\app\dflowfm_interactor\start_dflowfm_autostartstop.bat')
    app.run('work','simplechannel.mdu')

if __name__ == '__main__':
    runner()