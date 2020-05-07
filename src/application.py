"""Module containing Application Class"""

#load libraries
import os
from subprocess import run, CompletedProcess, CalledProcessError

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
        self.run_flags = kwargs.get('run_flags', '')

    def __str__(self):
        return '\n'.join(['Application class', 
                          'run_script:' + self.run_script, 
                          'run_flags:' + self.run_flags, 
                          'prep_script:' + self.prep_script, 
                          ])

    def prep(self, workdir, prep_entry):
        """Preparation routine for Application Class"""
        print(' '.join([self.prep_script, prep_entry]))

    def run(self, workdir, run_entry):
        """Running routine for Application Class"""
        os.chdir(workdir)
        command = self.run_script.copy()
        if self.run_flags != None: 
            for flag in self.run_flags: 
                command.append(flag)
        command.append(run_entry)
        logger.info('Simulation starting')
        logger.info(' '.join(command))
        process = run(command, capture_output=True)
        if process.returncode != 0: 
            raise CalledProcessError
        logger.info('Simulation finished')
        os.chdir('..')

