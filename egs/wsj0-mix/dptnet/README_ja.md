## 実験結果
`L` はカーネルサイズを表している．
### 2話者
| encoder | decoder | mask_nonlinear | N | L | F | K | P | B | d_ff | h | causal | batch size | optimizer | lr | gradient clipping | SI-SDRi [dB] | SDRi [dB] | PESQ |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| trainable | trainable | relu | 64 | 2 | 64 | 250 | 125 | 6 | 128 | 4 | False | 2 | adam | 1e-3 | 5 |  |  |  |

### 3話者
| encoder | decoder | mask_nonlinear | N | L | F | K | P | B | d_ff | h | causal | batch size | optimizer | lr | gradient clipping | SI-SDRi [dB] | SDRi [dB] | PESQ |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| trainable | trainable | relu | 64 | 2 | 64 | 250 | 125 | 6 | 128 | 4 | False | 2 | adam | 1e-3 | 5 |  |  |  |