#!/bin/bash

# A little bit of scripting magic so that whatever directory this script is
# run from, we always find the python scripts and data we need.
cd "$(dirname "$0")"
cwd=`pwd`/..
cd ${cwd}

# Activate python virtual environment
source ../../../../virtualenv/bin/activate

# Now do some work

# Randomly split a library into two parts, taking only spectra at SNR/pixel 100
python3 rearrange.py --input-library 4fs_demo_stars_lrs[SNR=100] \
                     --output-library tmp_sample_A_lrs \
                     --output-library tmp_sample_B_lrs \
                     --output-fraction 0.25 --output-fraction 0.75

# Contaminate a library with 10% of the Sun's light
python3 rearrange.py --input-library 4fs_demo_stars_lrs[SNR=100] \
                     --contamination-library 4fs_demo_stars_lrs[Starname=Sun,SNR=100] \
                     --contamination-fraction 0.1 \
                     --output-library polluted_demo_stars

# Randomly split a library into two parts, taking only spectra at SNR/pixel 100, and contaminating the stars such that 10% of the photons are from the Sun's spectrum
python3 rearrange.py --input-library 4fs_ges_dwarf_sample_lrs[SNR=100] \
                     --contamination-library 4fs_demo_stars_lrs[Starname=Sun,SNR=100] \
                     --contamination-fraction 0.1 \
                     --output-library tmp_ges_dwarf_A_lrs \
                     --output-library tmp_ges_dwarf_B_lrs \
                     --output-fraction 0.25 --output-fraction 0.75

# Contaminate a library of spectra with 1% of the Sun's light
python3 rearrange.py --input-library 4fs_ges_dwarf_sample_lrs[SNR=100] \
                     --contamination-library 4fs_demo_stars_lrs[Starname=Sun,SNR=100] \
                     --contamination-fraction 0.01 \
                     --output-library polluted_ges_dwarf_sample_lrs

# Randomly split a library into two parts, taking only spectra at SNR/pixel 100
python3 rearrange.py --input-library turbospec_galah_wm \
                     --output-library turbospec_galah_wm_training_sample \
                     --output-library turbospec_galah_wm_test_sample \
                     --output-fraction 0.25 --output-fraction 0.75

