#!../../../../../virtualenv/bin/python3
# -*- coding: utf-8 -*-

# NB: The shebang line above assumes you've installed a python virtual environment alongside your working copy of the
# <4most-4gp-scripts> git repository. It also only works if you invoke this python script from the directory where it
# is located. If these two assumptions are incorrect (e.g. you're using Conda), you can still use this script by typing
# <python offset_rms.py>, but <./offset_rms.py> will not work.

"""
Plot results of testing the Cannon against noisy test spectra, to see how well it reproduces stellar labels.
"""

import gzip
import json
import os
import re
from os import path as os_path

import numpy as np
from fourgp_degrade import SNRConverter
from lib.abscissa_information import AbscissaInformation
from lib.compute_cannon_offsets import CannonAccuracyCalculator
from lib.label_information import LabelInformation
from lib.plot_settings import snr_defined_at_wavelength
from lib.pyxplot_driver import PyxplotDriver
from offset_cmd_line_interface import fetch_command_line_arguments


def generate_rms_precision_plots(data_sets, abscissa_label, assume_scaled_solar,
                                 compare_against_reference_labels, output_figure_stem, run_title,
                                 abundances_over_h=True):
    """
    Create a set of plots of a number of Cannon runs.

    :param data_sets:
        A list of runs of the Cannon which are to be plotted. This should be a list of dictionaries. Each dictionary
        should have the entries:

        cannon_output: The filename of the JSON output file from the Cannon, without the ".summary.json.gz" suffix.
        title: Legend caption to use for each Cannon run.
        filters: A string containing semicolon-separated set of constraints on stars we are to include.
        colour: The colour to plot the dataset in.
        line_type: The Pyxplot line type to use for this Cannon run.
        point_type: The Pyxplot point type to use for this Cannon run.


    :param abscissa_label:
        The name of the label we are to plot on the horizontal axis. This should be 'SNR/A', 'SNR/pixel', 'ebv'. See
        <lib/abscissa_information.py>, where these are defined.

    :param compare_against_reference_labels:
        If true, we measure the difference between each label value estimated by the Cannon and the target value taken
        from that star's metadata in the original spectrum library. I.e. the value used to synthesise the spectrum.

        If false, we measure the deviation from the value for each label estimated at the highest abscissa value -- e.g.
        highest SNR.

    :param output_figure_stem:
        Directory to save plots in

    :param run_title:
        A suffix to put at the end of the label in the top-left corner of each plot

    :param abundances_over_h:
        Boolean flag to select whether we plot abundances over H or Fe.

    :return:
        None
    """

    # Metadata about all the labels which we can plot the Cannon's precision in estimating
    label_metadata = LabelInformation().label_metadata

    # Metadata data about all of the horizontal axes that we can plot precision against
    abscissa_info = AbscissaInformation().abscissa_labels[abscissa_label]

    # Look up a list of all the (unique) labels the Cannon tried to fit in all the data sets we're plotting
    unique_json_files = set([item['cannon_output'] for item in data_sets])
    labels_in_each_data_set = [json.loads(gzip.open(json_file + ".summary.json.gz", "rt").read())['labels']
                               for json_file in unique_json_files]
    unique_labels = set([label for label_list in labels_in_each_data_set for label in label_list])

    # Filter out any labels where we don't have metadata about how to plot them
    label_names = [item for item in unique_labels if item in label_metadata]

    # LaTeX strings to use to label each stellar label on graph axes
    labels_info = [label_metadata[ln] for ln in label_names]

    # Create directory to store output files in
    os.system("mkdir -p {}".format(output_figure_stem))

    data_set_titles = []
    output_figure_stem = os_path.abspath(output_figure_stem) + "/"
    data_set_counter = -1
    plot_precision = [[] for i in label_names]

    # If requested, plot all abundances (apart from Fe) over Fe
    if not abundances_over_h:
        for j, label_name in enumerate(label_names):
            test = re.match("\[(.*)/H\]", label_name)
            if test is not None:
                if test.group(1) != "Fe":
                    label_names[j] = "[{}/Fe]".format(test.group(1))

    common_x_limits = list(abscissa_info["axis_range"])

    # Loop over the various Cannon runs we have, e.g. LRS and HRS
    data_file_names = []
    for counter, data_set in enumerate(data_sets):

        try:
            cannon_output = json.loads(gzip.open(data_set['cannon_output'] + ".full.json.gz", "rt").read())
        except json.decoder.JSONDecodeError:
            print("Corrupt JSON file <{}>. Skipping.".format(data_set['cannon_output'] + ".full.json.gz"))
            continue

        # If no label has been specified for this Cannon run, use the description field from the JSON output
        if data_set['title'] is None:
            data_set['title'] = re.sub("_", r"\_", cannon_output['description'])

        # Calculate the accuracy of the Cannon's abundance determinations
        accuracy_calculator = CannonAccuracyCalculator(
            cannon_json_output=cannon_output,
            label_names=label_names,
            compare_against_reference_labels=compare_against_reference_labels,
            assume_scaled_solar=assume_scaled_solar,
            abscissa_field=abscissa_info['field']
        )

        stars_which_meet_filter = accuracy_calculator.filter_test_stars(constraints=data_set['filters'].split(";"))

        accuracy_calculator.calculate_cannon_offsets(filter_on_indices=stars_which_meet_filter)

        # Add data set to plot
        legend_label = data_set['title']  # Read the title which was supplied on the command line for this dataset
        if run_title:
            legend_label += " ({})".format(run_title)  # Possibly append a run title to the end, if supplied

        # add data set

        # Work out multiplication factor to convert SNR/pixel to SNR/A
        snr_converter = SNRConverter(raster=np.array(cannon_output['wavelength_raster']),
                                     snr_at_wavelength=snr_defined_at_wavelength)

        data_set_titles.append(legend_label)

        # Create a sorted list of all the abscissa values we've got
        abscissa_values = list(accuracy_calculator.label_offsets.keys())
        abscissa_values = sorted(set(abscissa_values))

        # If all abscissa values are off the range of the x axis, rescale axis
        if common_x_limits is not None:
            if abscissa_values[0] > common_x_limits[1]:
                common_x_limits[1] = abscissa_values[0]
                print("Rescaling x-axis to include {:.1f}".format(abscissa_values[0]))
            if abscissa_values[-1] < common_x_limits[0]:
                common_x_limits[0] = abscissa_values[-1]
                print("Rescaling x-axis to include {:.1f}".format(abscissa_values[-1]))

        data_set_counter += 1

        # Construct a data file listing the RMS and percentiles of the offset distribution for each label
        for i, (label_name, label_info) in enumerate(zip(label_names, labels_info)):
            y = []
            for abscissa_index, abscissa_value in enumerate(abscissa_values):
                displayed_abscissa_value = abscissa_value
                if abscissa_label == "SNR/A":
                    displayed_abscissa_value = snr_converter.per_pixel(abscissa_value).per_a()

                # List of offsets
                diffs = accuracy_calculator.label_offsets[abscissa_value][label_name]

                # Remove non-finite offsets
                diffs = np.asarray(diffs)
                diffs = diffs[np.logical_not(np.isnan(diffs))]

                # Create a blank row in output data table to receive this entry
                y.append([])

                # Compute root mean square offset
                y[-1].extend([displayed_abscissa_value])
                y[-1].extend([np.sqrt(np.mean(np.square(diffs)))])

            # Filename for data containing statistics on the RMS, and percentiles of the offset distributions
            file_name = "{}/data_offsets_rms_{:d}_{:d}.dat".format(output_figure_stem, i, data_set_counter)

            # Output table of statistical measures of label-mismatch-distribution as a function of abscissa
            # 1st column is RMS.
            np.savetxt(fname=file_name,
                       X=y,
                       header="""
# Abscissa_(probably_SNR)     RMS_offset

            """)

            plot_precision[i].append({
                "plot_item": "\"{}\" using 1:2".format(file_name),
                "title": legend_label,
                "style": "with lp pt {:d} col {} lt {:d}".format(int(data_set["point_type"]),
                                                                 data_set["colour"],
                                                                 int(data_set["line_type"])),
                "star_count": len(stars_which_meet_filter),
            })

            data_file_names.append(file_name)

        del cannon_output

    # Now plot the data

    # Create pyxplot script to produce this plot
    plotter_all = PyxplotDriver(multiplot_filename="{}/precision_all_multiplot".format(output_figure_stem),
                                multiplot_aspect=6. / 8)

    plotter = PyxplotDriver(multiplot_filename="{}/precision_multiplot".format(output_figure_stem),
                            multiplot_aspect=6. / 8)

    # Create a new pyxplot script for precision in all elements in one plot
    for j in range(len(plot_precision[0])):
        plotter_all.make_plot(output_filename="{}/precisionall_{:d}".format(output_figure_stem, j),
                              data_files=data_file_names,
                              caption=r"""
{title} ({star_count} stars)
                              """.format(
                                  title=plot_precision[2][j]["title"],
                                  star_count=plot_precision[2][j]["star_count"]
                              ).strip(),
                              pyxplot_script="""

set numerics errors quiet
set fontsize 1.3
set key top {keypos}
set keycols 2
set ylabel "RMS offset in abundance [dex]"
set xlabel "{x_label}"
set yrange [0:0.5]
{set_log}
{set_x_range}

plot {plot_items}
                              """.format(
                                  keypos="right" if abscissa_info["field"] == "SNR" else "left",
                                  x_label=abscissa_info["latex"],
                                  set_log=("set log x" if abscissa_info["log_axis"] else ""),
                                  set_x_range=("set xrange [{}:{}]".format(common_x_limits[0], common_x_limits[1])
                                               if common_x_limits is not None else ""),
                                  plot_items=", ".join(["""
{filename} title "{title}" w lp pt {point_type}
                                      """.format(
                                      filename=plot_precision[i][j]["plot_item"],
                                      title=label_info["latex"][:-13],  # Remove string "[dex]" from end of label
                                      point_type=16 + (i - 2)
                                  ).strip()
                                                        for i, (label_name, label_info) in
                                                        enumerate(zip(label_names, labels_info))
                                                        if label_name.startswith("[")
                                                        ] + ["""
{target} with lines col grey(0.75) notitle
                                      """.format(
                                      target=target_value
                                  ).strip()
                                                             for target_value in (0.1, 0.2)
                                                             ])
                              )
                              )

    # Create a new pyxplot script for precision plots
    for i, (label_name, label_info) in enumerate(zip(label_names, labels_info)):
        plotter.make_plot(output_filename="{}/precision_{:d}".format(output_figure_stem, i),
                          data_files=data_file_names,
                          caption=label_info["latex"],
                          pyxplot_script="""
                                  
{set_key}
set fontsize 1.3
set ylabel "RMS offset in {y_label}"
set xlabel "{x_label}"
set yrange [{y_min}:{y_max}]
{set_log}
{set_x_range}

plot {plot_items}

                                  """.format(
                              set_key=("set key top {}".format("right"
                                                               if abscissa_info["field"] == "SNR"
                                                               else "left")
                                       if (len(plot_precision[i]) > 1)
                                       else "set nokey"),
                              x_label=abscissa_info["latex"],
                              y_label=label_info["latex"],
                              y_min=0.5 * label_info["offset_min"],
                              y_max=0.5 * label_info["offset_max"],
                              set_log=("set log x" if abscissa_info["log_axis"] else ""),
                              set_x_range=("set xrange [{}:{}]".format(common_x_limits[0], common_x_limits[1])
                                           if common_x_limits is not None else ""),
                              plot_items=", ".join(["""
{plot_item} title "{title} ({star_count} stars)" {style}
                                      """.format(
                                  **item
                              ).strip()
                                                    for item in plot_precision[i]
                                                    ] + ["""
{target} with lines col grey(0.75) notitle
                                      """.format(
                                  target=target_value
                              ).strip()
                                                         for target_value in label_info["targets"]
                                                         ])

                          )
                          )


if __name__ == "__main__":
    # Read input parameters
    command_line_arguments = fetch_command_line_arguments()
    generate_rms_precision_plots(**command_line_arguments)
