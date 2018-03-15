#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

"""
Take a library of spectra, perhaps generated by Turbospectrum, and add Gaussian noise to them.
"""

import argparse
import os
from os import path as os_path
import hashlib
import time
import re
import logging
import numpy as np

from fourgp_speclib import SpectrumLibrarySqlite
from fourgp_degrade import GaussianNoise

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s:%(filename)s:%(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S')
logger = logging.getLogger(__name__)

# Read input parameters
our_path = os_path.split(os_path.abspath(__file__))[0]
root_path = os_path.join(our_path, "..", "..")
pid = os.getpid()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input-library',
                    required=False,
                    default="turbospec_apokasc_training_set",
                    dest="input_library",
                    help="The name of the SpectrumLibrary we are to read input spectra from. Stars may be filtered by "
                         "parameters by placing a comma-separated list of constraints in [] brackets after the name of "
                         "the library. Use the syntax [Teff=3000] to demand equality, or [0<[Fe/H]<0.2] to specify a "
                         "range.")
parser.add_argument('--output-library-lrs',
                    required=False,
                    default="4fs_apokasc_training_set_lrs",
                    dest="output_library_lrs",
                    help="The name of the SpectrumLibrary we are to feed synthesized LRS spectra into.")
parser.add_argument('--output-library-hrs',
                    required=False,
                    default="4fs_apokasc_training_set_hrs",
                    dest="output_library_hrs",
                    help="The name of the SpectrumLibrary we are to feed synthesized HRS spectra into.")
parser.add_argument('--workspace', dest='workspace', default="",
                    help="Directory where we expect to find spectrum libraries.")
parser.add_argument('--snr-definition',
                    action="append",
                    dest="snr_definitions",
                    help="Specify a way of defining SNR, in the form 'name,minimum,maximum', meaning we calculate the "
                         "median SNR per pixel between minimum and maximum wavelengths in Angstrom.")
parser.add_argument('--snr-list',
                    required=False,
                    default="10,20,50,80,100,130,180,250,5000",
                    dest="snr_list",
                    help="Specify a comma-separated list of the SNRs that 4FS is to degrade spectra to.")
parser.add_argument('--snr-definitions-lrs',
                    required=False,
                    default="",
                    dest="snr_definitions_lrs",
                    help="Specify the SNR definitions to use for the R, G and B bands of 4MOST LRS.")
parser.add_argument('--snr-definitions-hrs',
                    required=False,
                    default="",
                    dest="snr_definitions_hrs",
                    help="Specify the SNR definitions to use for the R, G and B bands of 4MOST HRS.")
parser.add_argument('--create',
                    required=False,
                    action='store_true',
                    dest="create",
                    help="Create a clean SpectrumLibrary to feed synthesized spectra into")
parser.add_argument('--no-create',
                    required=False,
                    action='store_false',
                    dest="create",
                    help="Do not create a clean SpectrumLibrary to feed synthesized spectra into")
parser.set_defaults(create=True)
parser.add_argument('--log-file',
                    required=False,
                    default="/tmp/fourfs_apokasc_{}.log".format(pid),
                    dest="log_to",
                    help="Specify a log file where we log our progress.")
args = parser.parse_args()

logger.info("Adding Gaussian noise to spectra with arguments <{}> <{}> <{}>".format(args.input_library,
                                                                                    args.output_library_lrs,
                                                                                    args.output_library_hrs))

# Set path to workspace where we create libraries of spectra
workspace = args.workspace if args.workspace else os_path.join(our_path, "..", "workspace")
os.system("mkdir -p {}".format(workspace))

# Open input SpectrumLibrary
spectra = SpectrumLibrarySqlite.open_and_search(library_spec=args.input_library,
                                                workspace=workspace,
                                                extra_constraints={"continuum_normalised": 0}
                                                )
input_library, input_spectra_ids, input_spectra_constraints = [spectra[i] for i in ("library", "items", "constraints")]

# Create new SpectrumLibrary
output_libraries = {}

for mode in ({"name": "lrs", "library": args.output_library_lrs},
             {"name": "hrs", "library": args.output_library_hrs}):
    library_name = re.sub("/", "_", mode['library'])
    library_path = os_path.join(workspace, library_name)
    output_libraries[mode['name']] = SpectrumLibrarySqlite(path=library_path, create=args.create)

# Definitions of SNR
if (args.snr_definitions is None) or (len(args.snr_definitions) < 1):
    snr_definitions = None
else:
    snr_definitions = []
    for snr_definition in args.snr_definitions:
        words = snr_definition.split(",")
        snr_definitions.append([words[0], float(words[1]), float(words[2])])

if len(args.snr_definitions_lrs) < 1:
    snr_definitions_lrs = None
else:
    snr_definitions_lrs = args.snr_definitions_lrs.split(",")
    assert len(snr_definitions_lrs) == 3

if len(args.snr_definitions_hrs) < 1:
    snr_definitions_hrs = None
else:
    snr_definitions_hrs = args.snr_definitions_hrs.split(",")
    assert len(snr_definitions_hrs) == 3

snr_list = [float(item.strip()) for item in args.snr_list.split(",")]

# Read wavelength rasters for LRS and HRS
raster_hrs = np.loadtxt(os_path.join(our_path, "raster_hrs.txt")).transpose()[0]
raster_lrs = np.loadtxt(os_path.join(our_path, "raster_lrs.txt")).transpose()[0]

# Instantiate Gaussian noise model
modes = {
    "hrs": GaussianNoise(
        wavelength_raster=raster_hrs,
        snr_definitions=snr_definitions,
        use_snr_definitions=snr_definitions_hrs,
        snr_list=snr_list
    ),
    "lrs": GaussianNoise(
        wavelength_raster=raster_lrs,
        snr_definitions=snr_definitions,
        use_snr_definitions=snr_definitions_lrs,
        snr_list=snr_list
    )
}

# Loop over spectra to process
with open(args.log_to, "w") as result_log:
    for input_spectrum_id in input_spectra_ids:
        logger.info("Working on <{}>".format(input_spectrum_id['filename']))
        # Open Spectrum data from disk
        input_spectrum_array = input_library.open(ids=input_spectrum_id['specId'])
        input_spectrum = input_spectrum_array.extract_item(0)

        # Look up the name of the star we've just loaded
        spectrum_matching_field = 'uid' if 'uid' in input_spectrum.metadata else 'Starname'
        object_name = input_spectrum.metadata[spectrum_matching_field]

        # Write log message
        result_log.write("\n[{}] {}... ".format(time.asctime(), object_name))
        result_log.flush()

        # Search for the continuum-normalised version of this same object
        search_criteria = input_spectra_constraints.copy()
        search_criteria[spectrum_matching_field] = object_name
        search_criteria['continuum_normalised'] = 1
        continuum_normalised_spectrum_id = input_library.search(**search_criteria)

        # Check that continuum-normalised spectrum exists
        assert len(continuum_normalised_spectrum_id) == 1, "Could not find continuum-normalised spectrum."

        # Load the continuum-normalised version
        input_spectrum_continuum_normalised_arr = input_library.open(ids=continuum_normalised_spectrum_id[0]['specId'])
        input_spectrum_continuum_normalised = input_spectrum_continuum_normalised_arr.extract_item(0)

        # Process spectra through Gaussian noise model
        degraded_spectra = {}
        for mode_name, noise_model in modes.iteritems():
            degraded_spectra[mode_name] = noise_model.process_spectra(
                spectra_list=((input_spectrum, input_spectrum_continuum_normalised),)
            )

        # Import degraded spectra into output spectrum library
        for mode in degraded_spectra:
            for index in range(len(degraded_spectra[mode])):
                for snr in degraded_spectra[mode][index]:
                    unique_id = hashlib.md5(os.urandom(32).encode("hex")).hexdigest()[:16]
                    for spectrum_version in degraded_spectra[mode][index][snr]:
                        output_libraries[mode].insert(spectra=spectrum_version,
                                                      filenames=input_spectrum_id['filename'],
                                                      metadata_list={"uid": unique_id})

# Clean up noise models
for mode in modes.itervalues():
    mode.close()
