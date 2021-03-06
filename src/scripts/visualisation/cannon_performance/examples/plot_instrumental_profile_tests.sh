#!/bin/bash

# Produce plots of the precision of labels as a function of the instrumental profile they were convolved with

# ---

# A little bit of scripting magic so that whatever directory this script is
# run from, we always find the python scripts and data we need.
cd "$(dirname "$0")"
cwd=`pwd`/..
cd ${cwd}

# Activate python virtual environment
source ../../../../../virtualenv/bin/activate

for kernel in gaussian half_ellipse
do
    for mode in hrs lrs
    do
        for snr in 20 50
        do
            for script in offset_rms.py offset_box_and_whisker.py
            do
                python3 ${script} \
                --cannon-output ../../../../output_data/cannon/cannon_galah_${kernel}_all_censored_${mode}_10label_snr${snr} \
                --abscissa convolution \
                --output ../../../../output_plots/cannon_performance/instrumental_profile_tests/${kernel}_${mode}_10label_snr${snr} \
                &
            done
            wait
        done
    done
done
