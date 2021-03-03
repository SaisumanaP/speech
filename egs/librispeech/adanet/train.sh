#!/bin/bash

exp_dir="./exp"
continue_from=""

n_sources=2

wav_root="../../../dataset/LibriSpeech"
train_json_path="../../../dataset/LibriSpeech/train-clean-100/train-100-${n_sources}mix.json"
valid_json_path="../../../dataset/LibriSpeech/dev-clean/valid-${n_sources}mix.json"

sr=16000

window_fn='hamming'
fft_size=256
hop_size=64
threshold=40

# Model configuration
K=20
H=256
B=4
N=6
causal=0
mask_nonlinear='sigmoid'

# Criterion
criterion='l2loss'

# Optimizer
optimizer='rmsprop'
lr=1e-4
weight_decay=0

batch_size=4
epochs=100

use_cuda=1
overwrite=0
seed=111

. ./path.sh
. parse_options.sh || exit 1

save_dir="${exp_dir}/${n_sources}mix/${criterion}/stft${fft_size}-${hop_size}_${window_fn}-window_threshold${threshold}/K${K}_H${H}_B${B}_N${N}_causal${causal}_mask-${mask_nonlinear}/b${batch_size}_e${epochs}_${optimizer}-lr${lr}-decay${weight_decay}/seed${seed}"

model_dir="${save_dir}/model"
loss_dir="${save_dir}/loss"
sample_dir="${save_dir}/sample"
log_dir="${save_dir}/log"

if [ ! -e "${log_dir}" ]; then
    mkdir -p "${log_dir}"
fi

time_stamp=`TZ=UTC-9 date "+%Y%m%d-%H%M%S"`

export CUDA_VISIBLE_DEVICES="0"

train.py \
--wav_root ${wav_root} \
--train_json_path ${train_json_path} \
--valid_json_path ${valid_json_path} \
--sr ${sr} \
--window_fn ${window_fn} \
--threshold ${threshold} \
--fft_size ${fft_size} \
--hop_size ${hop_size} \
-K ${K} \
-H ${H} \
-B ${B} \
-N ${N} \
--causal ${causal} \
--mask_nonlinear ${mask_nonlinear} \
--n_sources ${n_sources} \
--criterion ${criterion} \
--optimizer ${optimizer} \
--lr ${lr} \
--weight_decay ${weight_decay} \
--batch_size ${batch_size} \
--epochs ${epochs} \
--model_dir "${model_dir}" \
--loss_dir "${loss_dir}" \
--sample_dir "${sample_dir}" \
--continue_from "${continue_from}" \
--use_cuda ${use_cuda} \
--overwrite ${overwrite} \
--seed ${seed} | tee "${log_dir}/train_${time_stamp}.log"

