# load libraries 
import click
import logging
import glob 
import mako
import os
import platform
import sys 
import netCDF4
import yaml 
import shutil

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
    click.echo('--dependencies---')
    click.echo(f'click : {click.__version__}')
    click.echo(f'logging: {logging.__version__}')
    click.echo(f'mako: {mako.__version__}')  
    click.echo(f'netCDF4: {netCDF4.__version__}')  
    click.echo(f'yaml: {yaml.__version__}')  
    ctx.exit()



@click.command()
@click.option('-v', '--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True, help='Print version information')
@click.option('-s', '--settings', default='smt.yml', help='SMT settings YAML file (default = smt.yml)')
@click.option('-c', '--clean', is_flag=True, help='Flag indicating whether previous output should be cleaned')
def runner(settings, clean): 
    # create logger
    logger = tools.init_logger()

    # read input 
    smt_settings = model.read(settings)

    # check input 
    model.validate(smt_settings)

    # clean previous simulation 
    if clean: 
        logger.info(f'Cleaning previous output')
        if os.path.exists('output'):
            shutil.rmtree('output')

    tools.guaranteedir('central_database')
    tools.guaranteedir('local_database')

    # get model input 
    for model_settings in model.get_input(smt_settings): 
        # check if previous output exists 
        new_output_folder = os.path.join('output', str(model_settings['TStop']))
        if os.path.exists(new_output_folder): 
            logger.info(f'Output folder {new_output_folder} exists, skipping ...')
            continue

        # apply input 
        if os.path.exists('work'):
            shutil.rmtree('work')
        shutil.copytree('source','work')
        model.adapt(model_settings, smt_settings)
        tools.remove(os.path.join('work','**.template'))
   
        # run model
        platform_system = platform.system()
        app = Application(run_script=smt_settings['application']['command'][platform_system])
        app.run('work', smt_settings['model']['input'])

        # model.finalize(model_settings, smt_settings)
        # backup restart file 
        restart_file = [rst for rst in glob.glob('work**/**/**_rst.nc', recursive=True)][-1]
        #logger.info(f'Found {restart_file}')
        tools.copy(restart_file, model_settings['RestartFileBackup'])
        # finalize model 
        tools.guaranteedir('output')
        shutil.copytree('work', new_output_folder)

if __name__ == '__main__':
    runner()