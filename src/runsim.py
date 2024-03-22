# load libraries 
import click
import logging
import glob 
import mako
import os
import platform
import sys 
import yaml 
import shutil

#load modules
import tools
import model
from application import Application

def print_version(ctx, param, value):
    import netCDF4
    if not value or ctx.resilient_parsing:
        return
    click.echo('SMT version 2.0.' + '$Revision$'.split(' ')[1])
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
@click.option('-c', '--clean', is_flag=True, help='Flag indicating whether previous output and local_database should be cleaned')
@click.option('-b', '--backup', is_flag=True, help='Flag indicating whether central_database should be replaced by local_database')
def runner(settings, clean, backup): 
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
        if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
            logger.info(f'Removing local_database')
            if os.path.exists('local_database'):
                shutil.rmtree('local_database')
        logger.info(f'Finished cleaning previous output')
        exit()

    if backup: 
        if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
            shutil.copytree('local_database', 'central_database')
        exit()

    if smt_settings['model']['simulation_type'] == 'quasi-steady-hydrograph':
        tools.guaranteedir('central_database')
        tools.guaranteedir('local_database')
        tools.guaranteedir('output')

    # get model input 
    for model_settings in model.get_input(smt_settings): 
        # check if output exists from previous run
        new_output_folder = os.path.join('output', str(model_settings['TimeIndex']))
        if os.path.exists(new_output_folder): 
            logger.info(f'Output folder {new_output_folder} exists, skipping ...')
            continue

        # apply input 
        if os.path.exists(os.path.join('output','work')):
            shutil.rmtree(os.path.join('output','work'))
        shutil.copytree('dynamic',os.path.join('output','work'))
        model.adapt(model_settings, smt_settings)
        tools.remove(os.path.join('output','work','**','**.template'))
   
        # run model step
        platform_system = platform.system()
        app = Application(run_script=smt_settings['application']['command'][platform_system],
                          run_flags=smt_settings['application']['flags'][platform_system])
        app.run(os.path.join('output','work'), smt_settings['model']['input'])

        # finalize model step
        model.finalize(model_settings, smt_settings)
        shutil.move(os.path.join('output','work'), new_output_folder)


if __name__ == '__main__':
    runner()