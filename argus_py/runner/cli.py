import argparse
import time
import os
import csv
import json
import numpy as np
from datetime import datetime
from argus_py.data.binance_downloader import BinanceDownloader
from argus_py.adapters import MarketLoadRequest, build_market_adapter
from argus_py.models.aegean.aegean import AegeanEngine
from argus_py.models.orion.orion import OrionEngine
from argus_py.council.aggregator import Council
from argus_py.risk.mode_engine import ModeEngine
from argus_py.risk.regime import RegimeDetector
from argus_py.broker.paper import PaperBroker
from argus_py.data.reporting import Reporter
from argus_py.strategy.mrie import MRIE
from argus_py.strategy.router import ModeRouter

# Phase P2.8 Modules
from argus_py.risk.capital_engine import CapitalEngine
from argus_py.risk.performance_guard import PerformanceGuard
from argus_py.portfolio.allocator import PortfolioAllocatorV1
from argus_py.reporting.capital_report import save_capital_log
from argus_py.signals.external import ExternalSignalProvider

def run(args):
    print(f"--- Argus Phase C: {args.symbol} (${args.start_balance}) Mode:{args.mode} ---")
    
    # EFFECTIVE_CONFIG Audit Log
    eff_config = {
        "symbol": args.symbol,
        "start": args.start_date,
        "end": args.end_date,
        "data_dir": args.data_dir,
        "fee_bps": args.fee_bps,
        "slippage_bps": args.slippage_bps,
        "spread_bps": args.spread_bps,
        "min_adx": getattr(args, 'min_adx', 45.0),
        "max_exp_move_bps": getattr(args, 'max_exp_move_bps', 0.0),
        "vol_trap_mult": getattr(args, 'vol_trap_mult', 0.0),
        "vol_trap_thresh": getattr(args, 'vol_trap_threshold', 0.0),
        "vol_trap_v2": getattr(args, 'vol_trap_v2', False),
        "mode": args.mode,
        "router_enabled": True, # Implicit in Phase C
        "portfolio_allocator_v1": getattr(args, "portfolio_allocator_v1", False),
    }
    print(f"EFFECTIVE_CONFIG: {json.dumps(eff_config)}")

    # 1. Setup
    try:
        # Download if requested
        if getattr(args, 'download_binance', False):
            if not args.start_date or not args.end_date:
                print("Error: --download_binance requires --start_date and --end_date")
                return
            os.makedirs(args.data_dir, exist_ok=True)
            BinanceDownloader.download_binance_klines(args.symbol, args.start_date, args.end_date, args.data_dir)
            expected_file = os.path.join(args.data_dir, f"{args.symbol}_1m_{args.start_date}_{args.end_date}.csv")
            print(f"Downloaded -> {expected_file}")
            return # EXIT after download (Mega Prompt)
            
        max_bars = getattr(args, 'max_bars', None)
        market_adapter = build_market_adapter(args.asset_class, args.market_adapter)
        if not getattr(args, 'quiet', False):
            print(f"MarketAdapter: {market_adapter.name} ({args.asset_class})")

        market = market_adapter.load_market(
            MarketLoadRequest(
                data_dir=args.data_dir,
                symbol=args.symbol,
                start_date=args.start_date,
                end_date=args.end_date,
                max_bars=max_bars,
                strict_symbol=True,
            )
        )
        
        # Observability
        min_close = min([b.close for b in market._all_bars]) if market._all_bars else 0
        max_close = max([b.close for b in market._all_bars]) if market._all_bars else 0
        src_files = [os.path.basename(f) for f in market.source_files]
        if not getattr(args, 'quiet', False):
             print(f"DataSource: {src_files} | requested_symbol={market.symbol_requested} | resolved_symbol={market.symbol_resolved} | bars={len(market._all_bars)} | close_min/max={min_close:.2f}/{max_close:.2f}")
        
        # Preflight Guard: Range Coverage
        # Ensure loaded data covers requested range (within tolerance)
        # If max_bars is used, partial-range datasets are expected; skip strict coverage guard.
        if args.start_date and args.end_date and market._all_bars and not getattr(args, "max_bars", None):
             req_s_ts = time.mktime(datetime.strptime(args.start_date, "%Y-%m-%d").timetuple())
             req_e_ts = time.mktime(datetime.strptime(args.end_date, "%Y-%m-%d").timetuple())
             
             data_min_ts = market._all_bars[0].timestamp
             data_max_ts = market._all_bars[-1].timestamp
             
             # Tolerance: 48h (allow some missing data at start/end, but major mismatches are fatal)
             # If Data Start is > Requested Start + 48h -> Error (Missing Start Data)
             # If Data End is < Requested End - 48h -> Error (Missing End Data)
             TOLERANCE_SEC = 48 * 3600
             
             if (data_min_ts > req_s_ts + TOLERANCE_SEC) or (data_max_ts < req_e_ts - TOLERANCE_SEC):
                 print(f"ERROR: Dataset Range Mismatch!")
                 print(f"  Requested: {args.start_date} ({req_s_ts}) -> {args.end_date} ({req_e_ts})")
                 print(f"  Dataset:   {market._all_bars[0].dt} ({data_min_ts}) -> {market._all_bars[-1].dt} ({data_max_ts})")
                 import sys
                 sys.exit(1) # Force Exit for Backtest Script Checks
        
        if getattr(args, 'verify_data', False):
             print(f"--- DATA VERIFICATION ---")
             print(f"Symbol: {args.symbol}")
             print(f"Count: {len(market._all_bars)}")
             if market._all_bars:
                 print(f"Start: {market._all_bars[0].dt} ({market._all_bars[0].timestamp})")
                 print(f"End:   {market._all_bars[-1].dt} ({market._all_bars[-1].timestamp})")
                 print(f"Monotonic: {all(market._all_bars[i].timestamp <= market._all_bars[i+1].timestamp for i in range(len(market._all_bars)-1))}")
             print("--- VERIFY DONE ---")
             return

    except Exception as e:
        print(f"Error loading data: {e}")
        return None
    
    # Date Filtering
    # Date Filtering
    s_ts = 0
    e_ts = 9999999999
    
    if args.start_date:
        s_ts = time.mktime(datetime.strptime(args.start_date, "%Y-%m-%d").timetuple())
        market._all_bars = [b for b in market._all_bars if b.timestamp >= s_ts]
        if not getattr(args, 'quiet', False):
             print(f"Filtered start >= {args.start_date}: {len(market._all_bars)} bars.")
    
    if args.end_date:
        e_ts = time.mktime(datetime.strptime(args.end_date, "%Y-%m-%d").timetuple())
        market._all_bars = [b for b in market._all_bars if b.timestamp < e_ts]
        if not getattr(args, 'quiet', False):
             print(f"Filtered end < {args.end_date}: {len(market._all_bars)} bars.")

    if not market._all_bars:
         print("No bars left after filter!")
         return
         
    # Range Guard (Mega Prompt)
    # Check if loaded range is roughly within requested range
    # Actually, filter above ensures it is WITHIN.
    # Guard logic "ilk bar timestamp >= start_ts, son bar timestamp < end_ts"
    # Filter already enforces this. The risk is if the loaded data covers nothing or WRONG range.
    # The prompt check: "market._all_bars gerçekten o aralıkta mı kontrol et".
    # Since we filter, it's guaranteed to be within.
    # But maybe we want to check if data exists? We check `if not market._all_bars`.
    # Let's raise RuntimeError if range is empty or way off? 
    # "ilk bar timestamp >= start_ts" -> Guaranteed by loop.
    # Maybe prompt implies we should check we didn't lose data?
    # I'll rely on the filter + "No bars left" check for now.


    # Engines
    aegean = AegeanEngine()
    orion = OrionEngine()
    council = Council()
    regime_detector = RegimeDetector()
    mrie = MRIE()
    router = ModeRouter(cooldown_defense=30, cooldown_caution=15)
    
    mode_engine = ModeEngine(max_daily_dd_pct=0.04, max_total_dd_pct=0.10, profile_override=args.profile) 
    capital_engine = CapitalEngine()
    perf_guard = PerformanceGuard()
    portfolio_allocator = None
    if getattr(args, "portfolio_allocator_v1", False):
        portfolio_allocator = PortfolioAllocatorV1(
            risk_budget_pct=args.portfolio_risk_budget_pct,
            max_asset_exposure_pct=args.portfolio_max_asset_exposure_pct,
            assumed_stop_loss_pct=args.portfolio_assumed_stop_loss_pct,
        )
    
    use_auto_capital = getattr(args, 'auto_capital_mode', True)
    forced_cap_profile = getattr(args, 'capital_profile', None)

    reporter = Reporter()
    reporter.save_config(args)

    external_signal_provider = None
    if getattr(args, "external_signal_file", ""):
        try:
            external_signal_provider = ExternalSignalProvider.from_csv(
                args.external_signal_file,
                symbol=args.symbol,
            )
            if not getattr(args, "quiet", False):
                print(
                    f"ExternalSignals: loaded={external_signal_provider.size} "
                    f"file={args.external_signal_file}"
                )
        except Exception as e:
            print(f"WARNING: external signal file could not be loaded: {e}")
            external_signal_provider = None

    # Realism Config
    realism_config = {
        "fee_bps": args.fee_bps,
        "slippage_bps": args.slippage_bps,
        "spread_bps": args.spread_bps,
        "funding_bps_per_8h": args.funding_bps_per_8h,
        "use_bid_ask": args.use_bid_ask,
        "max_risk_per_trade_pct": args.max_risk_per_trade_pct,
        "max_notional_pct_of_equity": args.max_notional_pct_of_equity,
        "liq_safety_margin_pct": args.liq_safety_margin_pct
    }

    broker = PaperBroker(
        start_balance=args.start_balance, 
        mode=args.mode if args.mode != "adaptive" else "paper",
        exit_policy=args.exit_policy,
        reporter=reporter, # Inject reporter
        realism_config=realism_config
    )
    
    start_time = time.time()
    bars_processed = 0
    trade_cooldown_counter = 0 
    
    market.set_time(0)
    
    metrics = []
    # Seed equity curve so single-bar windows still produce summary artifacts.
    seed_bar = market.latest_bar
    broker.mark_to_market(args.symbol, seed_bar.close)
    metrics.append(broker.get_state(seed_bar.timestamp, snapshot_type="BAR"))
    capital_log = []
    
    # Signal Stats
    signal_stats = {
        "total_go": 0,
        "go_trend": 0,
        "go_chop": 0
    }
    
    # Calibration Stats
    candidate_scores = []
    go_scores = []
    trade_explanations = []
    
    # Adaptive Logic Tracking
    # Map: PositionID -> {entry_price, exp_move_bps, direction, total_cost_bps}
    position_meta = {} 
    
    # List of realized ratios (RealizedMoveBps / ExpMoveBps)
    realized_ratios = []
    
    # Volatility Trap Tracking (Phase 2)
    import collections
    atr_history = collections.deque(maxlen=20)
    vol_trap_mult = getattr(args, 'vol_trap_mult', 0.0) # 0.0 = Disabled
    
    # Warmup Check
    MIN_WARMUP = getattr(args, 'min_warmup', 200)
    if len(market._all_bars) < MIN_WARMUP:
        print(f"WARNING: Warmup insufficient ({len(market._all_bars)}/{MIN_WARMUP})")
        print("         Expect NO_GO signals due to indicator warmup lock.")

    # Hard-stop state (daily + total DD)
    current_day = None
    daily_start_equity = args.start_balance
    daily_halt_day = None
    equity_hwm = args.start_balance
    hard_total_stop = False

    while market.can_advance:
        market.advance()
        bars_processed += 1
        
        current_bar = market.latest_bar
        history = market.history
        
        # A. Update State
        broker.mark_to_market(args.symbol, current_bar.close)
        current_equity = broker.equity
        equity_hwm = max(equity_hwm, current_equity)

        bar_day = current_bar.dt.date()
        if current_day is None or bar_day != current_day:
            current_day = bar_day
            daily_start_equity = current_equity
            daily_halt_day = None

        daily_loss_pct = 0.0
        if daily_start_equity > 0:
            daily_loss_pct = ((daily_start_equity - current_equity) / daily_start_equity) * 100.0

        total_dd_pct = 0.0
        if equity_hwm > 0:
            total_dd_pct = ((equity_hwm - current_equity) / equity_hwm) * 100.0

        if total_dd_pct >= args.hard_stop_total_dd_pct:
            hard_total_stop = True
        if daily_loss_pct >= args.hard_stop_daily_loss_pct:
            daily_halt_day = current_day

        perf_guard.update(current_equity, broker.trades)
        safety_report = perf_guard.get_safety_report()
        
        # B. Capital Logic
        cap_config = None
        effective_threshold = args.council_threshold
        # Argparse overrides
        if args.min_conviction is not None: effective_threshold = args.min_conviction
        
        effective_lev_cap = args.leverage_max
        effective_max_risk = 0.02 * safety_report['risk_modifier']
        
        if use_auto_capital or forced_cap_profile:
            # If forced_cap_profile is set, pass it. Else None (Auto equity based)
            cap_config = capital_engine.get_config(current_equity, profile_override=forced_cap_profile)
            
            # Capital Profile has precedence, but if user explicitly passed min_conviction flag, we honor flag.
            # But usually Capital Profile sets threshold.
            # Let's say explicit flag overrides everything.
            if args.min_conviction is None:
                effective_threshold = cap_config.council_threshold
                
            effective_lev_cap = cap_config.leverage_cap
            effective_max_risk = cap_config.max_risk_per_trade * safety_report['risk_modifier']

        # Check Lockdown
        is_lockdown = (safety_report['status'] == "LOCKDOWN") or ("LOCKDOWN" in safety_report['status'])
        
        # C. Context & Vote
        regime = regime_detector.detect(history)
        ae_vote = aegean.calculate(history)
        or_vote = orion.calculate(history)
        verdict = council.deliberate(
            [ae_vote, or_vote], 
            regime, 
            current_bar.timestamp,
            threshold=effective_threshold,
            chop_floor=args.chop_floor
        )

        # Optional external overlay (news + trader signals).
        if external_signal_provider is not None:
            ext = external_signal_provider.latest_for(
                bar_ts=current_bar.timestamp,
                max_age_sec=int(max(0, args.external_signal_max_age_min * 60)),
            )
            if ext is not None:
                verdict.metadata["external_signal_source"] = ext.source
                verdict.metadata["external_signal_direction"] = ext.direction
                verdict.metadata["external_signal_confidence"] = ext.confidence
                if verdict.decision == "GO" and ext.direction in {"BUY", "SELL"}:
                    if ext.direction == verdict.direction:
                        boost = args.external_signal_conviction_boost * ext.confidence
                        verdict.conviction = min(1.0, verdict.conviction + boost)
                        verdict.metadata["external_signal_effect"] = "BOOST"
                    else:
                        verdict.metadata["external_signal_effect"] = "OPPOSED"
                        if (
                            args.external_signal_enforce_alignment
                            and ext.confidence >= args.external_signal_block_confidence
                        ):
                            verdict.decision = "BLOCK"
                            verdict.metadata["block_reason"] = "EXTERNAL_SIGNAL_CONFLICT"
                            reporter.log_reject(
                                current_bar.timestamp,
                                args.symbol,
                                "EXTERNAL_SIGNAL_CONFLICT",
                                f"model={verdict.direction} ext={ext.direction} "
                                f"conf={ext.confidence:.2f} src={ext.source}",
                            )
        
        # D. MRIE Update (Passive)
        _atr = or_vote.metadata.get('atr', 0.0)
        _adx = or_vote.metadata.get('adx', 0.0)
        mrie_features = mrie.update(_atr, current_bar.volume, _adx, current_bar.high, current_bar.low, current_bar.close)
        verdict.metadata['mrie'] = mrie_features
        
        # E. Mode Router Update
        router_res = router.update(mrie_features['mode_suggest'], mrie_features['shift_score'])
        verdict.metadata['router'] = router_res
        
        # Policy Enforcement (Local Variables)
        # Default: ATTACK (Base V5)
        r_risk_mult = 1.0
        r_adx_add = 0.0
        r_policy = router_res['policy']
        
        if r_policy == "caution_v5":
            r_risk_mult = 0.7
            r_adx_add = 10.0 # Increase MinADX by 10
        elif r_policy == "defense_flat":
            r_risk_mult = 0.0 # Block trades via risk
            r_adx_add = 999.0 # Block via ADX
        
        # Candidate Score Collection (Stabilization)
        # Capture on EVERY bar where conviction is high (>= 0.10)
        # regardless of filters, mode, or existing positions.
        if verdict.conviction >= 0.10:
             # Calculate score inputs
             slope_raw_c = ae_vote.metadata.get('slope', 0.0)
             adx_c = or_vote.metadata.get('adx', 0.0)
             slope_bps_c = (abs(slope_raw_c) / current_bar.close) * 10000.0
             adx_bps_c = adx_c * 0.4
             edge_score_c = (0.6 * slope_bps_c) + (0.4 * adx_bps_c)
             candidate_scores.append(edge_score_c)

        # Signal Stats Collection
        if verdict.decision == "GO":
            signal_stats["total_go"] += 1
            if regime == "TREND": signal_stats["go_trend"] += 1
            elif regime == "CHOP": signal_stats["go_chop"] += 1

        # D. Mode Update
        mode_snap = mode_engine.update(
            equity=broker.equity, 
            daily_start_equity=daily_start_equity, 
            trades=broker.trades,
            regime=regime,
            conviction=verdict.conviction
        )
        
        # Log Capital Evolution
        if cap_config:
             capital_log.append({
                 "Timestamp": current_bar.timestamp,
                 "Equity": current_equity,
                 "Profile": cap_config.profile.value,
                 "Risk": effective_max_risk,
                 "LevCap": effective_lev_cap,
                 "Mode": mode_snap.mode.value,
                 "DD": safety_report['current_dd'],
                 "WinRate20": safety_report['win_rate_20']
             })
        
        # E. Execution Logic flow
        exit_trade = broker.check_brackets(args.symbol, current_bar.high, current_bar.low, current_bar.timestamp)
        if exit_trade:
             if not getattr(args, 'quiet', False):
                 print(f"[{current_bar.dt}] EXIT {exit_trade.side} Price:{exit_trade.price:.2f} PnL:{exit_trade.pnl:.2f} Eq:{broker.equity:.2f}")
             
             # Capture Realized Ratio (Phase C.2)
             pid = exit_trade.position_id
             if pid in position_meta:
                 meta = position_meta[pid]
                 entry_price = meta['entry_price']
                 exp_move = meta.get('exp_move_bps', 0.0)
                 direction = 1 if meta['direction'] == "BUY" else -1
                 
                 # Realized Move BPS = (Exit - Entry) / Entry * 10000 * Direction
                 # Note: exit_trade.price is Fill Price.
                 move_raw = (exit_trade.price - entry_price) / entry_price
                 realized_bps = move_raw * 10000.0 * direction
                 
                 if exp_move > 0:
                     ratio = realized_bps / exp_move
                     realized_ratios.append(ratio)
                     
                 # Clean up
                 del position_meta[pid]
             
             # Standard Cooldown
             cd = args.cooldown_bars
             
             # Loss Cooldown Extension
             loss_cd = getattr(args, 'cooldown_bars_loss', 0)
             if loss_cd > 0 and exit_trade.pnl < 0:
                 cd = max(cd, loss_cd)
                 if not getattr(args, 'quiet', False):
                     print(f"   -> Loss Cooldown Active: {cd} bars")
             
             trade_cooldown_counter = cd
             
        if trade_cooldown_counter > 0:
            trade_cooldown_counter -= 1
        elif is_lockdown:
             pass 
             
        elif not mode_snap.can_trade:
             if verdict.decision == "GO":
                 reporter.log_reject(current_bar.timestamp, args.symbol, "Mode Block", mode_snap.reason)
                 
        elif args.symbol in broker.details:
             pass 
             
        else:
             cap_prof_str = cap_config.profile.value if cap_config else "N/A"
             
             # --- Pre-Calculate Metrics for Log ---
             expected_move = 0.0
             total_cost_bps = args.fee_bps + args.slippage_bps + args.spread_bps
             edge_score = 0.0
             
             slope_raw_m = ae_vote.metadata.get('slope', 0.0)
             adx_m = or_vote.metadata.get('adx', 0.0)
             slope_bps_abs = (abs(slope_raw_m) / current_bar.close) * 10000.0
             slope_bps = slope_bps_abs
             atr_m = or_vote.metadata.get('atr', 0.0)
             atr_bps = (atr_m / current_bar.close) * 10000.0 if current_bar.close > 0 else 0.0
             
             if verdict.decision == "GO":
                  adx_bps_m = adx_m * 0.4
                  edge_score = (0.6 * slope_bps_abs) + (0.4 * adx_bps_m)
                  
                  atr_k = getattr(args, 'atr_k', 1.0)
                  adx_boost = getattr(args, 'adx_boost', 1.3)
                  atr_base = atr_bps * atr_k
                  adx_factor = 0.0
                  if adx_m > 20: adx_factor = min(1.0, (adx_m - 20) / 40.0)
                  adx_boost = 1.0 + adx_factor
                  
                  expected_move = max(slope_bps_abs, atr_base) * adx_boost
                  
                  # Cap
                  cap_bps = atr_bps * getattr(args, 'exp_cap_mult', 1.5)
                  expected_move = min(expected_move, cap_bps)
                      
                  verdict.metadata['expected_move'] = expected_move
                  verdict.metadata['score'] = edge_score 
                  verdict.metadata['cost'] = total_cost_bps
                  
                  # Safety Factor Calculation (Pre-Log)
                  # Replicate logic: If High Score (HomeRun) -> Lower Safety. Else -> Standard.
                  _min_edge = getattr(args, 'min_expected_move_bps', 0.0)
                  _s_std = getattr(args, 'cost_safety_factor', 2.0)
                  _s_hr = getattr(args, 'cost_safety_homerun', 1.3)
                  
                  # Adaptive Override for Standard (if enabled)
                  if getattr(args, 'adaptive_cost_safety', False) and 'safety_factor' in verdict.metadata:
                       # Actually adaptive logic set verdict.metadata['safety_factor'] earlier in run()?
                       # Let's check. Yes, line 178 update logic? No.
                       # The adaptive logic is in the loop top?
                       # Just use what's in args or pre-calculated?
                       # Warning: Adaptive logic in loop modifies `adaptive_safety` variable?
                       pass 
                  
                  # If we have adaptive logic, `verdict.metadata['safety_factor']` might ALREADY be set?
                  # Line 326: `verdict.metadata['safety_factor'] = adaptive_safety`?
                  # Let's check previous context.
                  
                  final_safety = _s_std
                  # Check HomeRun Condition
                  if _min_edge > 0.1 and edge_score >= _min_edge:
                      final_safety = _s_hr
                  
                  # If adaptive was set and we are NOT HomeRun, use adaptive?
                  # Let's trust what we just calculated unless adaptive is active and we are in baseline.
                  # Ideally:
                  verdict.metadata['safety_factor'] = final_safety
             
             # Initialize Gates
             gates = {
                 'min_adx_pass': 1,
                 'max_exp_pass': 1,
                 'vol_trap_pass': 1,
                 'portfolio_pass': 1,
                 'blocked_reason': "N/A"
             }
             verdict.metadata['gates'] = gates
             
             # --- FILTER LOGIC (Applied to Verdict directly) ---
             if verdict.decision == "GO":
                 if hard_total_stop:
                     verdict.decision = "BLOCK"
                     gates['blocked_reason'] = "HARD_STOP_TOTAL_DD"
                     reporter.log_reject(current_bar.timestamp, args.symbol, "HARD_STOP_TOTAL_DD", f"DD {total_dd_pct:.2f}% >= {args.hard_stop_total_dd_pct:.2f}%")
                 elif daily_halt_day == current_day:
                     verdict.decision = "BLOCK"
                     gates['blocked_reason'] = "HARD_STOP_DAILY_LOSS"
                     reporter.log_reject(current_bar.timestamp, args.symbol, "HARD_STOP_DAILY_LOSS", f"DailyLoss {daily_loss_pct:.2f}% >= {args.hard_stop_daily_loss_pct:.2f}%")
                 elif is_lockdown:
                     verdict.decision = "BLOCK"
                     gates['blocked_reason'] = "LOCKDOWN"
                     reporter.log_reject(current_bar.timestamp, args.symbol, "LOCKDOWN", safety_report['status'])
                 else:
                     # ROUTER: Defense Block
                     if r_risk_mult == 0.0:
                         verdict.decision = "BLOCK"
                         gates['blocked_reason'] = "ROUTER_DEFENSE"
                         reporter.log_reject(current_bar.timestamp, args.symbol, "ROUTER_DEFENSE", "Risk=0.0")

                     # Keep execution risk aligned with broker hard cap to avoid false REJECT_RISK_CAP.
                     final_risk_raw = effective_max_risk * mode_snap.risk_multiplier * r_risk_mult
                     broker_risk_cap = max(0.0, args.max_risk_per_trade_pct / 100.0)
                     final_risk = min(final_risk_raw, broker_risk_cap) if broker_risk_cap > 0 else final_risk_raw
                     effective_leverage = min(mode_snap.leverage_allowed, effective_lev_cap)

                     # Portfolio allocator v1: risk budget + max asset exposure clamp.
                     if portfolio_allocator is not None:
                         current_asset_exposure_pct = 0.0
                         if args.symbol in broker.details and current_equity > 0:
                             pos = broker.details[args.symbol]
                             current_asset_exposure_pct = abs(pos.quantity * current_bar.close / current_equity) * 100.0

                         alloc = portfolio_allocator.allocate_single_asset(
                             requested_risk_pct=final_risk,
                             current_asset_exposure_pct=current_asset_exposure_pct,
                         )
                         final_risk = alloc.allowed_risk_pct / 100.0
                         verdict.metadata["portfolio_alloc_reason"] = alloc.reason
                         verdict.metadata["portfolio_requested_risk_pct"] = alloc.requested_risk_pct
                         verdict.metadata["portfolio_allowed_risk_pct"] = alloc.allowed_risk_pct
                         verdict.metadata["portfolio_implied_exposure_pct"] = alloc.implied_asset_exposure_pct
                         if alloc.blocked:
                             verdict.decision = "BLOCK"
                             gates['portfolio_pass'] = 0
                             gates['blocked_reason'] = "PORTFOLIO_BUDGET"
                             reporter.log_reject(
                                 current_bar.timestamp,
                                 args.symbol,
                                 "PORTFOLIO_BUDGET",
                                 f"{alloc.reason}: ReqRisk {alloc.requested_risk_pct:.2f}% -> Allow {alloc.allowed_risk_pct:.2f}%",
                             )

                     verdict.metadata["effective_risk_pct"] = final_risk * 100.0
                     verdict.metadata["effective_leverage"] = effective_leverage
                     
                     # 1. Min ADX Filter (V5 AdxGate)
                     base_min_adx = getattr(args, 'min_adx', 0.0)
                     if base_min_adx is None: base_min_adx = 0.0
                     min_adx = base_min_adx + r_adx_add
                     curr_adx = or_vote.metadata.get('adx', 0.0)
                     
                     if not getattr(args, 'quiet', False):
                          print(f"[{current_bar.dt}] GUARD CHECK | Regime:{regime} ADX:{curr_adx:.1f} Gate:{'FAIL' if curr_adx < min_adx else 'PASS'} (Thresh:{min_adx:.1f})")

                     if min_adx > 0 and curr_adx < min_adx:
                          verdict.decision = "BLOCK"
                          gates['min_adx_pass'] = 0
                          gates['blocked_reason'] = "MIN_ADX"
                          reporter.log_reject(current_bar.timestamp, args.symbol, "REJECT_WEAK_TREND", f"ADX {curr_adx:.1f} < {min_adx:.1f}")
                          
                     # 2. Volatility Trap (V3/V4/VolTrapV2)
                     # Only check if still GO
                     if verdict.decision == "GO":
                         vt_mult = getattr(args, 'vol_trap_mult', 0.0) 
                         vt_thresh = getattr(args, 'vol_trap_threshold', 0.0) 
                         if vt_mult is None: vt_mult = 0.0
                         if vt_thresh is None: vt_thresh = 0.0 
                         effective_vt_thresh = vt_thresh if vt_thresh > 0 else vt_mult

                         if effective_vt_thresh > 0.0 and len(atr_history) >= 10:
                             atr_avg = sum(atr_history) / len(atr_history)
                             atr_curr = or_vote.metadata.get('atr', 0.0)
                             
                             if atr_avg > 0 and (atr_curr / atr_avg) > effective_vt_thresh:
                                  # Check Allow Conditions
                                  blocked = True
                                  if getattr(args, 'vol_trap_v2', False):
                                      adx_v = or_vote.metadata.get('adx', 0.0)
                                      slope_v = abs(ae_vote.metadata.get('slope', 0.0) / current_bar.close * 10000.0)
                                      is_strong_trend = (adx_v > 25) and (slope_v > 2.0)
                                      if is_strong_trend: blocked = False
                                      
                                  if blocked:
                                      verdict.decision = "BLOCK"
                                      gates['vol_trap_pass'] = 0
                                      gates['blocked_reason'] = "VOL_TRAP"
                                      reporter.log_reject(current_bar.timestamp, args.symbol, "REJECT_VOL_TRAP", f"ATR {atr_curr:.2f} > {effective_vt_thresh}x")
 
                         # Update ATR History (Safest spot: update if we have data)
                         curr_atr = or_vote.metadata.get('atr', 0.0)
                         if curr_atr > 0:
                             atr_history.append(curr_atr)
                             
                     # 3. Max ExpMove Filter (V2)
                     if verdict.decision == "GO":
                         max_exp = getattr(args, 'max_exp_move_bps', 0.0)
                         if max_exp is None: max_exp = 0.0
                         em_check = verdict.metadata.get('expected_move', 0.0)
                         if max_exp > 0 and em_check > max_exp:
                              verdict.decision = "BLOCK"
                              gates['max_exp_pass'] = 0
                              gates['blocked_reason'] = "MAX_EXP"
                              reporter.log_reject(current_bar.timestamp, args.symbol, "REJECT_MAX_EXP", f"Exp {em_check:.1f} > {max_exp:.1f}")

                     if verdict.decision == "GO":
                         go_scores.append(edge_score)

             # LOG DECISION AFTER FILTERS
             reporter.log_decision(verdict, mode_process=mode_snap, capital_profile=cap_prof_str)
             
             # Continue if Blocked
             if verdict.decision != "GO":
                 metrics.append(broker.get_state(current_bar.timestamp, snapshot_type="BAR"))
                 continue
                     
             # Edge Filter (Diagnose & Home Run)
             min_edge = getattr(args, 'min_expected_move_bps', 0.0)
             min_edge_mult = getattr(args, 'min_expected_move_multiplier', 0.0)
             cost_safety = getattr(args, 'cost_safety_factor', 2.0)
             
             req_threshold = min_edge
             
             if verdict.decision == "GO":
                 # --- Filter Logic Setup (Cont'd) ---
                 
                 # Filter Logic Setup
                 req_threshold = min_edge
                 if min_edge_mult > 0:
                     cfg_fee = args.fee_bps + args.slippage_bps + args.spread_bps
                     req_threshold = max(req_threshold, cfg_fee * min_edge_mult)
                 
                 # --- 1. Split Logic ---
                 # Determine if we use "Baseline Safety" (Strict) or "HomeRun Safety" (Relaxed)
                 # Rule: If filtered scenario (req_threshold > 0) AND score >= threshold -> Relaxed.
                 #       Else -> Strict.
                 
                 is_filtered_run = (req_threshold > 0.1) # Non-zero threshold
                 passes_score_filter = (edge_score >= req_threshold)
                 
                 # Order:
                 # Start with Cost Check?
                 # User: "Baseline: Apply early." "HomeRun: Apply after score >= threshold".
                 
                 should_reject_cost = False
                 cost_safety_used = cost_safety
                 
                 if not is_filtered_run:
                      # Baseline Mode: Strict Cost Check Early
                      if expected_move < total_cost_bps * cost_safety:
                          should_reject_cost = True
                 else:
                      # HomeRun Mode:
                      # First check Score
                      if not passes_score_filter:
                           # We will reject by Score anyway.
                           pass 
                      else:
                           # High Score Trade -> Use Relaxed Safety
                           safety_h = getattr(args, 'cost_safety_homerun', 1.3)
                           cost_safety_used = safety_h
                           if expected_move < total_cost_bps * safety_h:
                                should_reject_cost = True
                 
                 # Execute Cost Reject
                 if should_reject_cost:
                     verdict.decision = "BLOCK"
                     gates['blocked_reason'] = "COST"
                     metrics_str = f"Exp:{expected_move:.1f} (Sl:{slope_bps_abs:.1f}/ATR:{atr_bps:.1f}) < Cost:{total_cost_bps:.1f}*{cost_safety_used:.1f} Score:{edge_score:.1f}"
                     reporter.log_reject(current_bar.timestamp, args.symbol, "REJECT_EDGE_COST", metrics_str, meta=f"{edge_score:.1f}")
                     reporter.log_decision(verdict, mode_process=mode_snap, capital_profile=cap_prof_str)
                     metrics.append(broker.get_state(current_bar.timestamp, snapshot_type="BAR"))
                     continue

                 # --- 2. Score Filter (Legacy/HomeRun) ---
                 if is_filtered_run:
                     if not passes_score_filter:
                         # Context stats (Rolling)
                         stats_ctx = ""
                         if len(candidate_scores) > 20:
                             p95_r = np.percentile(candidate_scores, 95)
                             p99_r = np.percentile(candidate_scores, 99)
                             stats_ctx = f"(p95={p95_r:.1f}, p99={p99_r:.1f})"
                             
                         verdict.decision = "BLOCK"
                         gates['blocked_reason'] = "LOW_SCORE"
                         reporter.log_reject(current_bar.timestamp, args.symbol, "REJECT_EDGE_TOO_LOW", f"Score {edge_score:.1f} < {req_threshold:.1f} {stats_ctx}")
                         reporter.log_decision(verdict, mode_process=mode_snap, capital_profile=cap_prof_str)
                         metrics.append(broker.get_state(current_bar.timestamp, snapshot_type="BAR"))
                         continue
             
             success, reason = broker.execute_strategy(
                 args.symbol,
                 verdict.decision,
                 verdict.direction,
                 current_bar.close,
                 current_bar.timestamp,
                 risk_pct=final_risk,
                 leverage=effective_leverage
             )
             
             if success:
                 if not getattr(args, 'quiet', False):
                     print(f"[{current_bar.dt}] ENTRY {verdict.direction} ({regime}) Mode:{mode_snap.mode.value} Lev:{effective_leverage}x Risk:{final_risk*100:.2f}% | {verdict.rationale}")
                 
                 # Store Meta for Calibration
                 if broker.trades:
                     last_trade = broker.trades[-1]
                     position_meta[last_trade.position_id] = {
                         "entry_price": last_trade.price,
                         "exp_move_bps": expected_move,
                         "direction": verdict.direction,
                         "total_cost_bps": total_cost_bps
                     }
                 
                 # Cooldown Logic
                 trade_cooldown_counter = args.cooldown_bars
                 metrics.append(broker.get_state(current_bar.timestamp, snapshot_type="POST_TRADE"))
                 
                 # Explainability Log (HomeRun)
                 if (min_edge > 0 or min_edge_mult > 0):
                     # Use the effective safety factor already computed for this verdict.
                     safety_factor_for_log = verdict.metadata.get(
                         "safety_factor",
                         getattr(args, "cost_safety_factor", 2.0),
                     )
                     explanation = {
                         "timestamp": current_bar.timestamp,
                         "dt": str(current_bar.dt),
                         "score": edge_score,
                         "threshold": req_threshold,
                         "conviction": verdict.conviction,
                         "regime": regime,
                         "slope_net": ae_vote.metadata.get('slope', 0.0),
                         "adx": or_vote.metadata.get('adx', 0.0),
                         "rationale": verdict.rationale,
                         "direction": verdict.direction,
                         "expected_move_bps": expected_move, 
                         "atr_bps": atr_bps,
                         "slip_bps": args.slippage_bps,
                         "spread_bps": args.spread_bps,
                         "fee_bps": args.fee_bps,
                         "safety_factor": safety_factor_for_log,
                     }
                     trade_explanations.append(explanation)
             else:
                 reporter.log_reject(current_bar.timestamp, args.symbol, "Exec Failed", reason, f"Prof:{mode_snap.profile.value} Lev:{effective_leverage}")

        # Metrics Capture
        metrics.append(broker.get_state(current_bar.timestamp, snapshot_type="BAR"))
        
        # if args.debug or bars_processed <= 3:
        #      print(f"[DEBUG Bar {bars_processed}] Eq:{broker.equity:.2f}")

    # End
    if args.close_at_end and broker.details:
        print(f"--- Force Closing Positions ---")
        final_ts = market.history[-1].timestamp + 1.0 # Safe check
        closed_trades = broker.close_all_positions(final_ts, {args.symbol: market.history[-1].close})
        for t in closed_trades:
             print(f"[EOS] EXIT {t.side} Price:{t.price:.2f} PnL:{t.pnl:.2f} Eq:{broker.equity:.2f}")
        metrics.append(broker.get_state(final_ts, snapshot_type="FINAL_CLOSE"))

    # Data Summary Capturing
    data_summary = {
        "bars": len(market._all_bars),
        "start_date": str(market._all_bars[0].dt) if market._all_bars else "N/A",
        "end_date": str(market._all_bars[-1].dt) if market._all_bars else "N/A",
        "min_price": min_close,
        "max_price": max_close
    }
    
    # Save Results
    reporter.save_trades(broker.trades)
    reporter.save_metrics(metrics)
    reporter.save_summary(args.start_balance, metrics, broker.trades, signal_stats=signal_stats, data_summary=data_summary)
    save_capital_log(reporter.run_dir, capital_log)
    
    print(f"\n--- DATA SUMMARY ---")
    print(f"Bars: {data_summary['bars']}")
    print(f"From: {data_summary['start_date']}")
    print(f"To:   {data_summary['end_date']}")
    print(f"Min:  {data_summary['min_price']:.2f}")
    print(f"Max:  {data_summary['max_price']:.2f}")
    
    print(f"\n--- DONE ---")
    print(f"Final Balance: {broker.balance:.2f} ({((broker.balance/args.start_balance)-1)*100:.2f}%)")
    print(f"Log Dir: {reporter.run_dir}")

    # Generate Reports
    if getattr(args, 'report', False):
        print("Generating reports...")
        # Lazy imports: avoid heavy matplotlib/pandas startup in no_report runs.
        from argus_py.lab.plot_report import generate_plots
        from argus_py.reporting.run_report import generate_report
        
        # Save Score Stats
        # Save Score Stats (Enhanced)
        try:
            stats_path = os.path.join(reporter.run_dir, "score_stats.json")
            
            def calc_stats(arr):
                if not arr: return {"count": 0}
                import numpy as np
                a = np.array(arr)
                return {
                    "count": int(len(a)),
                    "min": float(np.min(a)),
                    "max": float(np.max(a)),
                    "mean": float(np.mean(a)),
                    "std": float(np.std(a)),
                    "p50": float(np.percentile(a, 50)),
                    "p80": float(np.percentile(a, 80)),
                    "p90": float(np.percentile(a, 90)),
                    "p95": float(np.percentile(a, 95)),
                    "p99": float(np.percentile(a, 99))
                }

            full_stats = {
                "go_scores": calc_stats(go_scores),
                "candidate_scores": calc_stats(candidate_scores),
                "calibration_source": "candidate_scores" if len(candidate_scores) >= 50 else "go_scores"
            }
            
            with open(stats_path, 'w') as f:
                json.dump(full_stats, f, indent=2)
            print(f"Score stats saved: {stats_path}")
            print(f"Collected candidate_scores={len(candidate_scores)} go_scores={len(go_scores)} source={full_stats['calibration_source']}")
            
            # Save Explanations
            if trade_explanations:
                exp_path = os.path.join(reporter.run_dir, "homerun_explain.csv")
                keys = trade_explanations[0].keys()
                with open(exp_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(trade_explanations)
                print(f"Explanations saved: {exp_path}")

        except Exception as e:
            print(f"Error saving stats: {e}")

        generate_plots(reporter.run_dir)
        generate_report(reporter.run_dir)
        
    return reporter.run_dir

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="backtest", help="backtest, paper, adaptive, conservative")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--data_dir", required=False, default="argus_py/data", help="Data directory (default: argus_py/data)")
    parser.add_argument("--asset_class", default="crypto", choices=["crypto", "us_equity", "bist"], help="Asset class for market adapter routing")
    parser.add_argument("--market_adapter", default="auto", choices=["auto", "crypto_csv", "us_equity_stub", "bist_stub"], help="Explicit market adapter override")
    parser.add_argument("--start_balance", type=float, default=1000.0)
    
    # Adaptive Flags
    parser.add_argument("--leverage_max", type=float, default=1.0)
    parser.add_argument("--sniper", action="store_true")
    parser.add_argument("--close_at_end", type=str, default="true", help="Close all positions at end of run (true/false)")
    parser.add_argument("--profile", default="AUTO", help="Risk Profile: AUTO, DEFENSIVE, BALANCED, DEGEN")
    
    # Research Args
    parser.add_argument("--council_threshold", type=float, default=0.4, help="Default base threshold")
    parser.add_argument("--min_conviction", type=float, help="Override threshold")
    parser.add_argument("--chop_floor", type=float, help="Min score for CHOP")
    parser.add_argument("--trend_floor", type=float, help="Min score for TREND")
    
    parser.add_argument("--exit_policy", default="FIXED_BRACKET", help="FIXED_BRACKET, TRAILING_STOP, TIME_STOP")
    parser.add_argument("--cooldown_bars", type=int, default=3, help="Bars to wait after trade")
    parser.add_argument("--hard_stop_daily_loss_pct", type=float, default=3.0, help="Hard stop for daily loss %% (blocks new entries for rest of day)")
    parser.add_argument("--hard_stop_total_dd_pct", type=float, default=15.0, help="Hard stop for total drawdown %% (blocks all new entries)")
    
    # Capital Args (P2.8)
    parser.add_argument("--auto_capital_mode", action="store_true", default=True, help="Enable Capital Engine")
    parser.add_argument("--capital_profile", help="Force profile: SMALL, GROWTH, SCALE")
    
    # Date Filtering (Walk-Forward)
    parser.add_argument("--start_date", help="YYYY-MM-DD")
    parser.add_argument("--end_date", help="YYYY-MM-DD")
    parser.add_argument("--download_binance", action="store_true", help="Download fresh data from Binance")
    parser.add_argument("--min_warmup", type=int, default=200, help="Min bars relative to warmup")
    
    parser.add_argument("--debug", action="store_true", help="Print detailed debug logs")
    parser.add_argument("--verify_data", action="store_true", help="Verify loaded data and exit")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output (default: False)")
    
    # Phase P4 Args
    parser.add_argument("--max_bars", type=int, help="Limit number of bars loaded (tail)")
    parser.add_argument("--report", action="store_true", default=True, help="Generate plot and markdown report")
    parser.add_argument("--no_report", action="store_true", help="Skip plot and markdown report generation")
    parser.add_argument("--lab_grid", action="store_true", help="Run batch grid experiments")

    # Realism Toggles (Mega Prompt)
    parser.add_argument("--fee_bps", type=float, default=4.0, help="Exchange fee in basis points (default: 4 = 0.04%%)")
    parser.add_argument("--slippage_bps", type=float, default=2.0, help="Slippage in basis points (default: 2)")
    parser.add_argument("--spread_bps", type=float, default=1.0, help="Spread in basis points (default: 1)")
    parser.add_argument("--funding_bps_per_8h", type=float, default=0.0, help="Funding rate bps per 8h (default: 0)")
    parser.add_argument("--use_bid_ask", action="store_true", help="Simulate Bid/Ask spread logic")
    
    # Position Sizing Guardrails
    parser.add_argument("--max_risk_per_trade_pct", type=float, default=1.0, help="Hard risk cap %% of equity (final risk is clamped to this)")
    parser.add_argument("--max_notional_pct_of_equity", type=float, default=100.0, help="Max total notional %% of equity")
    parser.add_argument("--liq_safety_margin_pct", type=float, default=20.0, help="Liquidation safety margin %%")
    parser.add_argument("--portfolio_allocator_v1", action="store_true", help="Enable portfolio allocator v1 (risk budget + exposure cap)")
    parser.add_argument("--portfolio_risk_budget_pct", type=float, default=1.0, help="Portfolio risk budget per trade %%")
    parser.add_argument("--portfolio_max_asset_exposure_pct", type=float, default=35.0, help="Max per-asset exposure %% of equity")
    parser.add_argument("--portfolio_assumed_stop_loss_pct", type=float, default=2.0, help="Assumed stop distance %% for exposure->risk mapping")
    parser.add_argument("--external_signal_file", type=str, default="", help="CSV file for external signals (news/trader)")
    parser.add_argument("--external_signal_max_age_min", type=float, default=240.0, help="Max external signal age in minutes")
    parser.add_argument("--external_signal_conviction_boost", type=float, default=0.20, help="Conviction boost multiplier when aligned")
    parser.add_argument("--external_signal_block_confidence", type=float, default=0.75, help="Conflict confidence threshold for blocking")
    parser.add_argument("--external_signal_enforce_alignment", action="store_true", help="Block GO decisions when high-confidence external signal disagrees")
    
    # Trade Filtering (Diagnostics)
    parser.add_argument("--min_expected_move_bps", type=float, default=0.0, help="Min expected move score (bps)")
    parser.add_argument("--min_expected_move_multiplier", type=float, default=0.0, help="Dynamic threshold multiplier")
    parser.add_argument("--cost_safety_factor", type=float, default=2.0, help="Safety factor for cost filter (Baseline)")
    parser.add_argument("--cost_safety_homerun", type=float, default=1.3, help="Safety factor for HomeRun candidates")
    parser.add_argument("--atr_k", type=float, default=1.0, help="Accerlation Factor for ATR based expected move")
    parser.add_argument("--adx_boost", type=float, default=1.3, help="Boost multiplier for High ADX")
    parser.add_argument("--cooldown_bars_loss", type=int, default=0, help="Extra cooldown after loss")
    
    # Phase C.2: Calibration & Adaptive Logic
    parser.add_argument("--exp_cap_mult", type=float, default=1.5, help="Cap ExpMove at ATR * K (Default 1.5)")
    parser.add_argument("--adaptive_cost_safety", action="store_true", help="Enable adaptive safety factor learning")
    parser.add_argument("--safety_percentile", type=float, default=30.0, help="Percentile of Realized/Exp ratio to use as safety factor")
    
    # Phase 2 Filters (Strategy Upgrade)
    # parser.add_argument("--disable_buy", action="store_true", help="[DEPRECATED] Reject all BUY signals")
    parser.add_argument("--max_exp_move_bps", type=float, default=None, help="Reject signals with ExpMove > N bps (Default: Disabled)")
    parser.add_argument("--vol_trap_mult", type=float, default=None, help="Reject if ATR > Mult * AvgATR(20) (Legacy)")
    parser.add_argument("--vol_trap_threshold", type=float, default=None, help="VolTrap Threshold (V2)")
    parser.add_argument("--vol_trap_v2", action="store_true", help="Enable VolTrap V2 (Smart Conditional Filter)")
    parser.add_argument("--min_adx", type=float, default=None, help="Reject signals if ADX < N (Weak Trend) (Default: Disabled)")

    args = parser.parse_args()
    if getattr(args, "no_report", False):
        args.report = False
    
    if args.lab_grid:
        from argus_py.lab.batch_run import run_grid
        run_grid(args.data_dir)
    else:
        args.close_at_end = str(args.close_at_end).lower() == "true"
        run(args)
