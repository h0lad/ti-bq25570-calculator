## What is this thing?

This is a Python script for calculating all resistor values needed for the the TI BQ25570 energy harvester.

Meaning:
 - ROK1, ROK2, ROK3
 - ROUT1, ROUT2
 - ROV1, ROV2

As tolerances are highly critical in the design it calculates the voltage ranges based on 1% and 10% precision resistors and VBIAS tolerance. Per default it uses the E24 resistor series but it can be switched to E96.

Feel free to make pull requests.

## Commandline

```
# python3 src/bq25570_calc.py 
usage: bq25570_calc [-h] [--vout [VOUT ...]] [--vbat-ov VBAT_OV] [--never-exceed-ov] [--vbat-ok-prog VBAT_OK_PROG] [--vbat-ok-hyst VBAT_OK_HYST] [--vbat-uv VBAT_UV] [--series {E24,E96}]
                    [--decades MIN MAX] [--rsum-max RSUM_MAX] [--limit LIMIT] [--tolerance TOLERANCE]

Resistor divider optimizer for TI bq25570: VOUT, VBAT_OV, VBAT_OK.

options:
  -h, --help            show this help message and exit
  --vout [VOUT ...]     Target VOUT values (V).
  --vbat-ov VBAT_OV     Target VBAT_OV (V).
  --never-exceed-ov     Ensure 1% worst-case never exceeds VBAT_OV.
  --vbat-ok-prog VBAT_OK_PROG
                        VBAT_OK falling threshold (V).
  --vbat-ok-hyst VBAT_OK_HYST
                        VBAT_OK rising threshold (V).
  --vbat-uv VBAT_UV     Internal UV reference (V).
  --series {E24,E96}    Resistor series.
  --decades MIN MAX     Decade range, e.g., 6 7 for ~1–10 MΩ.
  --rsum-max RSUM_MAX   Max total resistance (Ω).
  --limit LIMIT         Limit number of candidates.
  --tolerance TOLERANCE
                        Resistor tolerance for worst-case calculations (default 0.01 = 1%).

Examples:

  # Common rails
  bq25570_calc --vout 3.3

  # LiPo 1-cell (VBAT_OV = 4.2V)
  bq25570_calc --vbat-ov 4.2 --never-exceed-ov

  # Battery-Good window
  bq25570_calc --vbat-ok-prog 3.5 --vbat-ok-hyst 3.7
```

## Example: 1-Cell LiPo setup with 3.3V output

```
# python3 src/bq25570_calc.py --vout 3.3 --vbat-ov 4.2 --never-exceed-ov --vbat-ok-prog 3.0 --vbat-ok-hyst 3.6

# VOUT = 3.300V
# R1(bottom), R2(top), RSUM, V(nom), 1%[min..max], 10%[min..max]
3.60MΩ  6.20MΩ  9.80MΩ  3.294 V  1% [3.239..3.355]  10% [2.903..3.779]
2.70MΩ  4.70MΩ  7.40MΩ  3.316 V  1% [3.261..3.378]  10% [2.921..3.806]
3.90MΩ  6.80MΩ  10.70MΩ  3.320 V  1% [3.264..3.382]  10% [2.924..3.810]
4.30MΩ  7.50MΩ  11.80MΩ  3.320 V  1% [3.265..3.383]  10% [2.925..3.811]

# VBAT_OV = 4.200V (NEVER-EXCEED@1%)
# R1(bottom), R2(top), RSUM, V(nom), 1%[min..max], 10%[min..max]
1.20MΩ  1.50MΩ  2.70MΩ  4.084 V  1% [4.022..4.153]  10% [3.656..4.614]
1.60MΩ  2.00MΩ  3.60MΩ  4.084 V  1% [4.022..4.153]  10% [3.656..4.614]
2.40MΩ  3.00MΩ  5.40MΩ  4.084 V  1% [4.022..4.153]  10% [3.656..4.614]
1.30MΩ  1.60MΩ  2.90MΩ  4.049 V  1% [3.988..4.118]  10% [3.628..4.572]

# VBAT_OK PROG=3.000V HYST=3.600V
# R_OK1(bottom), R_OK2(mid), R_OK3(top), RSUM, VBAT_OK_PROG(nom)[1%/10%], VBAT_OK_HYST(nom)[1%/10%]
2.40MΩ  3.60MΩ  1.10MΩ  7.10MΩ  VBAT_OK_PROG=3.025V [1% 2.977..3.079; 10% 2.684..3.448]  VBAT_OK_HYST=3.580V [1% 3.518..3.648; 10% 3.136..4.130]
2.20MΩ  3.30MΩ  1.00MΩ  6.50MΩ  VBAT_OK_PROG=3.025V [1% 2.977..3.079; 10% 2.684..3.448]  VBAT_OK_HYST=3.575V [1% 3.514..3.644; 10% 3.132..4.124]
2.00MΩ  3.00MΩ  1.00MΩ  6.00MΩ  VBAT_OK_PROG=3.025V [1% 2.977..3.079; 10% 2.684..3.448]  VBAT_OK_HYST=3.630V [1% 3.567..3.700; 10% 3.177..4.192]
2.20MΩ  3.30MΩ  1.10MΩ  6.60MΩ  VBAT_OK_PROG=3.025V [1% 2.977..3.079; 10% 2.684..3.448]  VBAT_OK_HYST=3.630V [1% 3.567..3.700; 10% 3.177..4.192]
```
