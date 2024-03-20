#!/bin/bash 
qsub -cwd -q test-c7 -N SMT ./run_single_discharge.sh

