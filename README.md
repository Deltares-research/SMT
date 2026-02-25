# Simulation Management Tool v1.0 (Delft3D4)
The Simulation Management Tool (SMT) is a Python program for running 
- quasi steady hydrograph simulations usinf Delft3D 4

## Background 

It was first developed in the context of the sustainable fairway in the Rhine [1], and provided a manner to run morphodynamic simulations using a quasi-steady approach using Delft3D 4. 

## Contents
adaptsrc.py  - Adapts source files to perform a multi-discharge simulation 
runsim.py    - Top level file to run simulation 
run.py       - Run scripts library and tools 
grid.py      - Load and write grid files  
dep.py       - Read/write Delft3D-FLOW *.dep files 