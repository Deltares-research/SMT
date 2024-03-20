#!/bin/bash 
qsub -cwd -q normal-e3-c7 -N SMT ./run_single_discharge.sh

