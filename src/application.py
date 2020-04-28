"""Module containing Application Class"""

import os
import logging
import logging.config
from subprocess import call

# create logger
head, tail = os.path.split(__file__)
logging.config.fileConfig(os.path.join(head,'logging.conf'))
logger = logging.getLogger('SMT')

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

