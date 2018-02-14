#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

"""
Take parameters of the SAGA survey, and synthesize spectra using TurboSpectrum.

Parameters downloaded from here: http://sagadatabase.jp/?page_id=10
"""

import os
import re
import time
import hashlib
import argparse
import numpy as np
from os import path as os_path
import logging
import json

from fourgp_speclib import SpectrumLibrarySqlite, Spectrum
from fourgp_telescope_data import FourMost
from fourgp_specsynth import TurboSpectrum

# List of elements whose abundances we pass to TurboSpectrum
# Elements with neutral abundances, e.g. LI1
element_list = (
    "Li", "B", "Be", "C", "N", "O", "Na", "Mg", "Al", "Si", "S", "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Ni",
    "Co", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Mo", "Ru", "Rh", "Pd", "Ag",
    "Cd", "Sn", "Te", "Ba", "La", "Ce", "Pr", "Nd", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er",
    "Tm", "Yb", "Lu", "Hf", "W", "Os", "Ir", "Pt", "Au", "Hg", "Pb", "Bi", "Th", "U")

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s:%(filename)s:%(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S')
logger = logging.getLogger(__name__)
logger.info("Synthesizing AHM2017 spectra")

# Read input parameters
our_path = os_path.split(os_path.abspath(__file__))[0]
root_path = os_path.join(our_path, "..", "..")
pid = os.getpid()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-library',
                    required=False,
                    default="turbospec_saga_sample",
                    dest="library",
                    help="Specify the name of the SpectrumLibrary we are to feed synthesized spectra into.")
parser.add_argument('--workspace', dest='workspace', default="",
                    help="Directory where we expect to find spectrum libraries.")
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
parser.add_argument('--log-dir',
                    required=False,
                    default="/tmp/turbospec_saga_{}".format(pid),
                    dest="log_to",
                    help="Specify a log directory where we log our progress and configuration files.")
parser.add_argument('--dump-to-sqlite-file',
                    required=False,
                    default="",
                    dest="sqlite_out",
                    help="Specify an sqlite3 filename where we dump the stellar parameters of the stars.")
parser.add_argument('--star-list',
                    required=False,
                    default="../../downloads/saga_survey.txt",
                    dest="star_list",
                    help="Specify an ASCII table which lists the stellar parameters of the stars to be synthesized.")
parser.add_argument('--line-lists-dir',
                    required=False,
                    default=root_path,
                    dest="lines_dir",
                    help="Specify a directory where line lists for TurboSpectrum can be found.")
parser.add_argument('--elements',
                    required=False,
                    default="",
                    dest="elements",
                    help="Only read the abundances of a comma-separated list of elements, and use scaled-solar "
                         "abundances for everything else.")
parser.add_argument('--binary-path',
                    required=False,
                    default=root_path,
                    dest="binary_path",
                    help="Specify a directory where Turbospectrum and Interpol packages are installed.")
parser.add_argument('--every',
                    required=False,
                    default=1,
                    type=int,
                    dest="every",
                    help="Only process every nth spectrum. "
                         "This is useful when parallelising this script across multiple processes.")
parser.add_argument('--skip',
                    required=False,
                    default=0,
                    type=int,
                    dest="skip",
                    help="Skip n spectra before starting to process every nth. "
                         "This is useful when parallelising this script across multiple processes.")
parser.add_argument('--limit',
                    required=False,
                    default=0,
                    type=int,
                    dest="limit",
                    help="Only process a maximum of n spectra.")
args = parser.parse_args()

logger.info("Synthesizing SAGA stars with arguments <{}> <{}>".format(args.library, args.star_list))

# Set path to workspace where we create libraries of spectra
workspace = args.workspace if args.workspace else os_path.join(our_path, "..", "workspace")
os.system("mkdir -p {}".format(workspace))


def valid_float(n):
    try:
        test = re.match("<?(.*)+-.*", n)
        if test is not None:
            n = test.group(1)
        n = float(n)
    except ValueError:
        return None
    except TypeError:
        return None
    return n


# Open list of stars
f = open(args.star_list).readlines()
stars = []
columns = f[0].split("\t")

for line in f[1:]:
    star = dict(zip(columns, line.split("\t")))
    valid_star = True
    print len(columns), len(line.split("\t"))
    for essential_item in ['Teff', 'log g', 'Fe']:
        if essential_item not in star:
            valid_star = False
        elif valid_float(star[essential_item]) is None:
            valid_star = False
    if not valid_star:
        continue
    stars.append(star)

# Create new SpectrumLibrary
library_name = re.sub("/", "_", args.library)
library_path = os_path.join(workspace, library_name)
library = SpectrumLibrarySqlite(path=library_path, create=args.create)

# Invoke FourMost data class. Ensure that the spectra we produce are much higher resolution than 4MOST.
# We down-sample them later to whatever resolution we actually want.
FourMostData = FourMost()
lambda_min = FourMostData.bands["LRS"]["lambda_min"]
lambda_max = FourMostData.bands["LRS"]["lambda_max"]
line_lists_path = FourMostData.bands["LRS"]["line_lists_edvardsson"]
spectral_resolution = 50000

# Invoke a TurboSpectrum synthesizer instance
synthesizer = TurboSpectrum(
    turbospec_path=os_path.join(args.binary_path, "turbospectrum-15.1/exec-gf-v15.1"),
    interpol_path=os_path.join(args.binary_path, "interpol_marcs"),
    line_list_paths=[os_path.join(args.lines_dir, line_lists_path)],
    marcs_grid_path=os_path.join(args.binary_path, "fromBengt/marcs_grid"))
counter_output = 0

# Start making log output
os.system("mkdir -p {}".format(args.log_to))
logfile = os.path.join(args.log_to, "synthesis.log")

# Iterate over the spectra we're supposed to be synthesizing
with open(logfile, "w") as result_log:
    for star in stars:
        star_name = star['Object']
        unique_id = hashlib.md5(os.urandom(32).encode("hex")).hexdigest()[:16]

        metadata = {
            "Starname": str(star_name),
            "uid": str(unique_id),
            "Teff": valid_float(star['Teff']),
            "[Fe/H]": valid_float(star['Fe']),
            "logg": valid_float(star['log g'])
        }

        # User can specify that we should only do every nth spectrum, if we're running in parallel
        counter_output += 1
        if (args.limit > 0) and (counter_output > args.limit):
            break
        if (counter_output - args.skip) % args.every != 0:
            continue

        # Configure Turbospectrum with the stellar parameters of the next star
        synthesizer.configure(lambda_min=lambda_min,
                              lambda_max=lambda_max,
                              lambda_delta=float(lambda_min) / spectral_resolution,
                              line_list_paths=[os_path.join(args.lines_dir, line_lists_path)],
                              stellar_mass=1,
                              t_eff=valid_float(star['Teff']),
                              metallicity=valid_float(star['Fe']),
                              log_g=valid_float(star['log g'])
                              )

        # Pass list of the abundances of individual elements to TurboSpectrum
        free_abundances = {}
        for element in element_list:
            for ionisation_state in [" II", " I", ""]:
                    field_name = "{}{}".format(element, ionisation_state)

                    if field_name in star:
                        abundance = valid_float(star[field_name])

                        if (abundance is not None) and np.isfinite(abundance):
                            free_abundances[element] = abundance
                            metadata["[{}/H]".format(element)] = abundance

        # Set free abundances
        synthesizer.configure(free_abundances=free_abundances)

        # Make spectrum
        time_start = time.time()
        turbospectrum_out = synthesizer.synthesise()
        time_end = time.time()

        # Log synthesizer status
        logfile_this = os.path.join(args.log_to, "{}.log".format(star_name))
        open(logfile_this, "w").write(json.dumps(turbospectrum_out))

        # Check for errors
        errors = turbospectrum_out['errors']
        if errors:
            result_log.write("[{}] {:6.0f} sec {}: {}\n".format(time.asctime(), time_end - time_start,
                                                                star_name, errors))
            result_log.flush()
            continue

        # Fetch filename of the spectrum we just generated
        filepath = os_path.join(turbospectrum_out["output_file"])

        # Insert spectrum into SpectrumLibrary
        try:
            filename = "spectrum_{:08d}".format(counter_output)

            # First import continuum-normalised spectrum, which is in columns 1 and 2
            metadata['continuum_normalised'] = 1
            spectrum = Spectrum.from_file(filename=filepath, metadata=metadata, columns=(0, 1), binary=False)
            library.insert(spectra=spectrum, filenames=filename)

            # Then import version with continuum, which is in columns 1 and 3
            metadata['continuum_normalised'] = 0
            spectrum = Spectrum.from_file(filename=filepath, metadata=metadata, columns=(0, 2), binary=False)
            library.insert(spectra=spectrum, filenames=filename)
        except (ValueError, IndexError):
            result_log.write("[{}] {:6.0f} sec {}: {}\n".format(time.asctime(), time_end - time_start,
                                                                star_name, "Could not read bsyn output"))
            result_log.flush()
            continue

        # Update log file to show our progress
        result_log.write("[{}] {:6.0f} sec {}: {}\n".format(time.asctime(), time_end - time_start,
                                                            star_name, "OK"))
        result_log.flush()

# Close TurboSpectrum synthesizer instance
synthesizer.close()