#!/bin/bash

# This script runs all of the various scripts in this git repository.

# It is provided for two reasons: firstly it demonstrates the correct command-line syntax for running each script.
# Secondly, it is useful as a test. If all the scripts below complete without error, then everything is working.

# Activate python virtual environment
source ../virtualenv/bin/activate

# Make sure we've got the latest version of the 4GP libraries installed in virtual environment
cd ../4most-4gp/src/pythonModules/fourgp_speclib
python setup.py install
cd ../fourgp_cannon
python setup.py install
cd ../fourgp_degrade
python setup.py install
cd ../fourgp_rv
python setup.py install
cd ../fourgp_specsynth
python setup.py install
cd ../fourgp_telescope_data
python setup.py install
cd ../fourgp_fourfs
python setup.py install

# Do unit testing
cd ../fourgp_speclib/fourgp_speclib/tests
python -m unittest discover -v

# Wipe our temporary workspace
cd ../../../../../../4most-4gp-scripts
mkdir -p workspace
rm -Rf workspace/*

# Import test spectra
cd import_grids/
python import_brani_grid.py
python import_apokasc.py

# Count number of CPU cores. This tell us how many copies of TurboSpectrum we can run at once.
n_cores_less_one=`cat /proc/cpuinfo | awk '/^processor/{print $3}' | tail -1`
n_cores=$((${n_cores_less_one} + 1))

# Synthesize test spectra
cd ../synthesize_grids/
create="--create"  # Only create clean SpectrumLibrary in first thread
for item in `seq 0 ${n_cores_less_one}`
do
python synthesize_test.py --every ${n_cores} --skip ${item} ${create} &
sleep 2  # Wait 2 seconds before launching next thread, to check SpectrumLibrary has appeared
create="--no-create"
done
wait

# Synthesize APOKASC test set
create="--create"  # Only create clean SpectrumLibrary in first thread
for item in `seq 0 ${n_cores_less_one}`
do
python synthesize_apokasc.py --output-library APOKASC_testset_turbospec \
                             --star-list ../../4MOST_testspectra/testset_param.tab \
                             --every ${n_cores} --skip ${item} ${create} &
sleep 2  # Wait 2 seconds before launching next thread, to check SpectrumLibrary has appeared
create="--no-create"
done
wait

# Synthesize APOKASC training set
create="--create"  # Only create clean SpectrumLibrary in first thread
for item in `seq 0 ${n_cores_less_one}`
do
python synthesize_apokasc.py --output-library APOKASC_trainingset_turbospec \
                             --star-list ../../4MOST_testspectra/trainingset_param.tab \
                             --every ${n_cores} --skip ${item} ${create} &
sleep 2  # Wait 2 seconds before launching next thread, to check SpectrumLibrary has appeared
create="--no-create"
done
wait

# Test RV determination
cd ../test_rv_determination
# python rv_test.py &> /tmp/rv_test_out.txt

# Test Cannon
# cd ../test_cannon_degraded_spec/
# 
# python cannon_test.py --train APOKASC_trainingset_HRS --test testset_HRS \
#                       --output-file /tmp/cannon_test_hrs
# 
# python cannon_test.py --train APOKASC_trainingset_HRS --test testset_HRS \
#                       --censor ../../4MOST_testspectra/ges_master_v5.fits \
#                       --output-file /tmp/cannon_test_hrs_censored
# 
# python cannon_test.py --train APOKASC_trainingset_LRS --test testset_LRS \
#                       --output-file /tmp/cannon_test_lrs
# 
# python cannon_test.py --train APOKASC_trainingset_LRS --test testset_LRS \
#                       --censor ../../4MOST_testspectra/ges_master_v5.fits \
#                       --output-file /tmp/cannon_test_lrs_censored

