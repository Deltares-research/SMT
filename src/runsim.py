# load libraries 
import click
import logging
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
    click.echo(f'yaml: {yaml.__version__}')  
    ctx.exit()


@click.command()
@click.option('-v', '--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True, help='Print version information')
@click.option('-s', '--settings', default='smt.yml', help='SMT settings YAML file')
def runner(settings): 
    # create logger
    logger = tools.init_logger()

    # read input 
    smt_settings = model.read(settings)

    # check input 
    model.validate(smt_settings)

    # get model input 
    for model_settings in model.get_input(smt_settings): 
        # apply input 
        tools.guaranteedir('work')
        tools.copy('source','work')

        print(model_settings)
        
        model.adapt(model_settings, smt_settings)
        tools.remove('work/**.template')
   
        # run model
        app = Application(run_script=smt_settings['application']['command'])
        app.run('work', 'simplechannel.mdu')

        # finalize model 
        tools.guaranteedir('work')
        tools.move('work', str(model_settings['TStop']))

if __name__ == '__main__':
    runner()