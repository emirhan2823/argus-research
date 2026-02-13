"""ARGUS v2.5 — Darwin: Genetic Algorithm Engine for Indicator Genome Evolution.

Darwin maintains a population of "Genomes" — each genome encodes the
parameters that govern a specific engine/asset_class combination:
    - Indicator periods (RSI-X, EMA-Y, ADX threshold, BB period, etc.)
    - SL/TP multipliers (ATR-based)
    - Confidence thresholds
    - Signal gate thresholds

Evolution lifecycle:
    1. FULL EVOLUTION: Runs periodically (e.g., weekly). Standard GA cycle
       with selection, crossover, mutation over the full population.
    2. MICRO-EVOLUTION: Triggered by the Reflector when a consistent failure
       mode is detected. Targets ONLY the genes relevant to that failure,
       leaving the rest of the genome frozen.

Architecture
============
Reflector.CorrectionVector  --->  Darwin.micro_evolve()
                                    |
                                    +-- select genes related to failure_mode
                                    +-- apply targeted mutation using correction vector
                                    +-- re-evaluate fitness on recent trade history
                                    +-- promote if improved, rollback if not
                                    |
Periodic Scheduler          --->  Darwin.full_evolve()
                                    |
                                    +-- tournament selection
                                    +-- BLX-alpha crossover (blend for float genes)
                                    +-- adaptive mutation (rate decays with fitness)
                                    +-- elitism (top-K survive unchanged)
                                    +-- fitness = Sharpe - DD_penalty + win_rate_bonus

GPU Acceleration: Fitness evaluation uses vectorized numpy operations.
When population is large, batch evaluation can be offloaded to CUDA via cupy.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import numpy as np

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gene Definition & Genome
# ---------------------------------------------------------------------------


@dataclass
class GeneSpec:
    """Defines a single evolvable parameter with bounds and type."""

    name: str
    min_val: float
    max_val: float
    dtype: str = "float"  # "float" | "int"
    step: Optional[float] = None  # For discrete stepping (e.g., period must be integer)
    description: str = ""


# Default genome template — the superset of evolvable parameters
DEFAULT_GENE_SPECS: list[GeneSpec] = [
    # Trend indicators
    GeneSpec("ema_fast", 8, 34, "int", 1, "Fast EMA period"),
    GeneSpec("ema_slow", 34, 89, "int", 1, "Slow EMA period"),
    GeneSpec("adx_period", 10, 21, "int", 1, "ADX lookback period"),
    GeneSpec("adx_threshold", 18, 35, "float", 0.5, "Min ADX for trend confirmation"),
    # Momentum indicators
    GeneSpec("rsi_period", 7, 21, "int", 1, "RSI lookback period"),
    GeneSpec("rsi_oversold", 20, 40, "float", 1.0, "RSI oversold level"),
    GeneSpec("rsi_overbought", 60, 80, "float", 1.0, "RSI overbought level"),
    GeneSpec("cci_period", 14, 30, "int", 1, "CCI lookback period"),
    # Volatility
    GeneSpec("bb_period", 14, 30, "int", 1, "Bollinger Band period"),
    GeneSpec("bb_std", 1.5, 3.0, "float", 0.1, "BB standard deviation multiplier"),
    GeneSpec("atr_period", 10, 21, "int", 1, "ATR lookback period"),
    # SL/TP
    GeneSpec("sl_atr_mult", 1.0, 4.0, "float", 0.1, "SL as multiple of ATR"),
    GeneSpec("tp_atr_mult", 1.5, 6.0, "float", 0.1, "TP as multiple of ATR"),
    GeneSpec("sl_tighten_after_pct", 0.3, 0.8, "float", 0.05, "Tighten SL after X% of TP reached"),
    # Signal quality gates
    GeneSpec("confidence_threshold", 0.45, 0.75, "float", 0.01, "Min confidence to enter"),
    GeneSpec("min_reward_risk", 1.2, 3.0, "float", 0.1, "Min reward/risk ratio"),
    # Volume
    GeneSpec("volume_spike_mult", 1.2, 3.0, "float", 0.1, "Volume spike detection multiplier"),
    GeneSpec("obv_slope_min", 0.0, 0.5, "float", 0.05, "Min OBV slope for confirmation"),
]

# Map failure modes to the genes they should affect during micro-evolution
FAILURE_MODE_GENE_MAP: dict[str, list[str]] = {
    "sl_too_tight": ["sl_atr_mult", "atr_period"],
    "sl_too_wide": ["sl_atr_mult", "atr_period", "tp_atr_mult"],
    "entry_timing": ["confidence_threshold", "volume_spike_mult", "obv_slope_min"],
    "hermes_veto_ignored": ["confidence_threshold"],  # Not a genome issue, but we can nudge
    "regime_mismatch": ["adx_threshold", "adx_period", "bb_std"],
    "adx_threshold_wrong": ["adx_threshold", "adx_period"],
    "confidence_inflated": ["confidence_threshold", "min_reward_risk"],
    "oracle_divergence": ["confidence_threshold"],
    "sizing_error": ["sl_atr_mult", "tp_atr_mult"],
}


@dataclass
class Genome:
    """A single genome — a complete parameter set for one engine/asset pair."""

    genome_id: str
    engine: str  # TITAN | NAUTILUS | PHOENIX
    asset_class: str  # crypto | us_equity | etc.
    genes: dict[str, float]
    fitness: float = 0.0
    generation: int = 0
    lineage: list[str] = field(default_factory=list)  # Parent genome IDs
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def clone(self, new_id: Optional[str] = None) -> Genome:
        return Genome(
            genome_id=new_id or str(uuid.uuid4()),
            engine=self.engine,
            asset_class=self.asset_class,
            genes=dict(self.genes),
            fitness=self.fitness,
            generation=self.generation,
            lineage=list(self.lineage) + [self.genome_id],
            created_at=datetime.now(timezone.utc).isoformat(),
        )


@dataclass(frozen=True)
class FitnessResult:
    """Output of fitness evaluation for a single genome."""

    sharpe: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    net_pnl: float
    fitness_score: float


@dataclass(frozen=True)
class EvolutionReport:
    """Summary of a single evolution cycle."""

    generation: int
    population_size: int
    best_fitness: float
    mean_fitness: float
    worst_fitness: float
    best_genome_id: str
    mutations_applied: int
    crossovers_applied: int
    elite_preserved: int
    trigger: str  # "full" | "micro:<failure_mode>"
    timestamp: str


# ---------------------------------------------------------------------------
# Fitness Evaluator
# ---------------------------------------------------------------------------


class FitnessEvaluator:
    """Evaluates genome fitness against historical trade data.

    Fitness = w_sharpe * Sharpe + w_winrate * WinRate - w_dd * MaxDD + w_pf * log(PF)

    This is vectorized for speed. For large populations on RTX A3000M,
    the caller can substitute numpy with cupy for GPU acceleration.
    """

    def __init__(
        self,
        *,
        w_sharpe: float = 1.0,
        w_winrate: float = 0.3,
        w_dd: float = 0.8,
        w_profit_factor: float = 0.2,
        min_trades: int = 10,
    ) -> None:
        self.w_sharpe = w_sharpe
        self.w_winrate = w_winrate
        self.w_dd = w_dd
        self.w_profit_factor = w_profit_factor
        self.min_trades = min_trades

    def evaluate(
        self,
        genome: Genome,
        trade_returns: np.ndarray,
    ) -> FitnessResult:
        """Evaluate a genome's fitness on a sequence of trade returns.

        Parameters
        ----------
        genome : The genome being evaluated
        trade_returns : 1D array of per-trade PnL percentages
                        (already filtered to trades that match this genome's
                         engine/asset_class)
        """
        n = len(trade_returns)
        if n < self.min_trades:
            return FitnessResult(
                sharpe=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=n,
                net_pnl=0.0,
                fitness_score=-999.0,  # Penalize insufficient data
            )

        # Sharpe ratio (annualized assuming ~250 trades/year)
        mean_r = float(np.mean(trade_returns))
        std_r = float(np.std(trade_returns, ddof=1))
        sharpe = (mean_r / std_r * math.sqrt(250)) if std_r > 1e-12 else 0.0

        # Max drawdown on cumulative equity curve
        equity = np.cumsum(trade_returns)
        peak = np.maximum.accumulate(equity)
        dd = peak - equity
        max_dd = float(np.max(dd)) if dd.size > 0 else 0.0

        # Win rate
        wins = float(np.sum(trade_returns > 0))
        win_rate = wins / n

        # Profit factor
        gross_profit = float(np.sum(trade_returns[trade_returns > 0]))
        gross_loss = float(np.abs(np.sum(trade_returns[trade_returns < 0])))
        profit_factor = gross_profit / max(gross_loss, 1e-12)

        # Composite fitness score
        fitness = (
            self.w_sharpe * sharpe
            + self.w_winrate * win_rate
            - self.w_dd * max_dd
            + self.w_profit_factor * math.log(max(profit_factor, 0.01))
        )

        return FitnessResult(
            sharpe=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=n,
            net_pnl=float(np.sum(trade_returns)),
            fitness_score=fitness,
        )


# ---------------------------------------------------------------------------
# Genetic Operators
# ---------------------------------------------------------------------------


class GeneticOperators:
    """Selection, crossover, and mutation operators."""

    def __init__(
        self,
        *,
        gene_specs: list[GeneSpec],
        tournament_size: int = 3,
        crossover_alpha: float = 0.5,  # BLX-alpha blend parameter
        base_mutation_rate: float = 0.15,
        mutation_strength: float = 0.2,  # Fraction of gene range
        elite_count: int = 2,
    ) -> None:
        self.gene_specs = {g.name: g for g in gene_specs}
        self.tournament_size = tournament_size
        self.crossover_alpha = crossover_alpha
        self.base_mutation_rate = base_mutation_rate
        self.mutation_strength = mutation_strength
        self.elite_count = elite_count
        self._rng = np.random.default_rng()

    def tournament_select(self, population: list[Genome], k: int = 1) -> list[Genome]:
        """Tournament selection: pick `k` winners."""
        winners: list[Genome] = []
        for _ in range(k):
            contestants = self._rng.choice(len(population), size=min(self.tournament_size, len(population)), replace=False)
            best = max(contestants, key=lambda idx: population[idx].fitness)
            winners.append(population[int(best)])
        return winners

    def blx_crossover(self, parent_a: Genome, parent_b: Genome) -> Genome:
        """BLX-alpha crossover: blend float genes with exploration margin."""
        child_genes: dict[str, float] = {}
        alpha = self.crossover_alpha

        for gene_name in parent_a.genes:
            val_a = parent_a.genes[gene_name]
            val_b = parent_b.genes[gene_name]
            spec = self.gene_specs.get(gene_name)

            lo = min(val_a, val_b)
            hi = max(val_a, val_b)
            span = hi - lo
            blend_lo = lo - alpha * span
            blend_hi = hi + alpha * span

            if spec:
                blend_lo = max(blend_lo, spec.min_val)
                blend_hi = min(blend_hi, spec.max_val)

            child_val = float(self._rng.uniform(blend_lo, blend_hi))

            if spec and spec.dtype == "int":
                child_val = round(child_val)
            elif spec and spec.step:
                child_val = round(child_val / spec.step) * spec.step

            child_genes[gene_name] = child_val

        return Genome(
            genome_id=str(uuid.uuid4()),
            engine=parent_a.engine,
            asset_class=parent_a.asset_class,
            genes=child_genes,
            generation=max(parent_a.generation, parent_b.generation) + 1,
            lineage=[parent_a.genome_id, parent_b.genome_id],
        )

    def mutate(
        self,
        genome: Genome,
        *,
        rate_override: Optional[float] = None,
        target_genes: Optional[set[str]] = None,
    ) -> Genome:
        """Mutate genome genes.

        Parameters
        ----------
        rate_override : Override mutation rate (for micro-evolution)
        target_genes : If set, ONLY mutate these genes (for micro-evolution)
        """
        rate = rate_override if rate_override is not None else self.base_mutation_rate
        mutated = dict(genome.genes)
        mutations = 0

        for gene_name, val in mutated.items():
            if target_genes and gene_name not in target_genes:
                continue

            if self._rng.random() > rate:
                continue

            spec = self.gene_specs.get(gene_name)
            if spec is None:
                continue

            gene_range = spec.max_val - spec.min_val
            perturbation = self._rng.normal(0, self.mutation_strength * gene_range)
            new_val = val + perturbation

            # Clamp to bounds
            new_val = max(spec.min_val, min(spec.max_val, new_val))

            if spec.dtype == "int":
                new_val = round(new_val)
            elif spec.step:
                new_val = round(new_val / spec.step) * spec.step

            mutated[gene_name] = new_val
            mutations += 1

        child = genome.clone()
        child.genes = mutated
        child.genome_id = str(uuid.uuid4())
        return child

    def adaptive_mutation_rate(self, fitness: float, best_fitness: float) -> float:
        """Higher mutation for less fit individuals, lower for the best."""
        if best_fitness <= 0:
            return self.base_mutation_rate
        ratio = fitness / max(abs(best_fitness), 1e-12)
        # Less fit -> higher mutation (explore more), more fit -> lower (exploit)
        return self.base_mutation_rate * (2.0 - min(ratio, 1.5))


# ---------------------------------------------------------------------------
# Darwin Engine — Main Orchestrator
# ---------------------------------------------------------------------------


class DarwinEngine:
    """Genetic Algorithm optimizer for indicator parameter genomes.

    Maintains separate populations per (engine, asset_class) pair.
    Supports two evolution modes:
        1. full_evolve() — Standard GA cycle over the full population
        2. micro_evolve() — Targeted mutation from Reflector correction vectors

    Persistence: Populations are saved/loaded as JSON for crash recovery.
    """

    def __init__(
        self,
        *,
        gene_specs: Optional[list[GeneSpec]] = None,
        population_size: int = 30,
        elite_count: int = 3,
        tournament_size: int = 3,
        crossover_rate: float = 0.7,
        base_mutation_rate: float = 0.15,
        mutation_strength: float = 0.2,
        fitness_evaluator: Optional[FitnessEvaluator] = None,
        persist_dir: str = "runs/darwin",
    ) -> None:
        self._gene_specs = gene_specs or DEFAULT_GENE_SPECS
        self._pop_size = population_size
        self._crossover_rate = crossover_rate
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._evaluator = fitness_evaluator or FitnessEvaluator()
        self._operators = GeneticOperators(
            gene_specs=self._gene_specs,
            tournament_size=tournament_size,
            elite_count=elite_count,
            base_mutation_rate=base_mutation_rate,
            mutation_strength=mutation_strength,
        )
        self._rng = np.random.default_rng()

        # Populations indexed by "ENGINE:ASSET_CLASS"
        self._populations: dict[str, list[Genome]] = {}
        # Active genome per population (the one currently deployed)
        self._active: dict[str, Genome] = {}
        # Evolution history
        self._reports: list[EvolutionReport] = []

    # -------------------------------------------------------------------
    # Population management
    # -------------------------------------------------------------------

    def _pop_key(self, engine: str, asset_class: str) -> str:
        return f"{engine.upper()}:{asset_class.lower()}"

    def initialize_population(self, engine: str, asset_class: str) -> list[Genome]:
        """Create a random initial population for an engine/asset pair."""
        key = self._pop_key(engine, asset_class)
        population: list[Genome] = []

        for _ in range(self._pop_size):
            genes: dict[str, float] = {}
            for spec in self._gene_specs:
                val = float(self._rng.uniform(spec.min_val, spec.max_val))
                if spec.dtype == "int":
                    val = round(val)
                elif spec.step:
                    val = round(val / spec.step) * spec.step
                genes[spec.name] = val

            population.append(
                Genome(
                    genome_id=str(uuid.uuid4()),
                    engine=engine.upper(),
                    asset_class=asset_class.lower(),
                    genes=genes,
                    generation=0,
                )
            )

        self._populations[key] = population
        # Set the first genome as active by default
        self._active[key] = population[0]
        LOGGER.info("Darwin: initialized population key=%s size=%d", key, len(population))
        return population

    def get_active_genome(self, engine: str, asset_class: str) -> Optional[Genome]:
        """Get the currently deployed genome for an engine/asset pair."""
        key = self._pop_key(engine, asset_class)
        return self._active.get(key)

    def get_population(self, engine: str, asset_class: str) -> list[Genome]:
        """Get the full population for an engine/asset pair."""
        key = self._pop_key(engine, asset_class)
        return self._populations.get(key, [])

    # -------------------------------------------------------------------
    # Full Evolution — Standard GA cycle
    # -------------------------------------------------------------------

    def full_evolve(
        self,
        engine: str,
        asset_class: str,
        trade_returns: np.ndarray,
    ) -> EvolutionReport:
        """Run a full generation of genetic evolution.

        Steps:
        1. Evaluate fitness of all genomes in population
        2. Select elite (direct survival)
        3. Tournament selection + BLX crossover for offspring
        4. Adaptive mutation
        5. Replace population with new generation
        6. Update active genome to the best

        Parameters
        ----------
        engine : Engine name (TITAN, NAUTILUS, PHOENIX)
        asset_class : Asset class
        trade_returns : 1D array of per-trade returns for this engine/asset
        """
        key = self._pop_key(engine, asset_class)
        population = self._populations.get(key)

        if not population:
            population = self.initialize_population(engine, asset_class)

        # 1. Evaluate fitness
        for genome in population:
            result = self._evaluator.evaluate(genome, trade_returns)
            genome.fitness = result.fitness_score

        # Sort by fitness (best first)
        population.sort(key=lambda g: g.fitness, reverse=True)
        best_fitness = population[0].fitness
        mean_fitness = float(np.mean([g.fitness for g in population]))

        # 2. Elitism — top K survive
        elite_count = self._operators.elite_count
        elite = [g.clone() for g in population[:elite_count]]

        # 3. Generate offspring
        new_pop: list[Genome] = list(elite)
        crossovers = 0
        mutations = 0

        while len(new_pop) < self._pop_size:
            if self._rng.random() < self._crossover_rate and len(population) >= 2:
                parents = self._operators.tournament_select(population, k=2)
                child = self._operators.blx_crossover(parents[0], parents[1])
                crossovers += 1
            else:
                parent = self._operators.tournament_select(population, k=1)[0]
                child = parent.clone()

            # Adaptive mutation
            adaptive_rate = self._operators.adaptive_mutation_rate(child.fitness, best_fitness)
            child = self._operators.mutate(child, rate_override=adaptive_rate)
            mutations += 1

            new_pop.append(child)

        # 4. Replace population
        self._populations[key] = new_pop[:self._pop_size]

        # 5. Re-evaluate and set best as active
        for genome in self._populations[key]:
            result = self._evaluator.evaluate(genome, trade_returns)
            genome.fitness = result.fitness_score

        self._populations[key].sort(key=lambda g: g.fitness, reverse=True)
        self._active[key] = self._populations[key][0]

        generation = max(g.generation for g in self._populations[key])

        report = EvolutionReport(
            generation=generation,
            population_size=len(self._populations[key]),
            best_fitness=self._populations[key][0].fitness,
            mean_fitness=float(np.mean([g.fitness for g in self._populations[key]])),
            worst_fitness=self._populations[key][-1].fitness,
            best_genome_id=self._populations[key][0].genome_id,
            mutations_applied=mutations,
            crossovers_applied=crossovers,
            elite_preserved=elite_count,
            trigger="full",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._reports.append(report)

        LOGGER.info(
            "Darwin FULL evolution: key=%s gen=%d best=%.4f mean=%.4f",
            key, generation, report.best_fitness, report.mean_fitness,
        )

        return report

    # -------------------------------------------------------------------
    # Micro-Evolution — Targeted correction from Reflector
    # -------------------------------------------------------------------

    def micro_evolve(
        self,
        engine: str,
        asset_class: str,
        failure_mode: str,
        genome_deltas: dict[str, float],
        trade_returns: np.ndarray,
    ) -> EvolutionReport:
        """Run a targeted micro-evolution cycle.

        Unlike full_evolve, this:
        1. Only mutates genes related to the failure mode
        2. Uses the correction vector as a bias for the mutation direction
        3. Creates a small "challenger pool" from the active genome
        4. Promotes the challenger only if fitness improves

        Parameters
        ----------
        engine, asset_class : Scope
        failure_mode : From Reflector's FailureMode enum
        genome_deltas : Suggested adjustments from Reflector (e.g. {"sl_atr_mult": 0.3})
        trade_returns : Recent trade returns for fitness evaluation
        """
        key = self._pop_key(engine, asset_class)
        active = self._active.get(key)

        if active is None:
            self.initialize_population(engine, asset_class)
            active = self._active[key]

        # Identify target genes for this failure mode
        target_gene_names = set(FAILURE_MODE_GENE_MAP.get(failure_mode, []))
        # Also include any genes explicitly mentioned in deltas
        target_gene_names.update(genome_deltas.keys())

        if not target_gene_names:
            LOGGER.warning("Darwin micro-evolve: no target genes for failure_mode=%s", failure_mode)
            return self._empty_report(key, "micro:" + failure_mode)

        # Create challenger pool (5 variants of the active genome)
        challenger_count = 5
        challengers: list[Genome] = []

        for _ in range(challenger_count):
            challenger = active.clone()

            # Apply correction vector bias first
            for gene_name, delta in genome_deltas.items():
                if gene_name in challenger.genes:
                    spec = self._operators.gene_specs.get(gene_name)
                    new_val = challenger.genes[gene_name] + delta
                    if spec:
                        new_val = max(spec.min_val, min(spec.max_val, new_val))
                        if spec.dtype == "int":
                            new_val = round(new_val)
                    challenger.genes[gene_name] = new_val

            # Then apply random mutation ONLY to target genes
            challenger = self._operators.mutate(
                challenger,
                rate_override=0.8,  # High mutation rate for targeted genes
                target_genes=target_gene_names,
            )
            challenger.generation = active.generation + 1
            challengers.append(challenger)

        # Evaluate active genome and challengers
        active_fitness = self._evaluator.evaluate(active, trade_returns)
        active.fitness = active_fitness.fitness_score

        best_challenger = active
        best_fitness = active.fitness

        for challenger in challengers:
            result = self._evaluator.evaluate(challenger, trade_returns)
            challenger.fitness = result.fitness_score
            if challenger.fitness > best_fitness:
                best_challenger = challenger
                best_fitness = challenger.fitness

        # Promote if improved
        promoted = best_challenger is not active
        if promoted:
            self._active[key] = best_challenger
            # Also inject into population
            pop = self._populations.get(key, [])
            if pop:
                # Replace the worst genome
                pop.sort(key=lambda g: g.fitness)
                pop[0] = best_challenger
                self._populations[key] = pop

            LOGGER.info(
                "Darwin MICRO evolution promoted: key=%s failure=%s "
                "fitness %.4f -> %.4f",
                key, failure_mode, active.fitness, best_fitness,
            )
        else:
            LOGGER.info(
                "Darwin MICRO evolution: no improvement for key=%s failure=%s",
                key, failure_mode,
            )

        report = EvolutionReport(
            generation=active.generation + 1,
            population_size=challenger_count + 1,
            best_fitness=best_fitness,
            mean_fitness=float(np.mean([c.fitness for c in challengers] + [active.fitness])),
            worst_fitness=min(c.fitness for c in challengers),
            best_genome_id=best_challenger.genome_id,
            mutations_applied=challenger_count,
            crossovers_applied=0,
            elite_preserved=1 if not promoted else 0,
            trigger=f"micro:{failure_mode}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._reports.append(report)
        return report

    # -------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------

    def save(self, filename: Optional[str] = None) -> Path:
        """Save all populations and active genomes to JSON."""
        path = self._persist_dir / (filename or "darwin_state.json")
        state = {
            "populations": {},
            "active": {},
            "reports_count": len(self._reports),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        for key, pop in self._populations.items():
            state["populations"][key] = [self._genome_to_dict(g) for g in pop]

        for key, genome in self._active.items():
            state["active"][key] = self._genome_to_dict(genome)

        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        LOGGER.info("Darwin state saved to %s", path)
        return path

    def load(self, filename: Optional[str] = None) -> None:
        """Load populations and active genomes from JSON."""
        path = self._persist_dir / (filename or "darwin_state.json")
        if not path.exists():
            LOGGER.warning("Darwin state file not found: %s", path)
            return

        state = json.loads(path.read_text(encoding="utf-8"))

        for key, pop_data in state.get("populations", {}).items():
            self._populations[key] = [self._dict_to_genome(d) for d in pop_data]

        for key, genome_data in state.get("active", {}).items():
            self._active[key] = self._dict_to_genome(genome_data)

        LOGGER.info(
            "Darwin state loaded: %d populations, %d active genomes",
            len(self._populations),
            len(self._active),
        )

    def get_evolution_history(self) -> list[EvolutionReport]:
        """Return all evolution reports from this session."""
        return list(self._reports)

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _empty_report(self, key: str, trigger: str) -> EvolutionReport:
        return EvolutionReport(
            generation=0,
            population_size=0,
            best_fitness=0.0,
            mean_fitness=0.0,
            worst_fitness=0.0,
            best_genome_id="",
            mutations_applied=0,
            crossovers_applied=0,
            elite_preserved=0,
            trigger=trigger,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _genome_to_dict(genome: Genome) -> dict[str, Any]:
        return {
            "genome_id": genome.genome_id,
            "engine": genome.engine,
            "asset_class": genome.asset_class,
            "genes": genome.genes,
            "fitness": genome.fitness,
            "generation": genome.generation,
            "lineage": genome.lineage,
            "created_at": genome.created_at,
        }

    @staticmethod
    def _dict_to_genome(data: dict[str, Any]) -> Genome:
        return Genome(
            genome_id=str(data["genome_id"]),
            engine=str(data["engine"]),
            asset_class=str(data["asset_class"]),
            genes={str(k): float(v) for k, v in data["genes"].items()},
            fitness=float(data.get("fitness", 0.0)),
            generation=int(data.get("generation", 0)),
            lineage=list(data.get("lineage", [])),
            created_at=str(data.get("created_at", "")),
        )
