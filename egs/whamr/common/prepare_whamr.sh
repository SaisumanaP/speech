#!/bin/bash

whamr_root="../../../dataset/WHAM!"
wham_noise_root="../../../dataset/WHAM!_noise"
create_from="wsjmix" # or "scratch"

# WSJ0
wsj0_root="../../../dataset/wsj0_wav"
wsjmix_8k="../../../dataset/wsj0-mix/2speakers/wav8k"
wsjmix_16k="../../../dataset/wsj0-mix/2speakers/wav16k"

. ./parse_options.sh || exit 1

# Prepare wham noise
. ./prepare_wham_noise.sh \
--wham_noise_root "${wham_noise_root}"

# Prepare whamr mixture
file="whamr_scripts.tar.gz"

if [ -e "${whamr_root}/whamr_scripts/create_wham_from_scratch.py" ] ; then
    echo "Already downloaded whamr_scripts."
else
    if [ ! -d "${whamr_root}" ] ; then
        mkdir -p "${whamr_root}"
    fi
    wget "https://storage.googleapis.com/whisper-public/${file}" -P "/tmp/"
    tar -xzvf "/tmp/${file}" -C "${whamr_root}"
    rm "/tmp/${file}"
fi

work_dir="$PWD"

cd "${whamr_root}/whamr_scripts/"

python create_wham_from_scratch.py \
--wsj0-root "${wsj0_root}" \
--wham-noise-root "${wham_noise_root}" \
--output-dir "${whamr_root}"

cd "${work_dir}"