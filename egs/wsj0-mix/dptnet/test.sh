#!/bin/bash

exp_dir="./exp"

n_sources=2
sr_k=8 # sr_k=8 means sampling rate is 8kHz. Choose from 8kHz or 16kHz.
sr=${sr_k}000
duration=4
max_or_min='min'

wav_root="../../../dataset/wsj0-mix/${n_sources}speakers/wav${sr_k}k/${max_or_min}/tt"
test_list_path="../../../dataset/wsj0-mix/${n_sources}speakers/mix_${n_sources}_spk_${max_or_min}_tt_mix"

# Encoder & decoder
enc_bases='trainable' # choose from 'trainable','Fourier', or 'trainableFourier'
dec_bases='trainable' # choose from 'trainable','Fourier', 'trainableFourier', or 'pinv'
enc_nonlinear='relu' # enc_nonlinear is activated if enc_bases='trainable' and dec_bases!='pinv'
window_fn='' # window_fn is activated if enc_bases='Fourier' or dec_bases='Fourier'
N=64
L=2 # L corresponds to the window length (samples) in this script.

# Separator
F=64
H=128
K=250
P=125
B=6
d_ff=128
h=4
causal=0
sep_norm=1
sep_nonlinear='relu'
sep_dropout=0
mask_nonlinear='relu'

# Criterion
criterion='sisdr'

# Optimizer
optimizer='adam'
k1=2e-1
k2=4e-4
warmup_steps=4000
weight_decay=0
max_norm=5 # 0 is handled as no clipping

batch_size=1
epochs=100

use_cuda=1
overwrite=0
seed=111

. ./path.sh
. parse_options.sh || exit 1

prefix=""

if [ ${enc_bases} = 'trainable' -a -n "${enc_nonlinear}" -a ${dec_bases} != 'pinv' ]; then
    prefix="${preffix}enc-${enc_nonlinear}_"
fi

if [ ${enc_bases} = 'Fourier' -o ${dec_bases} = 'Fourier' ]; then
    prefix="${preffix}${window_fn}-window_"
fi

save_dir="${exp_dir}/${n_sources}mix/sr${sr_k}k_${max_or_min}/${duration}sec/${enc_bases}-${dec_bases}/${criterion}/N${N}_L${L}_F${F}_H${H}_K${K}_P${P}_B${B}_d-ff${d_ff}_h${h}/${prefix}causal${causal}_norm${sep_norm}_${sep_nonlinear}_drop${sep_dropout}_mask-${mask_nonlinear}/b${batch_size}_e${epochs}_${optimizer}-k1${k1}-k2${k2}-decay${weight_decay}-warmup${warmup_steps}_clip${max_norm}/seed${seed}"

model_choice="best"

model_dir="${save_dir}/model"
model_path="${model_dir}/${model_choice}.pth"
log_dir="${save_dir}/log"
out_dir="${save_dir}/test"

if [ ! -e "${log_dir}" ]; then
    mkdir -p "${log_dir}"
fi

time_stamp=`TZ=UTC-9 date "+%Y%m%d-%H%M%S"`

export CUDA_VISIBLE_DEVICES="0"

test.py \
--test_wav_root ${wav_root} \
--test_list_path ${test_list_path} \
--sr ${sr} \
--n_sources ${n_sources} \
--criterion ${criterion} \
--out_dir "${out_dir}" \
--model_path "${model_path}" \
--use_cuda ${use_cuda} \
--overwrite ${overwrite} \
--seed ${seed} | tee "${log_dir}/test_${time_stamp}.log"
