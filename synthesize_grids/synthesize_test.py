#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Synthesize a handful of test stars using TurboSpectrum.
"""

import os
import re
import time
import argparse
from os import path as os_path
import logging

from fourgp_speclib import SpectrumLibrarySqlite, Spectrum
from fourgp_specsynth import TurboSpectrum

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s:%(filename)s:%(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S')
logger = logging.getLogger(__name__)
logger.info("Synthesizing spectra for some simple test stars")

# Read input parameters
our_path = os_path.split(os_path.abspath(__file__))[0]
root_path = os_path.join(our_path, "..", "..")
pid = os.getpid()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-library',
                    required=False,
                    default='demo_stars',
                    dest='library',
                    help="Specify the name of the SpectrumLibrary we are to feed synthesized spectra into.")
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
                    default='/tmp/turbospec_test_{}.log'.format(pid),
                    dest='log_to',
                    help="Specify a log file where we log our progress.")
parser.add_argument('--line-lists-dir',
                    required=False,
                    default=os_path.join(our_path, "..", "..", "fromBengt", "line_lists", "3700-9500"),
                    dest='lines_dir',
                    help="Specify a directory where line lists for TurboSpectrum can be found.")
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

logger.info("Synthesizing test stars with arguments <{}> <{}>".format(args.library, args.lines_dir))

# Set path to workspace where we create libraries of spectra
root_path = os_path.join(our_path, "..", "..")
workspace = os_path.join(our_path, "..", "workspace")
os.system("mkdir -p {}".format(workspace))

# Create new SpectrumLibrary
library_name = re.sub("/", "_", args.library)
library_path = os_path.join(workspace, library_name)
library = SpectrumLibrarySqlite(path=library_path, create=args.create, binary_spectra=False)

# Invoke a TurboSpectrum synthesizer instance
synthesizer = TurboSpectrum(
    turbospec_path=os_path.join(args.binary_path, "turbospectrum-15.1/exec-gf-v15.1"),
    interpol_path=os_path.join(args.binary_path, "interpol_marcs"),
    line_list_paths=args.lines_dir,
    marcs_grid_path=os_path.join(args.binary_path, "fromBengt/marcs_grid"))
counter_output = 0

# Iterate over the spectra we're supposed to be synthesizing
with open(args.log_to, "w") as result_log:
    for t_eff in (3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000):
        # User can specify that we should only do every nth spectrum, if we're running in parallel
        counter_output += 1
        if (args.limit > 0) and (counter_output > args.limit):
            break
        if (counter_output - args.skip) % args.every != 0:
            continue

        # Configure Turbospectrum with the stellar parameters of the next star
        synthesizer.configure(t_eff=t_eff,
                              metallicity=0,
                              log_g=2,
                              lambda_min=3700,
                              lambda_max=9500,
                              lambda_delta=1,
                              line_list_paths=args.lines_dir
                              )

        # Make spectrum
        turbospectrum_out = synthesizer.synthesise()

        # Check for errors
        errors = turbospectrum_out['errors']
        if errors:
            result_log.write("[{}] {:.0f}: {}\n".format(time.asctime(), t_eff, errors))
            result_log.flush()
            continue

        # Fetch filename of the spectrum we just generated
        filepath = os_path.join(turbospectrum_out["output_file"])

        # Insert spectrum into SpectrumLibrary
        metadata = {'Teff': t_eff, '[Fe/H]': 0, 'logg': 2}
        try:
            filename = os_path.split(filepath)[1]

            # First import continuum-normalised spectrum, which is in columns 1 and 2
            metadata['continuum_normalised'] = 1
            spectrum = Spectrum.from_file(filename=filepath, metadata=metadata, columns=(0, 1), binary=False)
            library.insert(spectra=spectrum, filenames=filename)

            # Then import version with continuum, which is in columns 1 and 3
            metadata['continuum_normalised'] = 0
            spectrum = Spectrum.from_file(filename=filepath, metadata=metadata, columns=(0, 2), binary=False)
            library.insert(spectra=spectrum, filenames=filename)
        except (ValueError, IndexError):
            result_log.write("[{}] {:.0f}: {}\n".format(time.asctime(), t_eff, "Could not read bsyn output"))
            result_log.flush()
            continue

        result_log.write("[{}] {:.0f}: {}\n".format(time.asctime(), t_eff, "OK"))
        result_log.flush()

# Close TurboSpectrum synthesizer instance
synthesizer.close()