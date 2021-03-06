#!../../../../../virtualenv/bin/python3
# -*- coding: utf-8 -*-

# NB: The shebang line above assumes you've installed a python virtual environment alongside your working copy of the
# <4most-4gp-scripts> git repository. It also only works if you invoke this python script from the directory where it
# is located. If these two assumptions are incorrect (e.g. you're using Conda), you can still use this script by typing
# <python scatter_plot_arrows.py>, but <./scatter_plot_arrows.py> will not work.

"""
Take an output file from the Cannon, and produce a scatter plot with arrows connecting the library parameter values to
those estimated by the Cannon.
"""

import argparse
import gzip
import json
import os
import re
import sys

import numpy as np
from fourgp_degrade import SNRConverter
from label_tabulator import tabulate_labels
from lib.plot_settings import snr_defined_at_wavelength
from lib.pyxplot_driver import PyxplotDriver

# Read input parameters
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--label', required=True, action="append", dest='labels',
                    help="Labels we should plot on the two axes of the scatter plot.")
parser.add_argument('--label-axis-latex', required=True, action="append", dest='label_axis_latex',
                    help="Titles we should put on the two axes of the scatter plot.")
parser.add_argument('--cannon-output',
                    required=True,
                    default="",
                    dest='cannon',
                    help="Filename of the JSON file containing the label values estimated by the Cannon, without "
                         "the <.summary.json.gz> suffix.")
parser.add_argument('--output', default="/tmp/scatter_plot_arrows", dest='output_stub',
                    help="Data file to write output to.")
args = parser.parse_args()

# Check that we have one label to plot on each axis label, and a title to show on each axis
assert len(args.labels) == 2, "A scatter plot needs two labels to plot -- one on each axis."
assert len(args.label_axis_latex) == 2, "A scatter plot needs label names for two axes."

# Labels are supplied with ranges listed in {}. We extract the names to pass to label_tabulator.
label_list = []
label_names = []
for item in args.labels:
    test = re.match("(.*){(.*:.*)}", item)
    assert test is not None, "Label names should take the form <name{:2}>, with range to plot in {}."
    label_list.append({
        "name": test.group(1),
        "range": test.group(2)
    })
    label_names.append(test.group(1))

# Create data files listing parameter values
snr_list = tabulate_labels(output_stub="{}/scatter_plot_arrows_snr_".format(args.output_stub),
                           labels=label_names,
                           cannon=args.cannon)

# Fetch title for this Cannon run
if not os.path.exists(args.cannon + ".summary.json.gz"):
    print("scatter_plot_arrows.py could not proceed: Cannon run <{}> not found". \
          format(args.cannon + ".summary.json.gz"))
    sys.exit()

cannon_output = json.loads(gzip.open(args.cannon + ".summary.json.gz", "rt").read())
description = cannon_output['description']

# Work out multiplication factor to convert SNR/pixel to SNR/A
snr_converter = SNRConverter(raster=np.array(cannon_output['wavelength_raster']),
                             snr_at_wavelength=snr_defined_at_wavelength)

# Create pyxplot script to produce this plot
plotter = PyxplotDriver(multiplot_filename="{filename}/multiplot".format(filename=args.output_stub),
                        multiplot_aspect=5.1 / 8)

for snr in snr_list:
    plotter.make_plot(output_filename=snr["filename"],
                      data_files=[snr["filename"]],
                      caption=re.sub("_", r"\_", description),
                      pyxplot_script="""
    
set numerics errors quiet
set key top left
set linewidth 0.4

set xlabel "{x_label}"
set xrange [{x_range}]
set ylabel "{y_label}"
set yrange [{y_range}]

plot "{filename}" title "Synthesised values -$>$ Cannon output at SNR/\\AA={snr_per_a:.1f}." \
     with arrows colour red using 1:4:2:5

""".format(x_label=args.label_axis_latex[0],
           y_label=args.label_axis_latex[1],
           x_range=label_list[0]["range"],
           y_range=label_list[1]["range"],
           filename=snr["filename"],
           snr_per_a=snr_converter.per_pixel(snr["snr"]).per_a()  # Convert SNR/pixel to SNR/A
           )
                      )

# Clean up plotter
del plotter
