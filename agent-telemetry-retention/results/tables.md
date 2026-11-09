Prices: AWS us-east-1 list, verified 2026-06-10, re-verified 2026-06-14 (cost-to-serve-retention/cost_model.py): ebs_gp3 $0.08/GB-mo, s3_standard $0.023/GB-mo, s3_glacier_ir $0.004/GB-mo
Pricing frame: 1,000 users, 185 active days in a 365-day retention window; steady-state $/month at 365-day retention (cost_model method), annual run rate = 12x, year-1 accrual from empty = 6.5x monthly.


### coding tier, real text, zstd default (level 1), Parquet

| Arm | Order | bytes / M tokens (median, min-max, CV) | text share | raw JSONL bytes / M tokens | GB / yr per 1k users (avg vol) | S3 Std $/mo | Glacier IR $/mo | gp3 $/mo |
|---|---|---|---|---|---|---|---|---|
| T0_metadata | session_sorted | 1,067 (1,061-1,236, 7.2%) | 0.0% | 23,901 | 4.6 | $0.11 | $0.02 | $0.37 |
| T0_metadata | random | 1,151 (1,132-1,334, 7.6%) | 0.0% | 23,901 | 5.0 | $0.12 | $0.02 | $0.40 |
| T1_hash | session_sorted | 2,563 (2,499-2,968, 7.8%) | 61.3% | 27,640 | 11.1 | $0.26 | $0.04 | $0.89 |
| T1_hash | random | 2,655 (2,555-3,090, 8.4%) | 59.4% | 27,640 | 11.5 | $0.27 | $0.05 | $0.92 |
| T2_delta | session_sorted | 25,922 (24,404-33,044, 13.6%) | 96.4% | 138,376 | 112.7 | $2.59 | $0.45 | $9.02 |
| T2_delta | random | 32,476 (30,024-41,312, 14.0%) | 96.8% | 138,376 | 141.2 | $3.25 | $0.56 | $11.30 |
| T3_full | session_sorted | 195,906 (162,990-217,288, 11.6%) | 99.5% | 4,253,613 | 851.7 | $19.59 | $3.41 | $68.14 |
| T3_full | random | 785,203 (764,650-857,459, 5.0%) | 99.9% | 4,253,613 | 3,413.7 | $78.51 | $13.65 | $273.09 |

### chat tier, real text, zstd default (level 1), Parquet

| Arm | Order | bytes / M tokens (median, min-max, CV) | text share | raw JSONL bytes / M tokens | GB / yr per 1k users (avg vol) | S3 Std $/mo | Glacier IR $/mo | gp3 $/mo |
|---|---|---|---|---|---|---|---|---|
| T0_metadata | session_sorted | 9,376 (9,372-10,267, 4.4%) | 0.0% | 251,202 | 0.3 | $0.01 | $0.00 | $0.03 |
| T0_metadata | random | 10,504 (10,467-11,477, 4.3%) | 0.0% | 251,202 | 0.4 | $0.01 | $0.00 | $0.03 |
| T1_hash | session_sorted | 25,447 (25,373-27,689, 4.1%) | 63.8% | 292,105 | 0.9 | $0.02 | $0.00 | $0.08 |
| T1_hash | random | 26,486 (26,383-29,115, 4.6%) | 61.1% | 292,105 | 1.0 | $0.02 | $0.00 | $0.08 |
| T2_delta | session_sorted | 204,199 (201,952-218,811, 3.6%) | 95.5% | 826,265 | 7.6 | $0.17 | $0.03 | $0.60 |
| T2_delta | random | 205,975 (203,622-220,091, 3.5%) | 95.0% | 826,265 | 7.6 | $0.18 | $0.03 | $0.61 |
| T3_full | session_sorted | 363,349 (360,259-386,690, 3.2%) | 97.5% | 4,379,971 | 13.4 | $0.31 | $0.05 | $1.08 |
| T3_full | random | 1,327,012 (1,320,070-1,329,835, 0.3%) | 99.2% | 4,379,971 | 49.1 | $1.13 | $0.20 | $3.93 |

### coding tier, high_entropy text, zstd default (level 1), Parquet

| Arm | Order | bytes / M tokens (median, min-max, CV) | text share | raw JSONL bytes / M tokens | GB / yr per 1k users (avg vol) | S3 Std $/mo | Glacier IR $/mo | gp3 $/mo |
|---|---|---|---|---|---|---|---|---|
| T0_metadata | session_sorted | 419 (390-578, 17.8%) | 0.0% | 7,126 | 1.8 | $0.04 | $0.01 | $0.15 |
| T0_metadata | random | 442 (407-605, 17.8%) | 0.0% | 7,126 | 1.9 | $0.04 | $0.01 | $0.15 |
| T1_hash | session_sorted | 885 (809-1,204, 17.7%) | 58.7% | 8,229 | 3.8 | $0.09 | $0.02 | $0.31 |
| T1_hash | random | 914 (832-1,248, 18.0%) | 57.6% | 8,229 | 4.0 | $0.09 | $0.02 | $0.32 |
| T2_delta | session_sorted | 20,671 (18,481-30,406, 22.4%) | 98.5% | 65,201 | 89.9 | $2.07 | $0.36 | $7.19 |
| T2_delta | random | 20,695 (18,499-30,450, 22.4%) | 98.3% | 65,201 | 90.0 | $2.07 | $0.36 | $7.20 |
| T3_full | session_sorted | 383,151 (206,379-443,586, 29.2%) | 99.9% | 2,222,775 | 1,665.7 | $38.31 | $6.66 | $133.26 |
| T3_full | random | 652,731 (619,508-672,797, 3.4%) | 99.9% | 2,222,775 | 2,837.7 | $65.27 | $11.35 | $227.02 |

### chat tier, high_entropy text, zstd default (level 1), Parquet

| Arm | Order | bytes / M tokens (median, min-max, CV) | text share | raw JSONL bytes / M tokens | GB / yr per 1k users (avg vol) | S3 Std $/mo | Glacier IR $/mo | gp3 $/mo |
|---|---|---|---|---|---|---|---|---|
| T0_metadata | session_sorted | 3,800 (3,576-3,831, 3.0%) | 0.0% | 92,587 | 0.1 | $0.00 | $0.00 | $0.01 |
| T0_metadata | random | 4,176 (3,926-4,195, 3.0%) | 0.0% | 92,587 | 0.2 | $0.00 | $0.00 | $0.01 |
| T1_hash | session_sorted | 10,001 (9,478-10,072, 2.7%) | 63.4% | 107,637 | 0.4 | $0.01 | $0.00 | $0.03 |
| T1_hash | random | 10,375 (9,817-10,418, 2.7%) | 61.1% | 107,637 | 0.4 | $0.01 | $0.00 | $0.03 |
| T2_delta | session_sorted | 111,367 (106,334-111,967, 2.3%) | 96.8% | 401,932 | 4.1 | $0.09 | $0.02 | $0.33 |
| T2_delta | random | 111,756 (106,657-112,436, 2.3%) | 96.5% | 401,932 | 4.1 | $0.10 | $0.02 | $0.33 |
| T3_full | session_sorted | 198,587 (192,119-200,304, 1.8%) | 98.2% | 2,311,269 | 7.3 | $0.17 | $0.03 | $0.59 |
| T3_full | random | 714,535 (713,950-725,949, 0.8%) | 99.4% | 2,311,269 | 26.4 | $0.61 | $0.11 | $2.12 |

### Codec / dictionary variants (median bytes per M tokens over seeds; real text)

| Tier | Arm | Order | snappy_default | zstd_default | zstd_1 | zstd_3 | zstd_9 | zstd_19 | zstd_default_nodict_text | zstd_default_page8m |
|---|---|---|---|---|---|---|---|---|---|---|
| coding | T0_metadata | session_sorted | 1,637 | 1,067 | 1,067 | 1,090 | 1,094 | 1,053 | 1,067 | - |
| coding | T0_metadata | random | 1,679 | 1,151 | 1,151 | 1,173 | 1,181 | 1,110 | 1,151 | - |
| coding | T1_hash | session_sorted | 4,476 | 2,563 | 2,563 | 2,623 | 2,728 | 2,518 | 2,563 | - |
| coding | T1_hash | random | 4,531 | 2,655 | 2,655 | 2,705 | 2,814 | 2,575 | 2,655 | - |
| coding | T2_delta | session_sorted | 44,766 | 25,922 | 25,922 | 20,614 | 18,475 | 16,991 | 26,629 | - |
| coding | T2_delta | random | 49,447 | 32,476 | 32,476 | 22,749 | 20,022 | 18,372 | 34,779 | - |
| coding | T3_full | session_sorted | 1,695,381 | 195,906 | 195,906 | 42,350 | 33,690 | 27,793 | 193,739 | 195,906 |
| coding | T3_full | random | 1,739,571 | 785,203 | 785,203 | 409,469 | 227,212 | 97,964 | 785,870 | - |
| chat | T0_metadata | session_sorted | 14,343 | 9,376 | 9,376 | 9,710 | 9,552 | 8,919 | 9,376 | - |
| chat | T0_metadata | random | 15,454 | 10,504 | 10,504 | 10,938 | 10,877 | 10,288 | 10,504 | - |
| chat | T1_hash | session_sorted | 44,591 | 25,447 | 25,447 | 26,048 | 26,024 | 24,313 | 25,447 | - |
| chat | T1_hash | random | 45,390 | 26,486 | 26,486 | 27,280 | 27,346 | 25,692 | 26,486 | - |
| chat | T2_delta | session_sorted | 297,587 | 204,199 | 204,199 | 149,139 | 133,990 | 122,925 | 204,746 | - |
| chat | T2_delta | random | 299,323 | 205,975 | 205,975 | 152,148 | 136,882 | 125,715 | 206,635 | - |
| chat | T3_full | session_sorted | 1,198,600 | 363,349 | 363,349 | 285,273 | 244,167 | 210,633 | 363,879 | 361,638 |
| chat | T3_full | random | 2,088,061 | 1,327,012 | 1,327,012 | 714,583 | 471,506 | 329,145 | 1,327,421 | - |

### Coding tier one-year bill, 1,000 users, real text (S3 Standard steady state at 365 d; run rate 12x)

| Arm | Order | Variant | Volume | GB held | S3 Std $/mo | S3 Std $/yr run rate | Glacier IR $/mo | year-1 accrual S3 $ |
|---|---|---|---|---|---|---|---|---|
| T0_metadata | session_sorted | zstd_default | avg | 5 | $0 | $1 | $0 | $1 |
| T0_metadata | session_sorted | zstd_default | p90 | 11 | $0 | $3 | $0 | $2 |
| T0_metadata | session_sorted | zstd_19 | avg | 5 | $0 | $1 | $0 | $1 |
| T0_metadata | session_sorted | zstd_19 | p90 | 11 | $0 | $3 | $0 | $2 |
| T0_metadata | random | zstd_default | avg | 5 | $0 | $1 | $0 | $1 |
| T0_metadata | random | zstd_default | p90 | 11 | $0 | $3 | $0 | $2 |
| T0_metadata | random | zstd_19 | avg | 5 | $0 | $1 | $0 | $1 |
| T0_metadata | random | zstd_19 | p90 | 11 | $0 | $3 | $0 | $2 |
| T1_hash | session_sorted | zstd_default | avg | 11 | $0 | $3 | $0 | $2 |
| T1_hash | session_sorted | zstd_default | p90 | 26 | $1 | $7 | $0 | $4 |
| T1_hash | session_sorted | zstd_19 | avg | 11 | $0 | $3 | $0 | $2 |
| T1_hash | session_sorted | zstd_19 | p90 | 25 | $1 | $7 | $0 | $4 |
| T1_hash | random | zstd_default | avg | 12 | $0 | $3 | $0 | $2 |
| T1_hash | random | zstd_default | p90 | 27 | $1 | $7 | $0 | $4 |
| T1_hash | random | zstd_19 | avg | 11 | $0 | $3 | $0 | $2 |
| T1_hash | random | zstd_19 | p90 | 26 | $1 | $7 | $0 | $4 |
| T2_delta | session_sorted | zstd_default | avg | 113 | $3 | $31 | $0 | $17 |
| T2_delta | session_sorted | zstd_default | p90 | 259 | $6 | $71 | $1 | $39 |
| T2_delta | session_sorted | zstd_19 | avg | 74 | $2 | $20 | $0 | $11 |
| T2_delta | session_sorted | zstd_19 | p90 | 170 | $4 | $47 | $1 | $25 |
| T2_delta | random | zstd_default | avg | 141 | $3 | $39 | $1 | $21 |
| T2_delta | random | zstd_default | p90 | 324 | $7 | $90 | $1 | $49 |
| T2_delta | random | zstd_19 | avg | 80 | $2 | $22 | $0 | $12 |
| T2_delta | random | zstd_19 | p90 | 184 | $4 | $51 | $1 | $27 |
| T3_full | session_sorted | zstd_default | avg | 852 | $20 | $235 | $3 | $127 |
| T3_full | session_sorted | zstd_default | p90 | 1,957 | $45 | $540 | $8 | $293 |
| T3_full | session_sorted | zstd_19 | avg | 121 | $3 | $33 | $0 | $18 |
| T3_full | session_sorted | zstd_19 | p90 | 278 | $6 | $77 | $1 | $42 |
| T3_full | random | zstd_default | avg | 3,414 | $79 | $942 | $14 | $510 |
| T3_full | random | zstd_default | p90 | 7,844 | $180 | $2,165 | $31 | $1,173 |
| T3_full | random | zstd_19 | avg | 426 | $10 | $118 | $2 | $64 |
| T3_full | random | zstd_19 | p90 | 979 | $23 | $270 | $4 | $146 |

### Iceberg (pyiceberg 0.12.0) vs plain Parquet zstd default, session-sorted, median over seeds

| Tier | Corpus | Arm | plain Parquet | Iceberg default (data) | Iceberg parity (data) | Iceberg parity (data+metadata) | EXPLORATORY plain, write_batch_size 20000 | parity vs plain |
|---|---|---|---|---|---|---|---|---|
| coding | real | T0_metadata | 1,067 | 1,110 | 1,110 | 1,419 | 1,067 | +4.0% |
| coding | real | T1_hash | 2,563 | 2,609 | 2,609 | 2,899 | 2,563 | +1.8% |
| coding | real | T2_delta | 25,922 | 25,185 | 25,968 | 26,258 | 25,139 | +0.2% |
| coding | real | T3_full | 195,906 | 189,118 | 195,951 | 196,241 | 189,072 | +0.0% |
| coding | high_entropy | T0_metadata | 419 | 453 | 453 | 671 | 419 | +7.9% |
| coding | high_entropy | T1_hash | 885 | 920 | 920 | 1,145 | 885 | +4.0% |
| coding | high_entropy | T2_delta | 20,671 | 20,707 | 20,707 | 20,931 | 20,671 | +0.2% |
| coding | high_entropy | T3_full | 383,151 | 383,186 | 383,186 | 383,411 | 383,151 | +0.0% |
| chat | real | T0_metadata | 9,376 | 9,475 | 9,475 | 10,121 | 9,376 | +1.1% |
| chat | real | T1_hash | 25,447 | 25,550 | 25,550 | 26,201 | 25,447 | +0.4% |
| chat | real | T2_delta | 204,199 | 192,449 | 204,301 | 204,953 | 192,347 | +0.1% |
| chat | real | T3_full | 363,349 | 350,406 | 363,451 | 364,101 | 350,304 | +0.0% |
| chat | high_entropy | T0_metadata | 3,800 | 3,878 | 3,878 | 4,388 | 3,800 | +2.1% |
| chat | high_entropy | T1_hash | 10,001 | 10,083 | 10,083 | 10,609 | 10,001 | +0.8% |
| chat | high_entropy | T2_delta | 111,367 | 111,204 | 111,450 | 111,974 | 111,122 | +0.1% |
| chat | high_entropy | T3_full | 198,587 | 198,341 | 198,669 | 199,193 | 198,259 | +0.0% |

### Trained zstd dictionary, per-record prompt_text at level 3 (held-out seed 99 training), vs Parquet column

| Tier | Corpus | Column | per-record zstd-3 bytes/M tok | + trained dict | dict gain | Parquet zstd default prompt_text column bytes/M tok (sorted / random) |
|---|---|---|---|---|---|---|
| chat | high_entropy | prompt_text_delta | 27,469 | 18,818 | 1.46x (1.46-1.46) | 18,251 / 18,272 |
| chat | high_entropy | prompt_text_full | 733,334 | 652,335 | 1.12x (1.12-1.12) | 105,788 / 621,329 |
| chat | real | prompt_text_delta | 59,250 | 38,234 | 1.55x (1.54-1.56) | 40,659 / 40,885 |
| chat | real | prompt_text_full | 1,433,926 | 1,080,636 | 1.32x (1.32-1.34) | 199,830 / 1,156,129 |
| coding | high_entropy | prompt_text_delta | 16,699 | 13,810 | 1.21x (1.20-1.21) | 14,404 / 14,400 |
| coding | high_entropy | prompt_text_full | 727,229 | 712,144 | 1.02x (1.02-1.03) | 376,929 / 646,481 |
| coding | real | prompt_text_delta | 28,315 | 23,028 | 1.23x (1.19-1.26) | 13,815 / 19,301 |
| coding | real | prompt_text_full | 840,249 | 767,782 | 1.10x (1.09-1.11) | 183,881 / 773,419 |
