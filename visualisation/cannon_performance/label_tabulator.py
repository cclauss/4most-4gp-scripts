#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Take an output file containing the label values produced by the Cannon. Tabulate the target and output stellar
parameters next to each other in an ASCII data file.
"""

import argparse
import json


def tabulate_labels(output_stub, labels, cannon):
    # library_values[Starname] = [list of label values]
    # cannon_values[Starname][SNR] = [list of label values]
    library_values = {}
    cannon_values = {}

    # Start compiling a list of all the SNR values in the Cannon output
    snr_list = []

    # Open Cannon output data file
    for item in json.loads(open(cannon).read())["stars"]:
        # Look up name of object and SNR of spectrum used
        object_name = item["Starname"]
        snr = float(item["SNR"])

        # Look up Cannon's estimated values of the labels we're interested in
        label_values = []
        for label in labels:
            label_values.append(item[label])

        # Feed Cannon's estimated values in the cannon_values data structure
        if object_name not in cannon_values:
            cannon_values[object_name] = {}
        cannon_values[object_name][snr] = label_values

        # Keep a list of all the SNRs we've seen
        if snr not in snr_list:
            snr_list.append(snr)

        # Look up the target values for each label
        label_values = []
        for label in labels:
            label_values.append(item["target_{}".format(label)])
        library_values[object_name] = label_values

    # Start creating output data files
    snr_list_with_filenames = []
    snr_list.sort()
    object_names = library_values.keys()
    object_names.sort()
    for snr in snr_list:
        filename = "{}_{:03.0f}.dat".format(output_stub, snr)
        snr_list_with_filenames.append({
            "snr": snr,
            "filename": filename
        })

        with open(filename, "w") as output:
            for object_name in object_names:
                # Start line with the library parameter values
                words = [str(i) for i in library_values[object_name]]

                # Add values which the Cannon estimated at this SNR
                if (object_name in cannon_values) and (snr in cannon_values[object_name]):
                    words.extend([str(i) for i in cannon_values[object_name][snr]])
                else:
                    words.extend(["-" for i in labels])
                line = " ".join(words)
                output.write("{}\n".format(line))
    return snr_list_with_filenames


if __name__ == "__main__":
    # Read input parameters
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True, action="append", dest='labels',
                        help="Labels we should output values for.")
    parser.add_argument('--cannon_output',
                        required=True,
                        default="",
                        dest='cannon',
                        help="Cannon output file.")
    parser.add_argument('--output-stub', default="/tmp/cannon_estimates_", dest='output_stub',
                        help="Data file to write output to.")
    args = parser.parse_args()

    tabulate_labels(args.output_stub, args.labels, args.cannon)