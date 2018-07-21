#!../../../../virtualenv/bin/python2.7
# -*- coding: utf-8 -*-

# NB: The shebang line above assumes you've installed a python virtual environment alongside your working copy of the
# <4most-4gp-scripts> git repository. It also only works if you invoke this python script from the directory where it
# is located. If these two assumptions are incorrect (e.g. you're using Conda), you can still use this script by typing
# <python degrade_library_with_rv.py>, but <./degrade_library_with_rv.py> will not work.

"""
Take a library of spectra, perhaps generated by Turbospectrum, and apply some radial velocity(s) to them. We do this
using the <apply_radial_velocity> method of the <Spectrum> class, which shifts the wavelength column in the spectra
without affecting the flux data. We feed the shifted spectra into a new spectrum library.
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
root_path = os_path.join(our_path, "../..")
pid = os.getpid()
parser = argparse.ArgumentParser(description=__doc__.strip())
parser.add_argument('--input-library',
                    required=False,
                    default="galah_test_sample_turbospec",
                    dest="input_library",
                    help="The name of the spectrum library we are to read input spectra from. A subset of the stars "
                         "in the input library may optionally be selected by suffixing its name with a comma-separated "
                         "list of constraints in [] brackets. Use the syntax my_library[Teff=3000] to demand equality, "
                         "or [0<[Fe/H]<0.2] to specify a range. We do not currently support other operators like "
                         "[Teff>5000], but such ranges are easy to recast is a range, e.g. [5000<Teff<9999].")
parser.add_argument('--output-library',
                    required=False,
                    default="galah_test_sample_withrv",
                    dest="output_library",
                    help="The name of the spectrum library we are to feed the processed output spectra into.")
parser.add_argument('--workspace', dest='workspace', default="",
                    help="Directory where we expect to find spectrum libraries.")
parser.add_argument('--rv-list',
                    required=False,
                    default="0.1,1,2,5,8,10,20,50",
                    dest="rv_list",
                    help="Specify a comma-separated list of the RVs (km/s) that we should add to spectra. A positive "
                         "radial velocity means that the object is receding from the observer.")
parser.add_argument('--create',
                    action='store_true',
                    dest="create",
                    help="Create a clean spectrum library to feed output spectra into. Will throw an error if "
                         "a spectrum library already exists with the same name.")
parser.add_argument('--no-create',
                    action='store_false',
                    dest="create",
                    help="Do not create a clean spectrum library to feed output spectra into.")
parser.set_defaults(create=True)
parser.add_argument('--db-in-tmp',
                    action='store_true',
                    dest="db_in_tmp",
                    help="Symlink database into /tmp while we're putting data into it (for performance). "
                         "Don't mess with this option unless you know what you're doing.")
parser.add_argument('--no-db-in-tmp',
                    action='store_false',
                    dest="db_in_tmp",
                    help="Do not symlink database into /tmp while we're putting data into it. Recommended")
parser.set_defaults(db_in_tmp=False)
parser.add_argument('--log-file',
                    required=False,
                    default="/tmp/add_rv_{}.log".format(pid),
                    dest="log_to",
                    help="Specify a log file where we log our progress.")
args = parser.parse_args()

logger.info("Adding radial velocities to spectra from <{}>, going into <{}>".format(args.input_library,
                                                                                    args.output_library))

# Set path to workspace where we create libraries of spectra
workspace = args.workspace if args.workspace else os_path.join(our_path, "../../../workspace")
os.system("mkdir -p {}".format(workspace))

# Open input SpectrumLibrary, and search for flux normalised spectra meeting our filtering constraints
spectra = SpectrumLibrarySqlite.open_and_search(library_spec=args.input_library,
                                                workspace=workspace,
                                                extra_constraints={"continuum_normalised": 0}
                                                )

# Get a list of the spectrum IDs which we were returned
input_library, input_spectra_ids, input_spectra_constraints = [spectra[i] for i in ("library", "items", "constraints")]

# Create new spectrum library for output
library_name = re.sub("/", "_", args.output_library)
library_path = os_path.join(workspace, library_name)
output_library = SpectrumLibrarySqlite(path=library_path, create=args.create)

# We may want to symlink the sqlite3 database file into /tmp for performance reasons
# This bit of crack-on-a-stick is only useful if /tmp is on a ram disk, though...
if args.db_in_tmp:
    del output_library
    os.system("mv {} /tmp/tmp_{}.db".format(os_path.join(library_path, "index.db"), library_name))
    os.system("ln -s /tmp/tmp_{}.db {}".format(library_name, os_path.join(library_path, "index.db")))
    output_library = SpectrumLibrarySqlite(path=library_path, create=False)

# Parse the list of radial velocities which were passed to us on the command line
rv_list = [float(item.strip()) for item in args.rv_list.split(",")]

# Start making a log file
with open(args.log_to, "w") as result_log:
    # Loop over spectra to process
    for input_spectrum_id in input_spectra_ids:
        logger.info("Working on <{}>".format(input_spectrum_id['filename']))
        # Open Spectrum data from disk
        input_spectrum_array = input_library.open(ids=input_spectrum_id['specId'])

        # Turn SpectrumArray object into a Spectrum object
        input_spectrum = input_spectrum_array.extract_item(0)

        # Look up the unique ID of the star we've just loaded
        # Newer spectrum libraries have a uid field which is guaranteed unique; for older spectrum libraries use
        # Starname instead.

        # Work out which field we're using (uid or Starname)
        spectrum_matching_field = 'uid' if 'uid' in input_spectrum.metadata else 'Starname'

        # Look up the unique ID of this object
        object_name = input_spectrum.metadata[spectrum_matching_field]

        # Write log message
        result_log.write("\n[{}] {}... ".format(time.asctime(), object_name))
        result_log.flush()

        # Search for the continuum-normalised version of this same object (which will share the same uid / name)
        search_criteria = input_spectra_constraints.copy()
        search_criteria[spectrum_matching_field] = object_name
        search_criteria['continuum_normalised'] = 1
        continuum_normalised_spectrum_id = input_library.search(**search_criteria)

        # Check that continuum-normalised spectrum exists and is unique
        assert len(continuum_normalised_spectrum_id) == 1, "Could not find continuum-normalised spectrum."

        # Load the continuum-normalised version
        input_spectrum_continuum_normalised_arr = input_library.open(ids=continuum_normalised_spectrum_id[0]['specId'])

        # Turn the SpectrumArray we got back into a single Spectrum
        input_spectrum_continuum_normalised = input_spectrum_continuum_normalised_arr.extract_item(0)

        # Process spectra with each radial velocity in turn
        for rv in rv_list:
            # Apply RV to the flux-normalised spectrum
            degraded = input_spectrum.apply_radial_velocity(rv * 1000)

            # Apply RV to the continuum-normalised spectrum
            degraded_cn = input_spectrum_continuum_normalised.apply_radial_velocity(rv * 1000)

            # Create a unique ID for this mock observation (shared between the flux- and continuum-normalised output)
            unique_id = hashlib.md5(os.urandom(32).encode("hex")).hexdigest()[:16]

            # Save the flux-normalised output
            output_library.insert(spectra=degraded,
                                  filenames=input_spectrum_id['filename'],
                                  metadata_list={"uid": unique_id, "rv": rv * 1000})

            # Save the continuum-normalised output
            output_library.insert(spectra=degraded_cn,
                                  filenames=input_spectrum_id['filename'],
                                  metadata_list={"uid": unique_id, "rv": rv * 1000})

# If we put database in /tmp while adding entries to it, now return it to original location
if args.db_in_tmp:
    del output_library
    os.system("mv /tmp/tmp_{}.db {}".format(library_name, os_path.join(library_path, "index.db")))