"""Module containing Application Class"""

#load libraries
import os
from subprocess import call

#load modules
import tools 

global logger 

# create logger
logger = tools.init_logger()

class Application():
    """Class for Application"""

    def __init__(self, **kwargs):
        """Initialisation routine for Application Class"""
        self.run_script = kwargs.get('run_script', '')
        self.prep_script = kwargs.get('prep_script', '')

    def __str__(self):
        return '\n'.join(['Application class', 
                          'run_script:' + self.run_script, 
                          'prep_script:' + self.prep_script, 
                          ])

    def prep(self, workdir, prep_entry):
        """Preparation routine for Application Class"""
        print(' '.join([self.prep_script, prep_entry]))

    def run(self, workdir, run_entry):
        """Running routine for Application Class"""
        os.chdir(workdir)
        print(' '.join([self.run_script, run_entry]))
        call([self.run_script, run_entry])
        os.chdir('..')

