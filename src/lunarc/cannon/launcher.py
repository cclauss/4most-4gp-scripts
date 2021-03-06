#!../../../../virtualenv/bin/python3
# -*- coding: utf-8 -*-

# NB: The shebang line above assumes you've installed a python virtual environment alongside your working copy of the
# <4most-4gp-scripts> git repository. It also only works if you invoke this python script from the directory where it
# is located. If these two assumptions are incorrect (e.g. you're using Conda), you can still use this script by typing
# <python launcher.py>, but <./launcher.py> will not work.

"""

Take a shell script which runs a load of tests through the Cannon, using <cannon_test.py>, and run all the tests in
parallel using the SLURM job management system on lunarc.

We parse the contents of the shell script, removing any commands which aren't running python, and piecing together
python commands which have been split over many lines.

Unfortunately, it seems very necessary to run this in SLURM's exclusive mode. Otherwise, the out of memory killer
tends to kill your jobs.

"""

import argparse
import logging
import os
import re

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s:%(filename)s:%(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S')
logger = logging.getLogger(__name__)

# Read input parameters
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--job_list', action="append", dest='jobs',
                    help="List of shell scripts containing python commands which run tests on the Cannon.")
args = parser.parse_args()

uid = os.getpid()

slurm_script = """#!/bin/sh
# requesting the number of nodes needed
#SBATCH -N 1
#SBATCH --exclusive
#
# job time, change for what your job requires
#SBATCH -t 150:00:00
#
# job name and output file names
#SBATCH -J cannon_{destination_name}
#SBATCH -o stdout_cannon_{destination_name}_%j.out
#SBATCH -e stderr_cannon_{destination_name}_%j.out
cat $0

module add GCC/4.9.3-binutils-2.25  OpenMPI/1.8.8 CFITSIO/3.38  GCCcore/6.4.0 SQLite/3.20.1 Anaconda3

# This line used to work up until Feb 2019...
source activate myenv

# ... but since it's stopped working, this line makes sure we use the right python ...
export PATH="/home/dominic/.conda/envs/myenv/bin:$PATH"

cd {python_directory}
echo Starting rsync: `date`
echo Temporary directory: {temporary_directory}
mkdir {temporary_directory}
{rsync_commands}
echo Rsync done: `date`
python cannon_test.py --workspace "{temporary_directory}" {python_arguments}

"""

os.system("mkdir -p ../../../output_data/cannon")

counter = 0
for job in args.jobs:
    # This is the parent directory of where the shell script is. If the shell script is in the <examples> subdirectory
    # of <test_cannon>, then we find the <cannon_test.py> python script up one level
    config_path = os.path.split(os.path.abspath(job + "/../"))[0]

    line_buffer = ""
    destination = ""
    libraries = []

    # Start piecing together the python command line to run this job
    start_string = "python3 cannon_test.py"

    for line in open(job):
        line = line.strip()
        # Ignore blank lines and lines which begin with a hash
        if (len(line) == 0) or (line[0] == '#'):
            continue

        # Check for output destination
        test = re.match("--output-file \"(.*)\"", line)
        if test is not None:
            destination = test.group(1)

        # Check for spectrum libraries we need
        test = re.search("(?:--train|--test) \"([^\"\\[]*)([^\"]*)?\"", line)
        if test is not None:
            libraries.append(test.group(1))

        # Lines which end in backslashes append
        if line[-1] == "\\":
            line_buffer = "{} {}".format(line_buffer, line[:-1])
            continue

        # Put current line onto the end of line buffer
        line = "{} {}".format(line_buffer, line).strip()
        line_buffer = ""

        # Ignore shell commands which don't run Cannon tests
        if not line.startswith(start_string):
            continue

        # If file product already exists, don't need to recreate it
        destination = os.path.join(config_path, destination) + ".full.json.gz"
        if os.path.exists(destination):
            print("-  Product <{}> already exists".format(destination))
            continue
        else:
            print("++ Product <{}> needs making".format(destination))

        # Create rsync command to copy spectrum libraries to node local storage
        run_id = "{}_{}".format(uid, counter)
        tmp_dir = "${{TMPDIR}}/cannon_{}".format(run_id)
        rsyncs = ["rsync -a ../../../workspace/{} {}/".format(library, tmp_dir) for library in libraries]
        rsync_commands = "\n".join(rsyncs)
        libraries = []

        command = line[len(start_string):]
        counter += 1
        slurm_tmp_filename = "tmp_{}.sh".format(run_id)

        # Write a slurm job description file
        with open(slurm_tmp_filename, "w") as f:
            f.write(slurm_script.format(python_directory=config_path,
                                        temporary_directory=tmp_dir,
                                        rsync_commands=rsync_commands,
                                        python_arguments=command,
                                        destination_name=os.path.split(destination)[1]))

        # This line submits the job to slurm, but I usuaully choose to do this manually
        # os.system("sbatch {}".format(slurm_tmp_filename))
