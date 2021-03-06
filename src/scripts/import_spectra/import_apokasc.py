#!../../../../virtualenv/bin/python3
# -*- coding: utf-8 -*-

# NB: The shebang line above assumes you've installed a python virtual environment alongside your working copy of the
# <4most-4gp-scripts> git repository. It also only works if you invoke this python script from the directory where it
# is located. If these two assumptions are incorrect (e.g. you're using Conda), you can still use this script by typing
# <python import_apokasc.py>, but <./import_apokasc.py> will not work.

"""
Take the APOKASC training set and test sets, as defined in ASCII tables provided by Keith Hawkins, and turn them into
SpectrumLibraries for use in 4MOST 4GP
"""

import argparse
import glob
import logging
import os
from os import path as os_path

from astropy.table import Table
from fourgp_speclib import SpectrumLibrarySqlite, Spectrum

# Path to where we find Keith Hawkins's <4MOST_testspectra>
our_path = os_path.split(os_path.abspath(__file__))[0]
test_spectra_path = os_path.join(our_path, "../../../../4MOST_testspectra")

# Set path to workspace where we create libraries of spectra
workspace = os_path.join(our_path, "../../../workspace")
os.system("mkdir -p {}".format(workspace))


# Convenience function to provide dictionary access to rows of an astropy table
def astropy_row_to_dict(x):
    return dict([(i, x[i]) for i in x.columns])


# Read input parameters
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--training-set',
                    required=False,
                    default=os_path.join(test_spectra_path, "trainingset_param.tab"),
                    dest="training_set",
                    help="Specify the filename of the ASCII table which lists the stellar parameters of the training "
                         "stars.")
parser.add_argument('--test-set',
                    required=False,
                    default=os_path.join(test_spectra_path, "testset_param.tab"),
                    dest="test_set",
                    help="Specify the filename of the ASCII table which lists the stellar parameters of the test "
                         "stars.")
args = parser.parse_args()

# Start logger
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s:%(filename)s:%(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S')
logger = logging.getLogger(__name__.strip())
logger.info("Importing APOKASC sample of spectra")

# Open table which lists stellar labels for each star in the training set
training_set = Table.read(args.training_set, format="ascii")

# Open table which lists stellar labels for each star in the test set
expected_test_output = Table.read(args.test_set, format="ascii")
expected_test_output_dict = dict([(star['Starname'], astropy_row_to_dict(star)) for star in expected_test_output])

# Import high- and low-resolution training sets into spectrum libraries
for training_set_dir, out_library in (("APOKASC_trainingset/HRS", "hawkins_apokasc_training_set_hrs"),
                                      ("APOKASC_trainingset/LRS", "hawkins_apokasc_training_set_lrs")):

    # Turn training set into a spectrum library with path specified above
    library_path = os_path.join(workspace, out_library)
    library = SpectrumLibrarySqlite(path=library_path, create=True)

    # Import each star in turn
    for star in training_set:
        filepath = os_path.join(test_spectra_path, training_set_dir, "{}_SNR250.txt".format(star["Starname"]))
        filename = os_path.split(filepath)[1]

        metadata = astropy_row_to_dict(star)
        metadata["continuum_normalised"] = 1
        metadata["SNR"] = 250

        # Read star from text file and import it into our SpectrumLibrary
        spectrum = Spectrum.from_file(filename=filepath, metadata=metadata, binary=False)
        library.insert(spectra=spectrum, filenames=filename)

# Import high- and low-resolution test sets into spectrum libraries
for test_set_dir, out_library in (("testset/HRS", "hawkins_apokasc_test_set_hrs"),
                                  ("testset/LRS", "hawkins_apokasc_test_set_lrs")):

    # Turn training set into a spectrum library with path specified above
    library_path = os_path.join(workspace, out_library)
    library = SpectrumLibrarySqlite(path=library_path, create=True)

    # Import each star in turn
    test_set = glob.glob(os_path.join(test_spectra_path, test_set_dir, "star*_SNR*.txt"))
    for filepath in test_set:
        # Identify which star it is, and its SNR
        basename = os_path.basename(filepath)
        star_name = basename.split("_")[0]
        snr = int(basename.split("_")[1].split(".")[0].lstrip("SNR"))

        metadata = expected_test_output_dict[star_name]
        metadata["continuum_normalised"] = 1
        metadata["SNR"] = snr

        # Read star from text file and import it into our SpectrumLibrary
        spectrum = Spectrum.from_file(filename=filepath, metadata=metadata, binary=False)
        filename = os_path.split(filepath)[1]
        library.insert(spectra=spectrum, filenames=filename)
