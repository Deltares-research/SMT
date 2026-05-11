# load libraries 
import click
import logging
import glob 
import mako
import os
import platform
import sys 
import scipy
import yaml 
import shutil

#load modules
import tools
import model
from application import Application

def print_version(ctx, param, value):
    import netCDF4
    import subprocess
    import importlib
    if not value or ctx.resilient_parsing:
        return
    try:
        git_version = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        git_version = 'unknown'
    # Versioning follows semantic versioning: https://semver.org/ - major.minor.patch
    # MAJOR version when you make incompatible API changes
    # MINOR version when you add functionality in a backward compatible manner
    # PATCH version when you make backward compatible bug fixes
    click.echo(f'SMT version 2.2.2 (git commit: {git_version})')

    # Print versions of dependencies
    click.echo('--dependencies---')
    click.echo(f'click : {importlib.metadata.version("click")}')
    click.echo(f'logging: {logging.__version__}')
    click.echo(f'mako: {mako.__version__}')  
    click.echo(f'netCDF4: {netCDF4.__version__}')  
    click.echo(f'yaml: {yaml.__version__}')  
    # Optional dependency - used for refplane.py
    try:
        import scipy
        click.echo(f'scipy: {scipy.__version__}')
    except ImportError as e:
        pass
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
        # apply input 
        if os.path.exists(os.path.join('output','work')):
            shutil.rmtree(os.path.join('output','work'))
        shutil.copytree('source',os.path.join('output','work'))
        model.adapt(model_settings, smt_settings)
        tools.remove(os.path.join('output','work','**','**.template'))
   
        # run model step
        platform_system = platform.system()
        app = Application(run_script=smt_settings['application']['command'][platform_system],
                          run_flags=smt_settings['application']['flags'][platform_system])
        app.run(os.path.join('output','work'), smt_settings['model']['input'])

        # finalize model step
        model.finalize(model_settings, smt_settings)
        shutil.move(os.path.join('output','work'), model_settings['OutputFolder'])


if __name__ == '__main__':
    runner()