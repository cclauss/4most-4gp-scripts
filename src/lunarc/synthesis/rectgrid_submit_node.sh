#!/bin/sh
# document this script to stdout (assumes redirection from caller)
cat $0

# receive my worker number
export item=$1
export WRK_NB=$1

# activate conda python environment
source activate myenv

# create worker-private subdirectory in $SNIC_TMP
# export WRK_DIR=$SNIC_TMP/WRK_${WRK_NB}
# mkdir $WRK_DIR

# create a variable to address the "job directory"
# export JOB_DIR=$SLURM_SUBMIT_DIR/job_${WRK_NB}

# now copy the input data and program from there

# cd $JOB_DIR
# cp -p input.dat processor $WRK_DIR

# change to the execution directory
# cd $WRK_DIR

# run the program
cd ${HOME}/iwg7_pipeline/4most-4gp-scripts/src/scripts/synthesize_grids

echo Temporary directory: ${TMPDIR}/workspace
mkdir ${TMPDIR}/workspace

python synthesize_rect_grid.py --every 80 --skip ${item} --create \
                               --workspace "${TMPDIR}/workspace" \
                               --output-library turbospec_rect_grid_${item} \
                               --log-dir ../../../output_data/logs/rect_grid_stars_${item}

echo Starting rsync: `date`
rsync -a ${TMPDIR}/workspace/turbospec_* ../../../workspace
echo Rsync done: `date`

# rescue the results back to job directory
# cp -p result.dat ${JOB_DIR}

# clean up the local disk and remove the worker-private directory

# cd $SNIC_TMP
# rm -rf WRK_${WRK_NB}