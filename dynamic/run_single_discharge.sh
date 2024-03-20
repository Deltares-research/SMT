#!/bin/bash 

# Load modules 
module load intelmpi/21.2.0

./run_dimr_parallel.sh
 
# Unload modules 
module unload intelmpi/21.2.0 
