#!../../../../virtualenv/bin/python3
# -*- coding: utf-8 -*-

# NB: The shebang line above assumes you've installed a python virtual environment alongside your working copy of the
# <4most-4gp-scripts> git repository. It also only works if you invoke this python script from the directory where it
# is located. If these two assumptions are incorrect (e.g. you're using Conda), you can still use this script by typing
# <python degrade_library_with_4fs.py>, but <./degrade_library_with_4fs.py> will not work.

"""
Take a library of spectra, perhaps generated by Turbospectrum, and pass them through 4FS. We create a pair of new
spectrum libraries, containing 4FS mock observations of the input spectra, for 4MOST LRS and HRS.
"""

import argparse
import hashlib
import logging
import os
import re
import time
from os import path as os_path

from fourgp_fourfs import FourFS
from fourgp_speclib import SpectrumLibrarySqlite

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s:%(filename)s:%(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S')
logger = logging.getLogger(__name__)

# Read input parameters
our_path = os_path.split(os_path.abspath(__file__))[0]
root_path = os_path.join(our_path, "../../../..")
pid = os.getpid()
parser = argparse.ArgumentParser(description=__doc__.strip())
parser.add_argument('--input-library',
                    required=False,
                    default="demo_stars",
                    dest="input_library",
                    help="The name of the spectrum library we are to read input spectra from. A subset of the stars "
                         "in the input library may optionally be selected by suffixing its name with a comma-separated "
                         "list of constraints in [] brackets. Use the syntax my_library[Teff=3000] to demand equality, "
                         "or [0<[Fe/H]<0.2] to specify a range. We do not currently support other operators like "
                         "[Teff>5000], but such ranges are easy to recast is a range, e.g. [5000<Teff<9999].")
parser.add_argument('--output-library-lrs',
                    required=False,
                    default="4fs_demo_stars_lrs",
                    dest="output_library_lrs",
                    help="The name of the spectrum library we are to feed mock LRS observations into.")
parser.add_argument('--output-library-hrs',
                    required=False,
                    default="4fs_demo_stars_hrs",
                    dest="output_library_hrs",
                    help="The name of the spectrum library we are to feed mock HRS observations into.")
parser.add_argument('--workspace', dest='workspace', default="",
                    help="Directory where we expect to find spectrum libraries.")
parser.add_argument('--snr-definition',
                    action="append",
                    dest="snr_definitions",
                    help="Specify a way of defining SNR, in the form 'name,minimum,maximum', meaning we calculate the "
                         "median SNR per pixel between minimum and maximum wavelengths in Angstrom.")
parser.add_argument('--snr-per-pixel',
                    action='store_true',
                    dest="per_pixel",
                    help="Specify that SNR values in --snr-list are quoted per pixel [default]")
parser.add_argument('--snr-per-angstrom',
                    action='store_false',
                    dest="per_pixel",
                    help="Specify that SNR values in --snr-list are quoted per Angstrom")
parser.set_defaults(per_pixel=True)
parser.add_argument('--snr-list',
                    required=False,
                    default="10,12,14,16,18,20,23,26,30,35,40,45,50,80,100,130,180,250",
                    dest="snr_list",
                    help="Specify a comma-separated list of the SNRs that 4FS is to degrade spectra to.")
parser.add_argument('--mag-list',
                    required=False,
                    default="15",
                    dest="mag_list",
                    help="Specify a comma-separated list of the magnitudes to assume when simulating observations "
                         "of each object. If multiple magnitudes are specified, than each input spectrum we be "
                         "output multiple times, once at each magnitude.")
parser.add_argument('--photometric-band',
                    required=False,
                    default="SDSS_r",
                    dest="photometric_band",
                    help="The name of the photometric band in which the magnitudes in --mag-list are specified. This "
                         "must match a band which is recognised by the pyphot python package.")
parser.add_argument('--magnitudes-post-reddening',
                    action='store_true',
                    dest="magnitudes_reddened",
                    help="Specify that magnitudes in --mag-list are specified post-reddening "
                         "(i.e. are observed magnitudes)")
parser.add_argument('--magnitudes-pre-reddening',
                    action='store_false',
                    dest="magnitudes_reddened",
                    help="Specify that magnitudes in --mag-list are specified pre-reddening "
                         "(i.e. are intrinsic, not observed, magnitudes)")
parser.set_defaults(magnitudes_reddened=True)
parser.add_argument('--snr-definitions-lrs',
                    required=False,
                    default="",
                    dest="snr_definitions_lrs",
                    help="Specify the SNR definition to use for LRS. For example, 'GalDiskHR_536NM' to use the S4 "
                         "green definition of SNR. You can even specify three comma-separated definitions, e.g. "
                         "'GalDiskHR_536NM,GalDiskHR_536NM,GalDiskHR_536NM' to use different SNR metrics for the "
                         "RGB arms within 4MOST LRS, though this is a pretty weird thing to want to do.")
parser.add_argument('--snr-definitions-hrs',
                    required=False,
                    default="",
                    dest="snr_definitions_hrs",
                    help="Specify the SNR definition to use for HRS. For example, 'GalDiskHR_536NM' to use the S4 "
                         "green definition of SNR. You can even specify three comma-separated definitions, e.g. "
                         "'GalDiskHR_536NM,GalDiskHR_536NM,GalDiskHR_536NM' to use different SNR metrics for the "
                         "RGB arms within 4MOST HRS, though this is a pretty weird thing to want to do.")
parser.add_argument('--run-hrs',
                    action='store_true',
                    dest="run_hrs",
                    help="Set 4FS to produce output for 4MOST HRS [default].")
parser.add_argument('--no-run-hrs',
                    action='store_false',
                    dest="run_hrs",
                    help="Set 4FS not to produce output for 4MOST HRS. Setting this will make us run quicker.")
parser.set_defaults(run_hrs=True)
parser.add_argument('--run-lrs',
                    action='store_true',
                    dest="run_lrs",
                    help="Set 4FS to produce output for 4MOST LRS [default].")
parser.add_argument('--no-run-lrs',
                    action='store_false',
                    dest="run_lrs",
                    help="Set 4FS not to produce output for 4MOST LRS. Setting this will make us run quicker.")
parser.set_defaults(run_lrs=True)
parser.add_argument('--binary-path',
                    required=False,
                    default=root_path,
                    dest="binary_path",
                    help="Specify a directory where 4FS binary package is installed.")
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
                    default="/tmp/fourfs_{}.log".format(pid),
                    dest="log_to",
                    help="Specify a log file where we log our progress.")
args = parser.parse_args()

logger.info("Running 4FS on spectra from <{}>, going into <{}> <{}>".format(args.input_library,
                                                                            args.output_library_lrs,
                                                                            args.output_library_hrs))

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

# Create new SpectrumLibrary(s) to hold the output from 4FS
output_libraries = {}

for mode in ({"name": "LRS", "library": args.output_library_lrs, "active": args.run_lrs},
             {"name": "HRS", "library": args.output_library_hrs, "active": args.run_hrs}):
    if mode['active']:
        # Create spectrum library
        library_name = re.sub("/", "_", mode['library'])
        library_path = os_path.join(workspace, library_name)
        output_library = SpectrumLibrarySqlite(path=library_path, create=args.create)
        # We may want to symlink the sqlite3 database file into /tmp for performance reasons
        # This bit of crack-on-a-stick is only useful if /tmp is on a ram disk, though...
        if args.db_in_tmp:
            del output_library
            os.system("mv {} /tmp/tmp_{}.db".format(os_path.join(library_path, "index.db"), library_name))
            os.system("ln -s /tmp/tmp_{}.db {}".format(library_name, os_path.join(library_path, "index.db")))
            output_library = SpectrumLibrarySqlite(path=library_path, create=False)
        output_libraries[mode['name']] = output_library

# Parse any definitions of SNR we were supplied on the command line
if (args.snr_definitions is None) or (len(args.snr_definitions) < 1):
    snr_definitions = None
else:
    snr_definitions = []
    for snr_definition in args.snr_definitions:
        words = snr_definition.split(",")
        snr_definitions.append([words[0], float(words[1]), float(words[2])])

# Look up what definition of SNR is user specified we should use for 4MOST LRS
if len(args.snr_definitions_lrs) < 1:
    # Case 1: None was specified, so we use default
    snr_definitions_lrs = None
else:
    snr_definitions_lrs = args.snr_definitions_lrs.split(",")
    # Case 2: A single definition was supplied which we use for all three arms
    if len(snr_definitions_lrs) == 1:
        snr_definitions_lrs *= 3
    # Case 3: Three definitions were supplied, one for each arm
    assert len(snr_definitions_lrs) == 3

# Look up what definition of SNR is user specified we should use for 4MOST HRS
if len(args.snr_definitions_hrs) < 1:
    # Case 1: None was specified, so we use default
    snr_definitions_hrs = None
else:
    snr_definitions_hrs = args.snr_definitions_hrs.split(",")
    # Case 2: A single definition was supplied which we use for all three arms
    if len(snr_definitions_hrs) == 1:
        snr_definitions_hrs *= 3
    # Case 3: Three definitions were supplied, one for each arm
    assert len(snr_definitions_hrs) == 3

# Parse the list of SNRs that the user specified on the command line
snr_list = [float(item.strip()) for item in args.snr_list.split(",")]

# Parse the list of magnitudes that the user specified on the command line
mag_list = [float(item.strip()) for item in args.mag_list.split(",")]

# Start making a log file
with open(args.log_to, "w") as result_log:
    # Loop over all the magnitudes we are to simulate for each object
    for magnitude in mag_list:

        # Instantiate 4FS wrapper
        etc_wrapper = FourFS(
            path_to_4fs=os_path.join(args.binary_path, "OpSys/ETC"),
            snr_definitions=snr_definitions,
            magnitude=magnitude,
            magnitude_unreddened=not args.magnitudes_reddened,
            photometric_band=args.photometric_band,
            run_lrs=args.run_lrs,
            run_hrs=args.run_hrs,
            lrs_use_snr_definitions=snr_definitions_lrs,
            hrs_use_snr_definitions=snr_definitions_hrs,
            snr_list=snr_list,
            snr_per_pixel=args.per_pixel
        )

        # Simulate observations of each input spectrum in turn
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
            input_spectrum_continuum_normalised_arr = input_library.open(
                ids=continuum_normalised_spectrum_id[0]['specId']
            )

            # Turn the SpectrumArray we got back into a single Spectrum
            input_spectrum_continuum_normalised = input_spectrum_continuum_normalised_arr.extract_item(0)

            # Process spectra through 4FS, which requires both flux- and continuum-normalised input
            degraded_spectra = etc_wrapper.process_spectra(
                spectra_list=((input_spectrum, input_spectrum_continuum_normalised),)
            )

            # Import degraded spectra into output spectrum library

            # Loop over LRS and HRS
            for mode in degraded_spectra:
                # Loop over the spectra we simulated (there was only one!)
                for index in degraded_spectra[mode]:
                    # Loop over the various SNRs we simulated
                    for snr in degraded_spectra[mode][index]:
                        # Create a unique ID for this mock observation
                        unique_id = hashlib.md5(os.urandom(32).encode("hex")).hexdigest()[:16]
                        # Import the flux- and continuum-normalised spectra separately, but give them the same ID
                        for spectrum_type in degraded_spectra[mode][index][snr]:
                            output_libraries[mode].insert(spectra=degraded_spectra[mode][index][snr][spectrum_type],
                                                          filenames=input_spectrum_id['filename'],
                                                          metadata_list={"uid": unique_id})

        # Clean up 4FS
        etc_wrapper.close()

# If we put database in /tmp while adding entries to it, now return it to original location
for mode in ({"name": "LRS", "library": args.output_library_lrs, "active": args.run_lrs},
             {"name": "HRS", "library": args.output_library_hrs, "active": args.run_hrs}):
    if mode['active']:
        if args.db_in_tmp:
            del output_libraries[mode['name']]
            library_name = re.sub("/", "_", mode['library'])
            library_path = os_path.join(workspace, library_name)
            os.system("mv /tmp/tmp_{}.db {}".format(library_name, os_path.join(library_path, "index.db")))
