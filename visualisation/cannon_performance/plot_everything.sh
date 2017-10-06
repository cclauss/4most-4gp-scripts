#!/bin/bash

source ../../../virtualenv/bin/activate

python scatter_plot_arrows.py --output-stub ../../output_plots/apogee_teff_logg_hrs_offset_arrows \
                              --label "Teff{5100:4000}" --label "logg{3.8:1.2}" \
                              --label-axis-latex "Teff" --label-axis-latex "log(g)" \
                              --cannon_output ../../output_data/cannon_4fs_hrs.dat

python scatter_plot_arrows.py --output-stub ../../output_plots/apogee_teff_logg_lrs_offset_arrows \
                              --label "Teff{5100:4000}" --label "logg{3.8:1.2}" \
                              --label-axis-latex "Teff" --label-axis-latex "log(g)" \
                              --cannon_output ../../output_data/cannon_4fs_lrs.dat

python mean_performance_vs_snr.py \
  --cannon-output ../../output_data/cannon_hawkins_lrs.dat --dataset-label "Hawkins LRS" \
  --cannon-output ../../output_data/cannon_hawkins_hrs.dat --dataset-label "Hawkins HRS" \
  --cannon-output ../../output_data/cannon_4fs_lrs.dat --dataset-label "Ford LRS" \
  --cannon-output ../../output_data/cannon_4fs_hrs.dat --dataset-label "Ford HRS" \
  --output-file ../../output_plots/apogee_mean_performance

python scatter_plot_coloured.py --label "Teff{5100:4000}" --label "logg{3.8:1.2}" \
                                --label-axis-latex "Teff" --label-axis-latex "log(g)" --label-axis-latex "Error in Teff" \
                                --colour-by-label "Teff{:}" \
                                --colour-range-min -400 --colour-range-max 400 \
                                --cannon_output ../../output_data/cannon_4fs_lrs.dat \
                                --output-stub ../../output_plots/apogee_Teff_performance_hr
