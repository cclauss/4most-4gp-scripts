#!/bin/sh
# requesting the number of nodes needed
#SBATCH -N 4
#SBATCH --exclusive
#
# job time, change for what your job farm requires
#SBATCH -t 14:00:00
#
# job name and output file names
#SBATCH -J ges_dwarfs_farm
#SBATCH -o stdout_ges_dwarfs_farm_%j.out
#SBATCH -e stderr_ges_dwarfs_farm_%j.out
cat $0

module add GCC/4.9.3-binutils-2.25  OpenMPI/1.8.8 CFITSIO/3.38  GCCcore/6.4.0 SQLite/3.20.1 Anaconda3

# activate python environment

# This line used to work up until Feb 2019...
source activate myenv

# ... but since it's stopped working, this line makes sure we use the right python ...
export PATH="/home/dominic/.conda/envs/myenv/bin:$PATH"

# set the number of jobs - change for your requirements
export NB_of_jobs=80

# Loop over the job number
for ((i=0; i<$NB_of_jobs; i++))
do
    srun -Q --exclusive -n 1 -N 1 \
        ges_dwarfs_submit_node.sh $i &> worker_${SLURM_JOB_ID}_${i} &
    sleep 1
done

# keep the wait statement, it is important!
wait

