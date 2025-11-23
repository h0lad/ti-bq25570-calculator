# -*- coding: utf-8 -*-

import argparse
import sys
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Tuple

# VBIAS nominal and bounds for worst-case corners (datasheet Electrical Characteristics)
VBIAS_TYP = 1.21
VBIAS_MIN = 1.205
VBIAS_MAX = 1.217

# Datasheet guidance for high-impedance VRDIV networks
DEFAULT_RSUM_MAX = 13e6  # ≈ 13 MΩ total per network

E24_BASE = [
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
    3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1
]
E96_BASE = [
    1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30, 1.33, 1.37, 1.40, 1.43,
    1.47, 1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74, 1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10,
    2.15, 2.21, 2.26, 2.32, 2.37, 2.43, 2.49, 2.55, 2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09,
    3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12, 4.22, 4.32, 4.42, 4.53,
    4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49, 5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65,
    6.81, 6.98, 7.15, 7.32, 7.50, 7.68, 7.87, 8.06, 8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76
]

@dataclass
class TwoResCandidate:
    error: float
    v_nom: float
    r1: float
    r2: float
    rsum: float

@dataclass
class ThreeResCandidate:
    error: float
    v_prog: float
    v_hyst: float
    r1: float
    r2: float
    r3: float
    rsum: float

class ESeries:
    def __init__(self, name: str, decade_min: int, decade_max: int) -> None:
        self.name = name.upper()
        self.decade_min = decade_min
        self.decade_max = decade_max

    def values(self) -> List[float]:
        base = E24_BASE if self.name == "E24" else E96_BASE
        vals: List[float] = []
        for d in range(self.decade_min, self.decade_max + 1):
            factor = 10 ** d
            vals.extend(b * factor for b in base)
        return sorted(vals)

class Calculator:
    @staticmethod
    def vout(r1: float, r2: float, vbias: float = VBIAS_TYP) -> float:
        # R1 = bottom, R2 = top
        return vbias * (1.0 + r2 / r1)

    @staticmethod
    def vbat_ov(r1: float, r2: float, vbias: float = VBIAS_TYP) -> float:
        # 3/2 scaling factor per OV comparator
        return 1.5 * vbias * (1.0 + r2 / r1)

    @staticmethod
    def vbat_ok_prog(r1: float, r2: float, vbias: float = VBIAS_TYP) -> float:
        return vbias * (1.0 + r2 / r1)

    @staticmethod
    def vbat_ok_hyst(r1: float, r2: float, r3: float, vbias: float = VBIAS_TYP) -> float:
        return vbias * (1.0 + (r2 + r3) / r1)

class WorstCase:
    @staticmethod
    def two_res_bounds(
        vfunc: Callable[..., float],
        r1: float,
        r2: float,
        tol: float,
        vbounds: Tuple[float, float]
    ) -> Tuple[float, float]:
        r1_min, r1_max = r1 * (1 - tol), r1 * (1 + tol)
        r2_min, r2_max = r2 * (1 - tol), r2 * (1 + tol)
        v_min = vfunc(r1_max, r2_min, vbounds[0])
        v_max = vfunc(r1_min, r2_max, vbounds[1])
        return v_min, v_max

    @staticmethod
    def ok_bounds(
        r1: float,
        r2: float,
        r3: float,
        tol: float,
        vbounds: Tuple[float, float]
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        # PROG bounds
        vp_min = Calculator.vbat_ok_prog(r1 * (1 + tol), r2 * (1 - tol), vbounds[0])
        vp_max = Calculator.vbat_ok_prog(r1 * (1 - tol), r2 * (1 + tol), vbounds[1])
        # HYST bounds
        vh_min = Calculator.vbat_ok_hyst(
            r1 * (1 + tol), r2 * (1 - tol), r3 * (1 - tol), vbounds[0]
        )
        vh_max = Calculator.vbat_ok_hyst(
            r1 * (1 - tol), r2 * (1 + tol), r3 * (1 + tol), vbounds[1]
        )
        return (vp_min, vp_max), (vh_min, vh_max)

class DatasheetLimits:
    def __init__(self, vbat_uv: float, vbat_ov_target: Optional[float]) -> None:
        self.vbat_uv = vbat_uv
        self.vbat_ov_target = vbat_ov_target

    def allow_vout_target(self, v: float) -> bool:
        return 2.0 <= v <= 5.5

    def allow_vbat_ov_target(self, v: float) -> bool:
        return 2.0 <= v <= 5.5

    def ok_relationships(self, v_prog: float, v_hyst: float) -> bool:
        if v_prog < self.vbat_uv:
            return False
        if v_hyst < v_prog:
            return False
        if self.vbat_ov_target is not None and v_hyst > self.vbat_ov_target:
            return False
        return True

class Optimizer:
    def __init__(
        self,
        series: ESeries,
        rsum_max: float,
        limit: int,
        limits: DatasheetLimits,
    ) -> None:
        self.series = series
        self.rsum_max = rsum_max
        self.limit = limit
        self.limits = limits
        self.pool = self.series.values()

    def search_two(
        self,
        target: float,
        vfunc: Callable[..., float],
        never_exceed: Optional[float] = None,
        tol_for_ne: float = 0.01,
        target_checker: Optional[Callable[[float], bool]] = None
    ) -> List[TwoResCandidate]:
        cands: List[TwoResCandidate] = []
        if target_checker and not target_checker(target):
            return []
        for r1 in self.pool:
            for r2 in self.pool:
                s = r1 + r2
                if s > self.rsum_max:
                    continue
                v = vfunc(r1, r2)
                if never_exceed is not None:
                    vmin, vmax = WorstCase.two_res_bounds(
                        vfunc, r1, r2, tol_for_ne, (VBIAS_MIN, VBIAS_MAX)
                    )
                    if vmax > never_exceed + 1e-12:
                        continue
                cands.append(TwoResCandidate(abs(v - target), v, r1, r2, s))
        cands.sort(key=lambda x: (x.error, x.rsum))
        return cands[: self.limit]

    def search_ok(
        self,
        target_prog: Optional[float],
        target_hyst: Optional[float]
    ) -> List[ThreeResCandidate]:
        cands: List[ThreeResCandidate] = []
        for r1 in self.pool:
            for r2 in self.pool:
                vp = Calculator.vbat_ok_prog(r1, r2)
                for r3 in self.pool:
                    s = r1 + r2 + r3
                    if s > self.rsum_max:
                        continue
                    vh = Calculator.vbat_ok_hyst(r1, r2, r3)
                    if not self.limits.ok_relationships(vp, vh):
                        continue
                    if target_prog is not None and target_hyst is not None:
                        err = abs(vp - target_prog) + abs(vh - target_hyst)
                    elif target_prog is not None:
                        err = abs(vp - target_prog)
                    elif target_hyst is not None:
                        err = abs(vh - target_hyst)
                    else:
                        continue
                    cands.append(ThreeResCandidate(err, vp, vh, r1, r2, r3, s))
        cands.sort(key=lambda x: (x.error, x.rsum))
        return cands[: self.limit]

class Formatter:
    @staticmethod
    def ohm(x: float) -> str:
        if x >= 1e6:
            return f"{x/1e6:.2f} MΩ"
        if x >= 1e3:
            return f"{x/1e3:.0f} kΩ"
        return f"{x:.0f} Ω"

    @staticmethod
    def print_two_section(title: str, rows: Iterable[TwoResCandidate], vfunc: Callable[..., float], tol: float) -> None:
        print(f"\n# {title}")
        print("# R1(bottom), R2(top), RSUM, V(nom), 1%[min..max], 10%[min..max]")
        for row in rows:
            m1, M1 = WorstCase.two_res_bounds(
                vfunc, row.r1, row.r2, tol, (VBIAS_MIN, VBIAS_MAX)
            )
            m10, M10 = WorstCase.two_res_bounds(
                vfunc, row.r1, row.r2, 0.10, (VBIAS_MIN, VBIAS_MAX)
            )
            print(
                f"{Formatter.ohm(row.r1)}  "
                f"{Formatter.ohm(row.r2)}  "
                f"{Formatter.ohm(row.rsum)}  "
                f"{row.v_nom:.3f} V  "
                f"1% [{m1:.3f}..{M1:.3f}]  "
                f"10% [{m10:.3f}..{M10:.3f}]"
            )

    @staticmethod
    def print_ok_section(title: str, rows, tol: float) -> None:
        print(f"\n# {title}")
        print("# R_OK1(bottom), R_OK2(mid), R_OK3(top), RSUM, "
              "VBAT_OK_PROG(nom)[1%/10%], VBAT_OK_HYST(nom)[1%/10%]")
        for row in rows:
            (vpmin1, vpmax1), (vhmin1, vhmax1) = WorstCase.ok_bounds(
                row.r1, row.r2, row.r3, 0.01, (VBIAS_MIN, VBIAS_MAX)
            )
            (vpmin10, vpmax10), (vhmin10, vhmax10) = WorstCase.ok_bounds(
                row.r1, row.r2, row.r3, 0.10, (VBIAS_MIN, VBIAS_MAX)
            )
            print(
                f"{Formatter.ohm(row.r1)}  "
                f"{Formatter.ohm(row.r2)}  "
                f"{Formatter.ohm(row.r3)}  "
                f"{Formatter.ohm(row.rsum)}  "
                f"VBAT_OK_PROG={row.v_prog:.3f} V [1% {vpmin1:.3f}..{vpmax1:.3f}; 10% {vpmin10:.3f}..{vpmax10:.3f}]  "
                f"VBAT_OK_HYST={row.v_hyst:.3f} V [1% {vhmin1:.3f}..{vhmax1:.3f}; 10% {vhmin10:.3f}..{vhmax10:.3f}]"
            )

class CLI:
    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser(
            prog="bq25570_calc",
            description="Resistor divider optimizer for TI bq25570: VOUT, VBAT_OV, VBAT_OK.",
            formatter_class=argparse.RawTextHelpFormatter,
            epilog="""Examples:

  # Common rails
  bq25570_calc --vout 1.8 3.3

  # LiPo 1-cell (VBAT_OV = 4.2 V)
  bq25570_calc --vbat-ov 4.2 --never-exceed-ov

  # Battery-Good window
  bq25570_calc --vbat-ok-prog 3.5 --vbat-ok-hyst 3.7
"""
        )

        self.parser.add_argument("--vout", nargs="*", type=float, default=[1.8, 3.0, 3.3],
            help="Target VOUT values (V).")
        self.parser.add_argument("--vbat-ov", type=float, default=None,
            help="Target VBAT_OV (V).")
        self.parser.add_argument("--never-exceed-ov", action="store_true",
            help="Ensure 1%% worst-case never exceeds VBAT_OV.")
        self.parser.add_argument("--vbat-ok-prog", type=float, default=None,
            help="VBAT_OK falling threshold (V).")
        self.parser.add_argument("--vbat-ok-hyst", type=float, default=None,
            help="VBAT_OK rising threshold (V).")
        self.parser.add_argument("--vbat-uv", type=float, default=1.95,
            help="Internal UV reference (V).")
        self.parser.add_argument("--series", choices=["E24", "E96"], default="E24",
            help="Resistor series.")
        self.parser.add_argument("--decades", nargs=2, type=int, default=[6, 7], metavar=("MIN", "MAX"),
            help="Decade range, e.g., 6 7 for ~1–10 MΩ.")
        self.parser.add_argument("--rsum-max", type=float, default=DEFAULT_RSUM_MAX,
            help="Max total resistance (Ω).")
        self.parser.add_argument("--limit", type=int, default=4,
            help="Limit number of candidates.")
        self.parser.add_argument("--tolerance", type=float, default=0.01,
            help="Resistor tolerance for worst-case calculations (default 0.01 = 1%%).")

    def run(self) -> None:
        if len(sys.argv) == 1:
            self.parser.print_help()
            return

        args = self.parser.parse_args()

        # Validate limits once before optimization
        if '--vout' in sys.argv:
            if any(v < 2.0 or v > 5.5 for v in args.vout):
                sys.exit("Error: VOUT must be between 2.0 V and 5.5 V.")

        if '--vbat-ov' in sys.argv:
            if args.vbat_ov is not None and not (2.2 <= args.vbat_ov <= 5.5):
                sys.exit("Error: VBAT_OV must be between 2.2 V and 5.5 V.")

        if '--vbat-ok-prog' in sys.argv or '--vbat-ok-hyst' in sys.argv:
            if args.vbat_ok_prog is None or args.vbat_ok_hyst is None:
                sys.exit("Error: Both --vbat-ok-prog and --vbat-ok-hyst must be provided.")
            if args.vbat_ok_prog < args.vbat_uv:
                sys.exit("Error: VBAT_OK_PROG must be >= VBAT_UV.")
            if args.vbat_ok_hyst <= args.vbat_ok_prog:
                sys.exit("Error: VBAT_OK_HYST must be > VBAT_OK_PROG.")
            if args.vbat_ov is not None and args.vbat_ok_hyst > args.vbat_ov:
                sys.exit("Error: VBAT_OK_HYST must be <= VBAT_OV.")

        limits = DatasheetLimits(args.vbat_uv, args.vbat_ov)
        series = ESeries(args.series, args.decades[0], args.decades[1])
        opt = Optimizer(series, args.rsum_max, args.limit, limits)

        # Print VOUT section
        if '--vout' in sys.argv:
            for v in args.vout:
                rows = opt.search_two(v, Calculator.vout, target_checker=limits.allow_vout_target)
                Formatter.print_two_section(f"VOUT = {v:.3f} V", rows, Calculator.vout, args.tolerance)

        # Print VBAT_OV section
        if '--vbat-ov' in sys.argv:
            rows_ov = opt.search_two(
                args.vbat_ov,
                Calculator.vbat_ov,
                never_exceed=(args.vbat_ov if args.never_exceed_ov else None),
                tol_for_ne=0.01,
                target_checker=limits.allow_vbat_ov_target
            )
            title = f"VBAT_OV = {args.vbat_ov:.3f} V"
            if args.never_exceed_ov:
                title += " (NEVER-EXCEED@1%)"
            Formatter.print_two_section(title, rows_ov, Calculator.vbat_ov, args.tolerance)

        # Print VBAT_OK section
        if '--vbat-ok-prog' in sys.argv and '--vbat-ok-hyst' in sys.argv:
            rows_ok = opt.search_ok(args.vbat_ok_prog, args.vbat_ok_hyst)
            title = f"VBAT_OK PROG={args.vbat_ok_prog:.3f} V HYST={args.vbat_ok_hyst:.3f} V"
            Formatter.print_ok_section(title, rows_ok, args.tolerance)

if __name__ == "__main__":
    CLI().run() 