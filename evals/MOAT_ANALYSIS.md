# MOAT DE CONTEXTO — análisis de campaña
fuente: evals + curvas /tmp/tlamati-bench/_raw · proxy codex bytes/4 (validado 0.43% vs usage oficial)
costos = tabla PRICES estimada, NO factura OpenRouter (honestidad EVALS).

## H3 GENERALIZACIÓN + H4 NEGOCIO (totales por celda)
modelo                         arnés      ok/n     tin μ  cache% $/tarea OK  ratio
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

ratio codex/tlamati entre modelos: anthropic_claude-opus-5_5=1.25× · deepseek_deepseek-v3_2=3.05× · moonshotai_kimi-k2_7-code=1.60× · openai_gpt-6_2-sol=1.83× · qwen_qwen3_8-flash=3.10× · qwen_qwen3_8-max-0902=1.31×
rango: 1.25×–3.10× (mediana 1.72×) → SE GENERALIZA (mismo orden)

## H2 ESCALA — ¿el ratio crece con la longitud de la tarea?
longitud = turnos de tlamati en esa tarea (proxy comparable entre arneses)
bucket               tareas  tin μ tlamati  tin μ codex   ratio
corta (≤5 turnos)        51         33,501       54,877   1.64×
media (6-12)             23         66,263      165,871   2.50×
larga (>12)               7        169,694      385,884   2.27×
(si el ratio SUBE de corta→larga, la ventaja es compuesta y escala;
 si es plano, la ventaja viene del prefijo+llamadas, no del crecimiento)

## H1 COMPOUNDING + H5 PREFIJO — curvas por llamada (evidencia _raw)
celda                                          arranque  pendiente    n
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

## H7 VARIANZA — ¿la ventaja es predecible o suerte de una corrida?
celda                                      tin med  tin stdev     $P50     $P90     $P95   ok%[IC95 Wilson]  TO
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

### Bootstrap del ratio codex/tlamati (unidad = tarea, B=10,000, semilla fija)
modelo                           ratio puntual             IC95 P(ratio>1.5)
anthropic_claude-opus-5_5                1.25× [1.05–1.46]×               0.9%
deepseek_deepseek-v3_2                   3.08× [2.61–3.67]×             100.0%
moonshotai_kimi-k2_7-code                1.60× [1.30–2.01]×              66.9%
openai_gpt-6_2-sol                       1.83× [1.55–2.14]×              99.1%
qwen_qwen3_8-flash                       3.10× [2.36–4.32]×             100.0%
qwen_qwen3_8-max-0902                    1.31× [1.11–1.57]×               7.0%
(frase del pitch = 'la ventaja es X× [IC95 a–b]'; P(ratio>1.5) es la
 probabilidad bootstrap de que la ventaja sea al menos 1.5×)

## H8 DESCOMPOSICIÓN — ¿de dónde sale la ventaja? (prefijo × pendiente × llamadas)
modelo: total ≈ arranque + pendiente·(n-1) por llamada; se descompone el ratio
- referencia 19-nov instruccion_en_archivo (flash) [tlamati]: n=7 llamadas · arranque 7,649 · pendiente +717/llamada · total 69,344
- referencia 19-nov instruccion_en_archivo (flash) [codex]: n=14 llamadas · arranque 11,258 · pendiente +1,212/llamada · total 263,582
- codex/anti_bucle_imposible.run1 [codex]: n=4 llamadas · arranque 11,299 · pendiente +697/llamada · total 50,287
- codex/anti_bucle_imposible.run2 [codex]: n=4 llamadas · arranque 11,299 · pendiente +780/llamada · total 50,690
- codex/anti_bucle_imposible.run3 [codex]: n=4 llamadas · arranque 11,299 · pendiente +746/llamada · total 50,517
- codex/context_rot_20_archivos.run1 [codex]: n=3 llamadas · arranque 11,307 · pendiente +747/llamada · total 36,656
- codex/context_rot_20_archivos.run2 [codex]: n=3 llamadas · arranque 11,307 · pendiente +724/llamada · total 36,610
- codex/context_rot_20_archivos.run3 [codex]: n=3 llamadas · arranque 11,307 · pendiente +748/llamada · total 36,657
- codex/conversor.run1 [codex]: n=3 llamadas · arranque 11,199 · pendiente +170/llamada · total 34,154
- codex/conversor.run2 [codex]: n=3 llamadas · arranque 11,199 · pendiente +173/llamada · total 34,160
- codex/conversor.run3 [codex]: n=3 llamadas · arranque 11,199 · pendiente +170/llamada · total 34,154
- codex/crear_modulo.run1 [codex]: n=3 llamadas · arranque 11,224 · pendiente +160/llamada · total 34,189
- codex/crear_modulo.run2 [codex]: n=3 llamadas · arranque 11,224 · pendiente +160/llamada · total 34,189
- codex/crear_modulo.run3 [codex]: n=3 llamadas · arranque 11,224 · pendiente +160/llamada · total 34,189
- codex/edicion_quirurgica_grande.run1 [codex]: n=6 llamadas · arranque 11,348 · pendiente +550/llamada · total 75,631
- codex/edicion_quirurgica_grande.run2 [codex]: n=6 llamadas · arranque 11,348 · pendiente +753/llamada · total 78,300
- codex/edicion_quirurgica_grande.run3 [codex]: n=5 llamadas · arranque 11,348 · pendiente +544/llamada · total 61,794
- codex/git_history.run1 [codex]: n=3 llamadas · arranque 11,300 · pendiente +270/llamada · total 34,857
- codex/git_history.run2 [codex]: n=3 llamadas · arranque 11,300 · pendiente +266/llamada · total 34,850
- codex/git_history.run3 [codex]: n=3 llamadas · arranque 11,300 · pendiente +270/llamada · total 34,857
- codex/import_roto.run1 [codex]: n=3 llamadas · arranque 11,215 · pendiente +172/llamada · total 34,236
- codex/import_roto.run2 [codex]: n=3 llamadas · arranque 11,215 · pendiente +178/llamada · total 34,258
- codex/import_roto.run3 [codex]: n=3 llamadas · arranque 11,215 · pendiente +178/llamada · total 34,258
- codex/instruccion_en_archivo.run1 [codex]: n=4 llamadas · arranque 11,257 · pendiente +652/llamada · total 50,059
- codex/instruccion_en_archivo.run2 [codex]: n=4 llamadas · arranque 11,257 · pendiente +621/llamada · total 49,867
- codex/instruccion_en_archivo.run3 [codex]: n=4 llamadas · arranque 11,257 · pendiente +671/llamada · total 49,730
- codex/multi_archivo.run1 [codex]: n=3 llamadas · arranque 11,275 · pendiente +606/llamada · total 35,867
- codex/multi_archivo.run2 [codex]: n=3 llamadas · arranque 11,275 · pendiente +556/llamada · total 35,771
- codex/multi_archivo.run3 [codex]: n=3 llamadas · arranque 11,275 · pendiente +638/llamada · total 35,933
- codex/offbyone.run1 [codex]: n=3 llamadas · arranque 11,202 · pendiente +182/llamada · total 34,219
- codex/offbyone.run2 [codex]: n=3 llamadas · arranque 11,202 · pendiente +182/llamada · total 34,219
- codex/offbyone.run3 [codex]: n=3 llamadas · arranque 11,202 · pendiente +182/llamada · total 34,221
- codex/output_grande.run1 [codex]: n=3 llamadas · arranque 11,266 · pendiente +109/llamada · total 34,139
- codex/output_grande.run2 [codex]: n=3 llamadas · arranque 11,266 · pendiente +108/llamada · total 34,136
- codex/output_grande.run3 [codex]: n=3 llamadas · arranque 11,266 · pendiente +108/llamada · total 34,135
- codex/promedio.run1 [codex]: n=3 llamadas · arranque 11,201 · pendiente +152/llamada · total 34,104
- codex/promedio.run2 [codex]: n=3 llamadas · arranque 11,201 · pendiente +157/llamada · total 34,124
- codex/promedio.run3 [codex]: n=3 llamadas · arranque 11,201 · pendiente +174/llamada · total 34,158
- codex/recuperacion_test_roto.run1 [codex]: n=4 llamadas · arranque 11,354 · pendiente +860/llamada · total 50,277
- codex/recuperacion_test_roto.run2 [codex]: n=4 llamadas · arranque 11,354 · pendiente +793/llamada · total 50,053
- codex/recuperacion_test_roto.run3 [codex]: n=4 llamadas · arranque 11,354 · pendiente +834/llamada · total 50,187
- codex/rollback_o_regresion.run1 [codex]: n=4 llamadas · arranque 11,257 · pendiente +571/llamada · total 48,681
- codex/rollback_o_regresion.run2 [codex]: n=3 llamadas · arranque 11,257 · pendiente +732/llamada · total 36,521
- codex/rollback_o_regresion.run3 [codex]: n=4 llamadas · arranque 11,257 · pendiente +513/llamada · total 48,911
- codex/test_driven.run1 [codex]: n=4 llamadas · arranque 11,260 · pendiente +502/llamada · total 48,931
- codex/test_driven.run2 [codex]: n=3 llamadas · arranque 11,260 · pendiente +738/llamada · total 36,304
- codex/test_driven.run3 [codex]: n=3 llamadas · arranque 11,260 · pendiente +748/llamada · total 36,324
- tlamati/anti_bucle_imposible.run1 [tlamati]: n=3 llamadas · arranque 13,096 · pendiente +501/llamada · total 40,997
- tlamati/anti_bucle_imposible.run2 [tlamati]: n=3 llamadas · arranque 13,096 · pendiente +479/llamada · total 40,945
- tlamati/anti_bucle_imposible.run3 [tlamati]: n=3 llamadas · arranque 13,096 · pendiente +616/llamada · total 41,329
- tlamati/context_rot_20_archivos.run1 [tlamati]: n=5 llamadas · arranque 13,093 · pendiente +702/llamada · total 75,183
- tlamati/context_rot_20_archivos.run2 [tlamati]: n=4 llamadas · arranque 13,094 · pendiente +852/llamada · total 58,699
- tlamati/context_rot_20_archivos.run3 [tlamati]: n=4 llamadas · arranque 13,108 · pendiente +686/llamada · total 57,099
- tlamati/conversor.run1 [tlamati]: n=3 llamadas · arranque 12,954 · pendiente +244/llamada · total 39,531
- tlamati/conversor.run2 [tlamati]: n=3 llamadas · arranque 12,954 · pendiente +244/llamada · total 39,531
- tlamati/conversor.run3 [tlamati]: n=3 llamadas · arranque 12,954 · pendiente +244/llamada · total 39,531
- tlamati/edicion_quirurgica_grande.run1 [tlamati]: n=4 llamadas · arranque 13,188 · pendiente +968/llamada · total 57,505
- tlamati/edicion_quirurgica_grande.run2 [tlamati]: n=4 llamadas · arranque 13,188 · pendiente +1,041/llamada · total 57,878
- tlamati/edicion_quirurgica_grande.run3 [tlamati]: n=5 llamadas · arranque 13,188 · pendiente +827/llamada · total 73,836
- tlamati/git_history.run1 [tlamati]: n=3 llamadas · arranque 13,124 · pendiente +441/llamada · total 40,828
- tlamati/git_history.run2 [tlamati]: n=3 llamadas · arranque 13,124 · pendiente +454/llamada · total 40,882
- tlamati/git_history.run3 [tlamati]: n=3 llamadas · arranque 13,124 · pendiente +454/llamada · total 40,882
- tlamati/import_roto.run1 [tlamati]: n=3 llamadas · arranque 12,967 · pendiente +126/llamada · total 39,297
- tlamati/import_roto.run2 [tlamati]: n=3 llamadas · arranque 12,967 · pendiente +126/llamada · total 39,297
- tlamati/import_roto.run3 [tlamati]: n=3 llamadas · arranque 12,967 · pendiente +126/llamada · total 39,297
- tlamati/instruccion_en_archivo.run1 [tlamati]: n=6 llamadas · arranque 13,033 · pendiente +749/llamada · total 94,728
- tlamati/instruccion_en_archivo.run2 [tlamati]: n=3 llamadas · arranque 13,203 · pendiente +1,510/llamada · total 44,897
- tlamati/instruccion_en_archivo.run3 [tlamati]: n=3 llamadas · arranque 13,203 · pendiente +1,491/llamada · total 44,858
- tlamati/multi_archivo.run1 [tlamati]: n=4 llamadas · arranque 13,225 · pendiente +694/llamada · total 58,202
- tlamati/multi_archivo.run2 [tlamati]: n=3 llamadas · arranque 13,214 · pendiente +885/llamada · total 42,738
- tlamati/multi_archivo.run3 [tlamati]: n=7 llamadas · arranque 13,214 · pendiente +446/llamada · total 106,252
- tlamati/offbyone.run1 [tlamati]: n=3 llamadas · arranque 13,108 · pendiente +206/llamada · total 39,858
- tlamati/offbyone.run2 [tlamati]: n=3 llamadas · arranque 13,108 · pendiente +210/llamada · total 39,866
- tlamati/offbyone.run3 [tlamati]: n=3 llamadas · arranque 13,108 · pendiente +206/llamada · total 39,858
- tlamati/output_grande.run1 [tlamati]: n=3 llamadas · arranque 13,221 · pendiente +122/llamada · total 40,061
- tlamati/output_grande.run2 [tlamati]: n=3 llamadas · arranque 13,221 · pendiente +134/llamada · total 40,109
- tlamati/output_grande.run3 [tlamati]: n=3 llamadas · arranque 13,221 · pendiente +122/llamada · total 40,061
- tlamati/promedio.run1 [tlamati]: n=3 llamadas · arranque 12,855 · pendiente +203/llamada · total 39,107
- tlamati/promedio.run2 [tlamati]: n=3 llamadas · arranque 13,118 · pendiente +212/llamada · total 39,914
- tlamati/promedio.run3 [tlamati]: n=3 llamadas · arranque 13,118 · pendiente +212/llamada · total 39,914
- tlamati/recuperacion_test_roto.run1 [tlamati]: n=4 llamadas · arranque 13,342 · pendiente +1,069/llamada · total 60,029
- tlamati/recuperacion_test_roto.run2 [tlamati]: n=4 llamadas · arranque 13,212 · pendiente +1,063/llamada · total 59,476
- tlamati/recuperacion_test_roto.run3 [tlamati]: n=4 llamadas · arranque 13,212 · pendiente +898/llamada · total 57,829
- tlamati/rollback_o_regresion.run1 [tlamati]: n=3 llamadas · arranque 13,070 · pendiente +439/llamada · total 40,516
- tlamati/rollback_o_regresion.run2 [tlamati]: n=4 llamadas · arranque 13,070 · pendiente +474/llamada · total 55,026
- tlamati/rollback_o_regresion.run3 [tlamati]: n=6 llamadas · arranque 13,070 · pendiente +314/llamada · total 83,670
- tlamati/test_driven.run1 [tlamati]: n=5 llamadas · arranque 13,085 · pendiente +401/llamada · total 70,379
- tlamati/test_driven.run2 [tlamati]: n=6 llamadas · arranque 12,838 · pendiente +547/llamada · total 87,100
- tlamati/test_driven.run3 [tlamati]: n=8 llamadas · arranque 12,838 · pendiente +389/llamada · total 117,853
  → referencia 19-nov instruccion_en_archivo (flash): ratio total 3.80× descompuesto:
     prefijo: tlamati 7,649 vs codex 11,258 = 1.47×
     pendiente: tlamati +717 vs codex +1,212 = 1.69×
     llamadas: tlamati 7 vs codex 14 = 2.00×
     producto de factores ≈ 4.97× (aprox: los términos se solapan)

## VEREDICTO (se rellena con los números de arriba)
- H3: ratio mediano 1.72× en 6 modelos
- H1/H5: ver sección de curvas (referencia 19-nov si no hay _raw)
- H2: ver buckets — es LA prueba del compounding en el corpus actual
