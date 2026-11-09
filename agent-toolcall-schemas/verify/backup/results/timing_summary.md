
### 100,000 calls

| query | layout | pooled median ms | CV % | min–max ms | per-pass medians | ratio vs L1 | answers equal |
|---|---|---|---|---|---|---|---|
| Q1_tool_by_agent | L1_typed | 3.64 | 50.7 | 3.19–13.24 | 3.443, 3.871, 3.64 | 1.0x (floor 0.24x) | True |
| Q1_tool_by_agent | L2_otel_map | 94.91 | 16.2 | 79.49–142.91 | 100.972, 86.086, 107.785 | 26.1x (floor 6.0x) | True |
| Q1_tool_by_agent | L3_aos_unmapped | 22.37 | 45.1 | 20.68–58.06 | 21.197, 23.027, 22.626 | 6.1x (floor 1.56x) | True |
| Q2_argument_hunt | L1_typed | 14.43 | 16.7 | 12.95–21.01 | 13.795, 15.963, 14.199 | 1.0x (floor 0.62x) | True |
| Q2_argument_hunt | L2_otel_map | 105.19 | 17.7 | 85.2–155.84 | 117.227, 105.193, 98.269 | 7.3x (floor 4.06x) | True |
| Q2_argument_hunt | L3_aos_unmapped | 80.43 | 29.0 | 48.9–133.89 | 86.753, 82.369, 51.075 | 5.6x (floor 2.33x) | True |
| Q3_tool_breadth_errors | L1_typed | 5.1 | 73.6 | 4.69–25.55 | 5.085, 7.384, 4.913 | 1.0x (floor 0.18x) | True |
| Q3_tool_breadth_errors | L2_otel_map | 116.74 | 17.7 | 89.83–158.15 | 124.456, 110.558, 116.742 | 22.9x (floor 3.52x) | True |
| Q3_tool_breadth_errors | L3_aos_unmapped | 57.4 | 43.9 | 24.93–95.35 | 64.4, 57.395, 38.322 | 11.3x (floor 0.98x) | True |
| Q4_failure_bursts | L1_typed | 3.36 | 123.9 | 2.68–37.63 | 3.21, 3.386, 3.182 | 1.0x (floor 0.07x) | True |
| Q4_failure_bursts | L2_otel_map | 103.77 | 21.4 | 77.43–166.82 | 101.409, 107.122, 93.581 | 30.9x (floor 2.06x) | True |
| Q4_failure_bursts | L3_aos_unmapped | 54.71 | 40.7 | 22.89–76.54 | 23.641, 57.991, 55.466 | 16.3x (floor 0.61x) | True |
| Q5_off_allowlist | L1_typed | 4.29 | 4.9 | 3.9–4.8 | 4.069, 4.277, 4.368 | 1.0x (floor 0.81x) | True |
| Q5_off_allowlist | L2_otel_map | 104.02 | 16.9 | 87.28–158.75 | 91.797, 117.048, 103.137 | 24.2x (floor 18.18x) | True |
| Q5_off_allowlist | L3_aos_unmapped | 88.53 | 29.3 | 48.88–155.11 | 84.874, 94.929, 92.571 | 20.6x (floor 10.18x) | True |

On disk (ZSTD, row group 122880): L1_typed 2.7 MB, L2_otel_map 5.8 MB, L3_aos_unmapped 3.1 MB; L3/L1 = 1.13x, L2/L1 = 2.12x. Write seconds: L1_typed 0.252, L2_otel_map 1.485, L3_aos_unmapped 0.391.

### 1,000,000 calls

| query | layout | pooled median ms | CV % | min–max ms | per-pass medians | ratio vs L1 | answers equal |
|---|---|---|---|---|---|---|---|
| Q1_tool_by_agent | L1_typed | 7.29 | 54.1 | 6.03–24.95 | 6.198, 7.818, 15.359 | 1.0x (floor 0.24x) | True |
| Q1_tool_by_agent | L2_otel_map | 235.48 | 7.8 | 209.86–267.77 | 231.448, 244.78, 222.234 | 32.3x (floor 8.41x) | True |
| Q1_tool_by_agent | L3_aos_unmapped | 61.32 | 20.7 | 54.94–102.3 | 61.32, 62.848, 57.324 | 8.4x (floor 2.2x) | True |
| Q2_argument_hunt | L1_typed | 36.05 | 14.3 | 33.41–52.06 | 34.661, 38.592, 34.447 | 1.0x (floor 0.64x) | True |
| Q2_argument_hunt | L2_otel_map | 265.33 | 17.7 | 239.07–465.25 | 277.918, 265.33, 248.576 | 7.4x (floor 4.59x) | True |
| Q2_argument_hunt | L3_aos_unmapped | 190.87 | 5.3 | 179.07–219.98 | 194.951, 185.182, 185.93 | 5.3x (floor 3.44x) | True |
| Q3_tool_breadth_errors | L1_typed | 24.48 | 72.4 | 7.08–74.62 | 7.494, 16.805, 29.935 | 1.0x (floor 0.09x) | True |
| Q3_tool_breadth_errors | L2_otel_map | 260.16 | 9.7 | 216.78–314.32 | 257.937, 262.086, 260.742 | 10.6x (floor 2.91x) | True |
| Q3_tool_breadth_errors | L3_aos_unmapped | 131.42 | 15.6 | 88.66–167.55 | 137.656, 120.648, 144.268 | 5.4x (floor 1.19x) | True |
| Q4_failure_bursts | L1_typed | 20.99 | 64.5 | 5.51–37.95 | 9.397, 25.638, 20.992 | 1.0x (floor 0.15x) | True |
| Q4_failure_bursts | L2_otel_map | 225.24 | 8.5 | 195.59–267.6 | 216.36, 238.073, 240.995 | 10.7x (floor 5.15x) | True |
| Q4_failure_bursts | L3_aos_unmapped | 98.75 | 21.9 | 61.54–137.22 | 98.754, 127.263, 90.95 | 4.7x (floor 1.62x) | True |
| Q5_off_allowlist | L1_typed | 8.32 | 59.2 | 7.34–29.34 | 8.15, 10.332, 7.804 | 1.0x (floor 0.25x) | True |
| Q5_off_allowlist | L2_otel_map | 269.95 | 8.4 | 238.11–324.14 | 271.164, 250.167, 277.343 | 32.4x (floor 8.12x) | True |
| Q5_off_allowlist | L3_aos_unmapped | 187.14 | 7.0 | 166.15–216.56 | 195.37, 186.317, 176.304 | 22.5x (floor 5.66x) | True |

On disk (ZSTD, row group 122880): L1_typed 27.4 MB, L2_otel_map 58.2 MB, L3_aos_unmapped 30.9 MB; L3/L1 = 1.12x, L2/L1 = 2.12x. Write seconds: L1_typed 0.568, L2_otel_map 3.266, L3_aos_unmapped 1.02.
