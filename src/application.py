"""Module containing Application Class"""

#load libraries
import os
#from subprocess import run, 
from subprocess import Popen, PIPE, STDOUT, CompletedProcess, CalledProcessError

#load modules
import tools 

global logger 

# create logger
logger = tools.init_logger()

def log_subprocess_output(pipe):
    # function to pass stdout to logger 
    for line in iter(pipe.readline, b''): # b'\n'-separated lines
        logger.debug('%s', line.decode().replace('\r\n',''))

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
        if run_entry != None: 
            command.append(run_entry)
        logger.info('Simulation starting')
        logger.info(' '.join(command))
        process = Popen(command, stdout=PIPE, stderr=STDOUT)
        with process.stdout:
            log_subprocess_output(process.stdout)
        exitcode = process.wait() # 0 means success
        #process = run(command, capture_output=True)
        #if exitcode != 0: 
        #    raise CalledProcessError
        logger.info('Simulation finished')
        os.chdir('..')

