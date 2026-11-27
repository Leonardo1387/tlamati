> English translation of evals/MOAT_ANALYSIS.md. The Spanish original is authoritative.

# CONTEXT MOAT — campaign analysis
source: evals + curves /tmp/tlamati-bench/_raw · codex proxy bytes/4 (validated 0.43% vs official usage)
costs = estimated PRICES table, NOT OpenRouter invoice (EVALS honesty).

## H3 GENERALIZATION + H4 BUSINESS (totals per cell)
model                          harness   ok/n     tin μ  cache% $/OK task  ratio
anthropic_claude-opus-5_5      codex     42/45    64,363    88.0    $0.0558  1.25×
anthropic_claude-opus-5_5      tlamati   45/45    51,654     0.0    $0.2266       
deepseek_deepseek-v3_2         codex     45/45   293,833    96.2    $0.0407  3.05× *1 nulls
deepseek_deepseek-v3_2         hermes    44/45    18,966  1905.6    $0.0435        *1 nulls
deepseek_deepseek-v3_2         opencode  45/45   151,359    91.6    $0.0219       
deepseek_deepseek-v3_2         tlamati   45/45    96,199    88.6    $0.0145       
moonshotai_kimi-k2_7-code      codex     44/45    70,527    87.6    $0.0191  1.60×
moonshotai_kimi-k2_7-code      hermes    40/45    24,018  4744.3    $0.0442       
moonshotai_kimi-k2_7-code      opencode  44/45    53,707    90.7    $0.0139       
moonshotai_kimi-k2_7-code      tlamati   42/45    44,133    84.7    $0.0139       
openai_gpt-6_2-sol             codex     42/45    44,495    62.7    $0.0406  1.83×
openai_gpt-6_2-sol             tlamati   42/45    24,264    85.7    $0.0102       
qwen_qwen3_8-flash             codex     36/45   120,841    92.1    $0.0045  3.10× *2 nulls
qwen_qwen3_8-flash             hermes    45/45     8,620  2382.6    $0.0043       
qwen_qwen3_8-flash             opencode  43/45    72,923    90.3    $0.0024       
qwen_qwen3_8-flash             tlamati   45/45    38,935    81.2    $0.0028       
qwen_qwen3_8-max-0902          codex     44/45    89,601    92.8    $0.0497  1.31×
qwen_qwen3_8-max-0902          tlamati   45/45    68,475    89.8    $0.0387       

codex/tlamati ratio across models: anthropic_claude-opus-5_5=1.25× · deepseek_deepseek-v3_2=3.05× · moonshotai_kimi-k2_7-code=1.60× · openai_gpt-6_2-sol=1.83× · qwen_qwen3_8-flash=3.10× · qwen_qwen3_8-max-0902=1.31×
range: 1.25×–3.10× (median 1.72×) → IT GENERALIZES (same order)

## H2 SCALE — does the ratio grow with task length?
length = tlamati turns on that task (proxy comparable across harnesses)
bucket               tasks  tin μ tlamati  tin μ codex   ratio
short (≤5 turns)        51         33,501       54,877   1.64×
medium (6-12)           23         66,263      165,871   2.50×
long (>12)               7        169,694      385,884   2.27×
(if the ratio RISES from short→long, the advantage compounds and scales;
 if flat, the advantage comes from prefix+calls, not from growth)

## H1 COMPOUNDING + H5 PREFIX — per-call curves (_raw evidence)
cell                                          start     slope    n
codex/anti_bucle_imposible.run1.jsonl            11,299        697    4
codex/anti_bucle_imposible.run2.jsonl            11,299        780    4
codex/anti_bucle_imposible.run3.jsonl            11,299        746    4
codex/context_rot_20_archivos.run1.jsonl         11,307        747    3
codex/context_rot_20_archivos.run2.jsonl         11,307        724    3
codex/context_rot_20_archivos.run3.jsonl         11,307        748    3
codex/conversor.run1.jsonl                       11,199        170    3
codex/conversor.run2.jsonl                       11,199        173    3
codex/conversor.run3.jsonl                       11,199        170    3
codex/crear_modulo.run1.jsonl                    11,224        160    3
codex/crear_modulo.run2.jsonl                    11,224        160    3
codex/crear_modulo.run3.jsonl                    11,224        160    3
codex/edicion_quirurgica_grande.run1.jsonl       11,348        550    6
codex/edicion_quirurgica_grande.run2.jsonl       11,348        753    6
codex/edicion_quirurgica_grande.run3.jsonl       11,348        544    5
codex/git_history.run1.jsonl                     11,300        270    3
codex/git_history.run2.jsonl                     11,300        266    3
codex/git_history.run3.jsonl                     11,300        270    3
codex/import_roto.run1.jsonl                     11,215        172    3
codex/import_roto.run2.jsonl                     11,215        178    3
codex/import_roto.run3.jsonl                     11,215        178    3
codex/instruccion_en_archivo.run1.jsonl          11,257        652    4
codex/instruccion_en_archivo.run2.jsonl          11,257        621    4
codex/instruccion_en_archivo.run3.jsonl          11,257        671    4
codex/multi_archivo.run1.jsonl                   11,275        606    3
codex/multi_archivo.run2.jsonl                   11,275        556    3
codex/multi_archivo.run3.jsonl                   11,275        638    3
codex/offbyone.run1.jsonl                        11,202        182    3
codex/offbyone.run2.jsonl                        11,202        182    3
codex/offbyone.run3.jsonl                        11,202        182    3
codex/output_grande.run1.jsonl                   11,266        109    3
codex/output_grande.run2.jsonl                   11,266        108    3
codex/output_grande.run3.jsonl                   11,266        108    3
codex/promedio.run1.jsonl                        11,201        152    3
codex/promedio.run2.jsonl                        11,201        157    3
codex/promedio.run3.jsonl                        11,201        174    3
codex/recuperacion_test_roto.run1.jsonl          11,354        860    4
codex/recuperacion_test_roto.run2.jsonl          11,354        793    4
codex/recuperacion_test_roto.run3.jsonl          11,354        834    4
codex/rollback_o_regresion.run1.jsonl            11,257        571    4
codex/rollback_o_regresion.run2.jsonl            11,257        732    3
codex/rollback_o_regresion.run3.jsonl            11,257        513    4
codex/test_driven.run1.jsonl                     11,260        502    4
codex/test_driven.run2.jsonl                     11,260        738    3
codex/test_driven.run3.jsonl                     11,260        748    3
tlamati/anti_bucle_imposible.run1.jsonl          13,096        501    3
tlamati/anti_bucle_imposible.run2.jsonl          13,096        479    3
tlamati/anti_bucle_imposible.run3.jsonl          13,096        616    3
tlamati/context_rot_20_archivos.run1.jsonl       13,093        702    5
tlamati/context_rot_20_archivos.run2.jsonl       13,094        852    4
tlamati/context_rot_20_archivos.run3.jsonl       13,108        686    4
tlamati/conversor.run1.jsonl                     12,954        244    3
tlamati/conversor.run2.jsonl                     12,954        244    3
tlamati/conversor.run3.jsonl                     12,954        244    3
tlamati/edicion_quirurgica_grande.run1.jsonl     13,188        968    4
tlamati/edicion_quirurgica_grande.run2.jsonl     13,188      1,041    4
tlamati/edicion_quirurgica_grande.run3.jsonl     13,188        827    5
tlamati/git_history.run1.jsonl                   13,124        441    3
tlamati/git_history.run2.jsonl                   13,124        454    3
tlamati/git_history.run3.jsonl                   13,124        454    3
tlamati/import_roto.run1.jsonl                   12,967        126    3
tlamati/import_roto.run2.jsonl                   12,967        126    3
tlamati/import_roto.run3.jsonl                   12,967        126    3
tlamati/instruccion_en_archivo.run1.jsonl        13,033        749    6
tlamati/instruccion_en_archivo.run2.jsonl        13,203      1,510    3
tlamati/instruccion_en_archivo.run3.jsonl        13,203      1,491    3
tlamati/multi_archivo.run1.jsonl                 13,225        694    4
tlamati/multi_archivo.run2.jsonl                 13,214        885    3
tlamati/multi_archivo.run3.jsonl                 13,214        446    7
tlamati/offbyone.run1.jsonl                      13,108        206    3
tlamati/offbyone.run2.jsonl                      13,108        210    3
tlamati/offbyone.run3.jsonl                      13,108        206    3
tlamati/output_grande.run1.jsonl                 13,221        122    3
tlamati/output_grande.run2.jsonl                 13,221        134    3
tlamati/output_grande.run3.jsonl                 13,221        122    3
tlamati/promedio.run1.jsonl                      12,855        203    3
tlamati/promedio.run2.jsonl                      13,118        212    3
tlamati/promedio.run3.jsonl                      13,118        212    3
tlamati/recuperacion_test_roto.run1.jsonl        13,342      1,069    4
tlamati/recuperacion_test_roto.run2.jsonl        13,212      1,063    4
tlamati/recuperacion_test_roto.run3.jsonl        13,212        898    4
tlamati/rollback_o_regresion.run1.jsonl          13,070        439    3
tlamati/rollback_o_regresion.run2.jsonl          13,070        474    4
tlamati/rollback_o_regresion.run3.jsonl          13,070        314    6
tlamati/test_driven.run1.jsonl                   13,085        401    5
tlamati/test_driven.run2.jsonl                   12,838        547    6
tlamati/test_driven.run3.jsonl                   12,838        389    8

## H7 VARIANCE — is the advantage predictable or single-run luck?
cell                                      tin med  tin stdev     $P50     $P90     $P95   ok%[95CI Wilson]  TO
anthropic_claude-opus-5_5 × codex           55,432     16,990  $0.0553  $0.1083  $0.1265  93% [82-98%]                   0
anthropic_claude-opus-5_5 × tlamati         40,945     20,404  $0.1796  $0.3552  $0.4288 100% [92-100%]                  0
deepseek_deepseek-v3_2 × codex             273,503    200,012  $0.0377  $0.0718  $0.0750 100% [92-100%]                  1
deepseek_deepseek-v3_2 × hermes             14,378     13,181  $0.0337  $0.0825  $0.1166  97% [88-100%]                  1
deepseek_deepseek-v3_2 × opencode          134,010    102,385  $0.0198  $0.0464  $0.0485 100% [92-100%]                  0
deepseek_deepseek-v3_2 × tlamati            58,270     81,640  $0.0102  $0.0291  $0.0417 100% [92-100%]                  0
moonshotai_kimi-k2_7-code × codex           49,134     57,253  $0.0133  $0.0400  $0.0532  97% [88-100%]                  0
moonshotai_kimi-k2_7-code × hermes          11,762     33,203  $0.0389  $0.1422  $0.3072  88% [77-95%]                   0
moonshotai_kimi-k2_7-code × opencode        46,578     25,294  $0.0120  $0.0250  $0.0275  97% [88-100%]                  0
moonshotai_kimi-k2_7-code × tlamati         35,881     27,041  $0.0096  $0.0250  $0.0384  93% [82-98%]                   0
openai_gpt-6_2-sol × codex                  37,531     30,882  $0.0256  $0.0834  $0.1181  93% [82-98%]                   0
openai_gpt-6_2-sol × tlamati                23,227      9,382  $0.0094  $0.0196  $0.0215  93% [82-98%]                   0
qwen_qwen3_8-flash × codex                 114,354     74,842  $0.0045  $0.0097  $0.0102  80% [66-89%]                   0
qwen_qwen3_8-flash × hermes                  8,336      3,987  $0.0036  $0.0063  $0.0089 100% [92-100%]                  0
qwen_qwen3_8-flash × opencode               57,275     48,622  $0.0020  $0.0048  $0.0054  95% [85-99%]                   0
qwen_qwen3_8-flash × tlamati                25,692     35,612  $0.0019  $0.0072  $0.0079 100% [92-100%]                  0
qwen_qwen3_8-max-0902 × codex               75,212     49,443  $0.0427  $0.0969  $0.1287  97% [88-100%]                  0
qwen_qwen3_8-max-0902 × tlamati             56,684     37,730  $0.0300  $0.0646  $0.0666 100% [92-100%]                  0

### Bootstrap of the codex/tlamati ratio (unit = task, B=10,000, fixed seed)
model                            point ratio              95CI P(ratio>1.5)
anthropic_claude-opus-5_5                1.25× [1.05–1.46]×               0.9%
deepseek_deepseek-v3_2                   3.08× [2.61–3.67]×             100.0%
moonshotai_kimi-k2_7-code                1.60× [1.30–2.01]×              66.9%
openai_gpt-6_2-sol                       1.83× [1.55–2.14]×              99.1%
qwen_qwen3_8-flash                       3.10× [2.36–4.32]×             100.0%
qwen_qwen3_8-max-0902                    1.31× [1.11–1.57]×               7.0%
(pitch phrase = 'the advantage is X× [95CI a–b]'; P(ratio>1.5) is the
 bootstrap probability that the advantage is at least 1.5×)

## H8 DECOMPOSITION — where does the advantage come from? (prefix × slope × calls)
model: total ≈ start + slope·(n-1) per call; the ratio is decomposed
- reference 19-Nov instruccion_en_archivo (flash) [tlamati]: n=7 calls · start 7,649 · slope +717/call · total 69,344
- reference 19-Nov instruccion_en_archivo (flash) [codex]: n=14 calls · start 11,258 · slope +1,212/call · total 263,582
- codex/anti_bucle_imposible.run1 [codex]: n=4 calls · start 11,299 · slope +697/call · total 50,287
- codex/anti_bucle_imposible.run2 [codex]: n=4 calls · start 11,299 · slope +780/call · total 50,690
- codex/anti_bucle_imposible.run3 [codex]: n=4 calls · start 11,299 · slope +746/call · total 50,517
- codex/context_rot_20_archivos.run1 [codex]: n=3 calls · start 11,307 · slope +747/call · total 36,656
- codex/context_rot_20_archivos.run2 [codex]: n=3 calls · start 11,307 · slope +724/call · total 36,610
- codex/context_rot_20_archivos.run3 [codex]: n=3 calls · start 11,307 · slope +748/call · total 36,657
- codex/conversor.run1 [codex]: n=3 calls · start 11,199 · slope +170/call · total 34,154
- codex/conversor.run2 [codex]: n=3 calls · start 11,199 · slope +173/call · total 34,160
- codex/conversor.run3 [codex]: n=3 calls · start 11,199 · slope +170/call · total 34,154
- codex/crear_modulo.run1 [codex]: n=3 calls · start 11,224 · slope +160/call · total 34,189
- codex/crear_modulo.run2 [codex]: n=3 calls · start 11,224 · slope +160/call · total 34,189
- codex/crear_modulo.run3 [codex]: n=3 calls · start 11,224 · slope +160/call · total 34,189
- codex/edicion_quirurgica_grande.run1 [codex]: n=6 calls · start 11,348 · slope +550/call · total 75,631
- codex/edicion_quirurgica_grande.run2 [codex]: n=6 calls · start 11,348 · slope +753/call · total 78,300
- codex/edicion_quirurgica_grande.run3 [codex]: n=5 calls · start 11,348 · slope +544/call · total 61,794
- codex/git_history.run1 [codex]: n=3 calls · start 11,300 · slope +270/call · total 34,857
- codex/git_history.run2 [codex]: n=3 calls · start 11,300 · slope +266/call · total 34,850
- codex/git_history.run3 [codex]: n=3 calls · start 11,300 · slope +270/call · total 34,857
- codex/import_roto.run1 [codex]: n=3 calls · start 11,215 · slope +172/call · total 34,236
- codex/import_roto.run2 [codex]: n=3 calls · start 11,215 · slope +178/call · total 34,258
- codex/import_roto.run3 [codex]: n=3 calls · start 11,215 · slope +178/call · total 34,258
- codex/instruccion_en_archivo.run1 [codex]: n=4 calls · start 11,257 · slope +652/call · total 50,059
- codex/instruccion_en_archivo.run2 [codex]: n=4 calls · start 11,257 · slope +621/call · total 49,867
- codex/instruccion_en_archivo.run3 [codex]: n=4 calls · start 11,257 · slope +671/call · total 49,730
- codex/multi_archivo.run1 [codex]: n=3 calls · start 11,275 · slope +606/call · total 35,867
- codex/multi_archivo.run2 [codex]: n=3 calls · start 11,275 · slope +556/call · total 35,771
- codex/multi_archivo.run3 [codex]: n=3 calls · start 11,275 · slope +638/call · total 35,933
- codex/offbyone.run1 [codex]: n=3 calls · start 11,202 · slope +182/call · total 34,219
- codex/offbyone.run2 [codex]: n=3 calls · start 11,202 · slope +182/call · total 34,219
- codex/offbyone.run3 [codex]: n=3 calls · start 11,202 · slope +182/call · total 34,221
- codex/output_grande.run1 [codex]: n=3 calls · start 11,266 · slope +109/call · total 34,139
- codex/output_grande.run2 [codex]: n=3 calls · start 11,266 · slope +108/call · total 34,136
- codex/output_grande.run3 [codex]: n=3 calls · start 11,266 · slope +108/call · total 34,135
- codex/promedio.run1 [codex]: n=3 calls · start 11,201 · slope +152/call · total 34,104
- codex/promedio.run2 [codex]: n=3 calls · start 11,201 · slope +157/call · total 34,124
- codex/promedio.run3 [codex]: n=3 calls · start 11,201 · slope +174/call · total 34,158
- codex/recuperacion_test_roto.run1 [codex]: n=4 calls · start 11,354 · slope +860/call · total 50,277
- codex/recuperacion_test_roto.run2 [codex]: n=4 calls · start 11,354 · slope +793/call · total 50,053
- codex/recuperacion_test_roto.run3 [codex]: n=4 calls · start 11,354 · slope +834/call · total 50,187
- codex/rollback_o_regresion.run1 [codex]: n=4 calls · start 11,257 · slope +571/call · total 48,681
- codex/rollback_o_regresion.run2 [codex]: n=3 calls · start 11,257 · slope +732/call · total 36,521
- codex/rollback_o_regresion.run3 [codex]: n=4 calls · start 11,257 · slope +513/call · total 48,911
- codex/test_driven.run1 [codex]: n=4 calls · start 11,260 · slope +502/call · total 48,931
- codex/test_driven.run2 [codex]: n=3 calls · start 11,260 · slope +738/call · total 36,304
- codex/test_driven.run3 [codex]: n=3 calls · start 11,260 · slope +748/call · total 36,324
- tlamati/anti_bucle_imposible.run1 [tlamati]: n=3 calls · start 13,096 · slope +501/call · total 40,997
- tlamati/anti_bucle_imposible.run2 [tlamati]: n=3 calls · start 13,096 · slope +479/call · total 40,945
- tlamati/anti_bucle_imposible.run3 [tlamati]: n=3 calls · start 13,096 · slope +616/call · total 41,329
- tlamati/context_rot_20_archivos.run1 [tlamati]: n=5 calls · start 13,093 · slope +702/call · total 75,183
- tlamati/context_rot_20_archivos.run2 [tlamati]: n=4 calls · start 13,094 · slope +852/call · total 58,699
- tlamati/context_rot_20_archivos.run3 [tlamati]: n=4 calls · start 13,108 · slope +686/call · total 57,099
- tlamati/conversor.run1 [tlamati]: n=3 calls · start 12,954 · slope +244/call · total 39,531
- tlamati/conversor.run2 [tlamati]: n=3 calls · start 12,954 · slope +244/call · total 39,531
- tlamati/conversor.run3 [tlamati]: n=3 calls · start 12,954 · slope +244/call · total 39,531
- tlamati/edicion_quirurgica_grande.run1 [tlamati]: n=4 calls · start 13,188 · slope +968/call · total 57,505
- tlamati/edicion_quirurgica_grande.run2 [tlamati]: n=4 calls · start 13,188 · slope +1,041/call · total 57,878
- tlamati/edicion_quirurgica_grande.run3 [tlamati]: n=5 calls · start 13,188 · slope +827/call · total 73,836
- tlamati/git_history.run1 [tlamati]: n=3 calls · start 13,124 · slope +441/call · total 40,828
- tlamati/git_history.run2 [tlamati]: n=3 calls · start 13,124 · slope +454/call · total 40,882
- tlamati/git_history.run3 [tlamati]: n=3 calls · start 13,124 · slope +454/call · total 40,882
- tlamati/import_roto.run1 [tlamati]: n=3 calls · start 12,967 · slope +126/call · total 39,297
- tlamati/import_roto.run2 [tlamati]: n=3 calls · start 12,967 · slope +126/call · total 39,297
- tlamati/import_roto.run3 [tlamati]: n=3 calls · start 12,967 · slope +126/call · total 39,297
- tlamati/instruccion_en_archivo.run1 [tlamati]: n=6 calls · start 13,033 · slope +749/call · total 94,728
- tlamati/instruccion_en_archivo.run2 [tlamati]: n=3 calls · start 13,203 · slope +1,510/call · total 44,897
- tlamati/instruccion_en_archivo.run3 [tlamati]: n=3 calls · start 13,203 · slope +1,491/call · total 44,858
- tlamati/multi_archivo.run1 [tlamati]: n=4 calls · start 13,225 · slope +694/call · total 58,202
- tlamati/multi_archivo.run2 [tlamati]: n=3 calls · start 13,214 · slope +885/call · total 42,738
- tlamati/multi_archivo.run3 [tlamati]: n=7 calls · start 13,214 · slope +446/call · total 106,252
- tlamati/offbyone.run1 [tlamati]: n=3 calls · start 13,108 · slope +206/call · total 39,858
- tlamati/offbyone.run2 [tlamati]: n=3 calls · start 13,108 · slope +210/call · total 39,866
- tlamati/offbyone.run3 [tlamati]: n=3 calls · start 13,108 · slope +206/call · total 39,858
- tlamati/output_grande.run1 [tlamati]: n=3 calls · start 13,221 · slope +122/call · total 40,061
- tlamati/output_grande.run2 [tlamati]: n=3 calls · start 13,221 · slope +134/call · total 40,109
- tlamati/output_grande.run3 [tlamati]: n=3 calls · start 13,221 · slope +122/call · total 40,061
- tlamati/promedio.run1 [tlamati]: n=3 calls · start 12,855 · slope +203/call · total 39,107
- tlamati/promedio.run2 [tlamati]: n=3 calls · start 13,118 · slope +212/call · total 39,914
- tlamati/promedio.run3 [tlamati]: n=3 calls · start 13,118 · slope +212/call · total 39,914
- tlamati/recuperacion_test_roto.run1 [tlamati]: n=4 calls · start 13,342 · slope +1,069/call · total 60,029
- tlamati/recuperacion_test_roto.run2 [tlamati]: n=4 calls · start 13,212 · slope +1,063/call · total 59,476
- tlamati/recuperacion_test_roto.run3 [tlamati]: n=4 calls · start 13,212 · slope +898/call · total 57,829
- tlamati/rollback_o_regresion.run1 [tlamati]: n=3 calls · start 13,070 · slope +439/call · total 40,516
- tlamati/rollback_o_regresion.run2 [tlamati]: n=4 calls · start 13,070 · slope +474/call · total 55,026
- tlamati/rollback_o_regresion.run3 [tlamati]: n=6 calls · start 13,070 · slope +314/call · total 83,670
- tlamati/test_driven.run1 [tlamati]: n=5 calls · start 13,085 · slope +401/call · total 70,379
- tlamati/test_driven.run2 [tlamati]: n=6 calls · start 12,838 · slope +547/call · total 87,100
- tlamati/test_driven.run3 [tlamati]: n=8 calls · start 12,838 · slope +389/call · total 117,853
  → reference 19-Nov instruccion_en_archivo (flash): total ratio 3.80× decomposed:
     prefix: tlamati 7,649 vs codex 11,258 = 1.47×
     slope: tlamati +717 vs codex +1,212 = 1.69×
     calls: tlamati 7 vs codex 14 = 2.00×
     product of factors ≈ 4.97× (approximate: the terms overlap)

## VERDICT (filled in with the numbers above)
- H3: median ratio 1.72× across 6 models
- H1/H5: see curves section (19-Nov reference if no _raw)
- H2: see buckets — it IS the proof of compounding in the current corpus
