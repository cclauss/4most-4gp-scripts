#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Take a training set and a test set, and see how well the Cannon can reproduce the stellar labels on the test
set of stars.
"""

import argparse
from os import path as os_path
import re
import logging
import json
import time
import numpy as np

from fourgp_speclib import SpectrumLibrarySqlite
from fourgp_cannon import CannonInstance

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s:%(filename)s:%(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S')
logger = logging.getLogger(__name__)

# Read input parameters
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--test', required=True, dest='test_library',
                    help="Library of spectra to test the trained Cannon on.")
parser.add_argument('--train', required=True, dest='train_library',
                    help="Library of labelled spectra to train the Cannon on.")
parser.add_argument('--censor', default="", dest='censor_line_list',
                    help="Optional list of line positions for the Cannon to fit, ignoring continuum between.")
parser.add_argument('--tolerance', default=1e-4, dest='tolerance', type=float,
                    help="The parameter xtol which is passed to the scipy optimisation routines as xtol to determine "
                         "whether they have converged.")
parser.add_argument('--output-file', default="./test_cannon.out", dest='output_file',
                    help="Data file to write output to.")
args = parser.parse_args()

logger.info("Testing Cannon with arguments <{}> <{}> <{}> <{}>".format(args.test_library,
                                                                       args.train_library,
                                                                       args.censor_line_list,
                                                                       args.output_file))

# List of labels over which we are going to test the performance of the Cannon
test_labels = ("Teff", "logg", "[Fe/H]",
               "[C/H]", "[N/H]", "[O/H]", "[Na/H]", "[Mg/H]", "[Al/H]", "[Si/H]",
               "[Ca/H]", "[Ti/H]", "[Mn/H]", "[Co/H]", "[Ni/H]", "[Ba/H]", "[Sr/H]")

# Set path to workspace where we expect to find libraries of spectra
our_path = os_path.split(os_path.abspath(__file__))[0]
workspace = os_path.join(our_path, "..", "workspace")


# Helper for opening input SpectrumLibrary(s)
def open_input_libraries(library_spec):
    test = re.match("(.*)\[(.*)\]", library_spec)
    constraints = {}
    if test is None:
        library_name = library_spec
    else:
        library_name = test.group(1)
        for constraint in test.group(2).split(","):
            words_1 = constraint.split("=")
            words_2 = constraint.split("<")
            if len(words_1) == 2:
                constraint_name = words_1[0]
                try:
                    constraint_value = float(words_1[1])
                except ValueError:
                    constraint_value = words_1[1]
                constraints[constraint_name] = constraint_value
            elif len(words_2) == 3:
                constraint_name = words_2[1]
                try:
                    constraint_value_a = float(words_2[0])
                    constraint_value_b = float(words_2[2])
                except ValueError:
                    constraint_value_a = words_2[0]
                    constraint_value_b = words_2[2]
                constraints[constraint_name] = (constraint_value_a, constraint_value_b)
            else:
                assert False, "Could not parse constraint <{}>".format(constraint)
    constraints["continuum_normalised"] = 1  # All input spectra must be continuum normalised
    library_path = os_path.join(workspace, library_name)
    input_library = SpectrumLibrarySqlite(path=library_path, create=False)
    library_items = input_library.search(**constraints)
    return {
        "library": input_library,
        "items": library_items
    }


# Open training set
spectra = open_input_libraries(args.train_library)
training_library, training_library_items = [spectra[i] for i in ("library", "items")]

# Open test set
spectra = open_input_libraries(args.test_library)
test_library, test_library_items = [spectra[i] for i in ("library", "items")]

# Load training set
training_library_ids = [i["specId"] for i in training_library_items]
training_spectra = training_library.open(ids=training_library_ids)
raster = training_spectra.wavelengths

# Load test set
test_library_ids = [i["specId"] for i in test_library_items]

# If required, generate the censoring masks
censoring_masks = None
if args.censor_line_list != "":
    # Only import astropy FITS reader if we actually need to use it
    from astropy.io import fits

    window = 0.5  # How many Angstroms either side of the line should be used?
    censoring_masks = {}
    ges_line_list = fits.open(args.censor_line_list)[1].data

    for label_name in test_labels[3:]:
        mask = np.zeros(raster.size, dtype=bool)

        # Find instances of this element in the line list
        element = label_name.lstrip("[").split("/")[0]
        match = np.any(ges_line_list["NAME"] == element, axis=1)

        # Get corresponding wavelengths
        matching_wavelengths = ges_line_list["LAMBDA"][match]

        # For each wavelength, allow +/- window that line.
        for i, wavelength in enumerate(matching_wavelengths):
            window_mask = ((wavelength + window) >= raster) * (raster >= (wavelength - window))
            mask[window_mask] = True

        logger.info("Pixels used for label {}: {} of {} (in {} lines)".format(label_name, mask.sum(),
                                                                              len(raster), len(matching_wavelengths)))
        censoring_masks[label_name] = ~mask

# Construct and train a model
time_training_start = time.time()
model = CannonInstance(training_set=training_spectra,
                       label_names=test_labels,
                       tolerance=args.tolerance,
                       censors=censoring_masks)
time_training_end = time.time()

# Test the model
N = len(test_library_ids)
time_taken = np.zeros(N)
results = []
for index in range(N):
    test_spectrum_array = test_library.open(ids=test_library_ids[index])
    spectrum = test_spectrum_array.extract_item(0)
    logger.info("Testing {}/{}: {}".format(index + 1, N, spectrum.metadata['Starname']))

    time_start = time.time()
    labels, cov, meta = model.fit_spectrum(spectrum=spectrum)
    time_end = time.time()
    time_taken[index] = time_end - time_start

    # Identify which star it is and what the SNR is
    star_name = spectrum.metadata["Starname"]
    snr = spectrum.metadata["SNR"]

    # From the label covariance matrix extract the standard deviation in each label value
    # (diagonal terms in the matrix are variances)
    err_labels = np.sqrt(np.diag(cov[0]))

    # Turn list of label values into a dictionary
    result = dict(zip(test_labels, labels[0]))

    # Add the standard deviations of each label into the dictionary
    result.update(dict(zip(["E_{}".format(label_name) for label_name in test_labels], err_labels)))

    # Add target values for each label into the dictionary
    for label_name in test_labels:
        if label_name in spectrum.metadata:
            result["target_{}".format(label_name)] = spectrum.metadata[label_name]

    # Add the star name and the SNR ratio of the test spectrum
    result.update({"Starname": star_name, "SNR": snr, "time": time_taken[index]})
    results.append(result)

# Report time taken
logger.info("Fitting of {:d} spectra completed. Took {:.2f} +/- {:.2f} sec / spectrum.".format(N,
                                                                                               np.mean(time_taken),
                                                                                               np.std(time_taken)))

# Write results to JSON file
with open(args.output_file + ".json", "w") as f:
    f.write(json.dumps({
        "start_time": time_training_start,
        "end_time": time.time(),
        "training_time": time_training_end - time_training_end,
        "stars": results
    }))
