import numpy as np
import random
import concurrent.futures
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Callable, Optional, Union
import copy

@dataclass
class Genome:
    """
    Represents a trading strategy's parameters.
    """
    id: str
    genes: Dict[str, float]
    fitness: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def random(cls, gene_ranges: Dict[str, tuple]) -> 'Genome':
        """
        Creates a random genome based on constraints.
        """
        genes = {}
        for name, (min_val, max_val) in gene_ranges.items():
            if isinstance(min_val, int):
                genes[name] = random.randint(min_val, max_val)
            else:
                genes[name] = random.uniform(min_val, max_val)
        return cls(id=f"gen_{random.randint(0, 1000000)}", genes=genes)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class DarwinEngine:
    """
    Evolutionary Optimization Engine.
    Supports Multi-Asset Populations (Islands).
    """
    def __init__(self,
                 population_size: int = 64,
                 mutation_rate: float = 0.1,
                 crossover_rate: float = 0.5,
                 max_drawdown_limit: float = 0.15,
                 champions_file: str = "data/champions.json"):
        self.pop_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.max_dd_limit = max_drawdown_limit
        self.champions_file = champions_file

        # Default Gene Config (Strategy Parameters)
        # Expanded for Dynamic Indicator Search
        self.gene_ranges = {
            'ema_short': (10, 100),
            'ema_long': (100, 300),
            'rsi_period': (7, 30),
            'rsi_upper': (60, 90),
            'rsi_lower': (10, 40),
            'sl_atr_mult': (1.0, 5.0),
            'tp_atr_mult': (1.5, 10.0),
            # New Genes
            'use_rsi': (0, 1),       # Binary: 0 or 1
            'use_macd': (0, 1),      # Binary
            'use_bollinger': (0, 1), # Binary
            'bb_period': (10, 50),
            'bb_std': (1.5, 3.0)
        }

        # Multi-Asset Populations: {symbol: List[Genome]}
        self.populations: Dict[str, List[Genome]] = {}
        self.generations: Dict[str, int] = {}

    def register_asset(self, symbol: str):
        """
        Initializes a population for a specific asset.
        """
        if symbol not in self.populations:
            self.populations[symbol] = [Genome.random(self.gene_ranges) for _ in range(self.pop_size)]
            self.generations[symbol] = 0
            print(f"Registered asset: {symbol} with random population.")

    def evaluate_population(self, backtest_func: Callable, specific_symbol: str = None):
        """
        Runs backtests in parallel.
        If specific_symbol is provided, only evaluates that asset.
        Otherwise evaluates ALL assets.
        backtest_func: Function that takes (Genome, Symbol) and returns metrics dict.
        """
        tasks = []

        target_symbols = [specific_symbol] if specific_symbol else list(self.populations.keys())

        for sym in target_symbols:
            if sym not in self.populations: continue
            for genome in self.populations[sym]:
                tasks.append((genome, sym))

        with concurrent.futures.ProcessPoolExecutor() as executor:
            # Map (genome, symbol) to futures
            # Note: backtest_func needs to handle the tuple or we wrap it
            # Ensure backtest_func is picklable (top-level function)
            future_to_genome = {
                executor.submit(backtest_func, genome, symbol): (genome, symbol)
                for genome, symbol in tasks
            }

            for future in concurrent.futures.as_completed(future_to_genome):
                genome, symbol = future_to_genome[future]
                try:
                    metrics = future.result()
                    genome.metrics = metrics
                    genome.fitness = self.calculate_fitness(metrics)
                except Exception as e:
                    print(f"Backtest Error for {genome.id} on {symbol}: {e}")
                    genome.fitness = 0.0

    def calculate_fitness(self, metrics: Dict[str, float]) -> float:
        """
        Multi-Objective Fitness Function.
        """
        sharpe = metrics.get('sharpe', 0.0)
        cagr = metrics.get('cagr', 0.0)
        max_dd = metrics.get('max_drawdown', 1.0)

        # Survival Hard Constraint
        if max_dd > self.max_dd_limit:
            return 0.0

        # Weighted Score
        # W1 * Sharpe + W2 * CAGR - W3 * DD
        score = (2.0 * sharpe) + (1.0 * cagr) - (5.0 * max_dd)

        return max(0.0, score) # No negative fitness

    def evolve(self, specific_symbol: str = None, adjustment_vector: Dict[str, float] = None, reflector_callback: Callable = None):
        """
        Creates the next generation for each asset's population.
        adjustment_vector: Optional dict to bias mutations (e.g., from Reflector).
        reflector_callback: Optional function(genome, symbol) to trigger if fitness is 0 (Survival Failure).
        """
        target_symbols = [specific_symbol] if specific_symbol else list(self.populations.keys())

        for sym in target_symbols:
            if sym not in self.populations: continue

            pop = self.populations[sym]
            sorted_pop = sorted(pop, key=lambda x: x.fitness, reverse=True)

            # Autopsy Trigger: Check for Survival Failures (Fitness = 0)
            if reflector_callback:
                failures = [g for g in pop if g.fitness == 0.0]
                if failures:
                    print(f"[{sym}] {len(failures)} Genomes Failed Survival. Triggering Autopsy...")
                    # Analyze the worst failure (or random one) to get adjustment
                    # Ideally we analyze all, but for speed let's just do one if adjustment_vector is missing
                    if not adjustment_vector:
                        worst_failure = failures[0] # Since 0 is equal, pick first
                        new_adj = reflector_callback(worst_failure, sym)
                        if new_adj:
                            print(f"[{sym}] Autopsy generated adjustment: {new_adj}")
                            adjustment_vector = new_adj

            # Elitism: Keep top 2
            next_gen = sorted_pop[:2]

            while len(next_gen) < self.pop_size:
                parent_a = self._tournament_selection(pop)
                parent_b = self._tournament_selection(pop)

                # Pass current generation count for ID generation
                current_gen = self.generations[sym]
                child = self._crossover(parent_a, parent_b, current_gen)
                self._mutate(child, adjustment_vector)

                next_gen.append(child)

            self.populations[sym] = next_gen
            self.generations[sym] += 1
            print(f"[{sym}] Evolved to Generation {self.generations[sym]}. Best Fitness: {sorted_pop[0].fitness:.4f}")

        # Auto-save champions after evolution
        self.save_champions()

    def _tournament_selection(self, pop: List[Genome], k: int = 4) -> Genome:
        """
        Selects the best from k random individuals.
        """
        tournament = random.sample(pop, k)
        return max(tournament, key=lambda x: x.fitness)

    def _crossover(self, parent_a: Genome, parent_b: Genome, generation_index: int) -> Genome:
        """
        Uniform Crossover.
        """
        child_genes = {}
        for gene in self.gene_ranges:
            if random.random() < 0.5:
                child_genes[gene] = parent_a.genes[gene]
            else:
                child_genes[gene] = parent_b.genes[gene]

        # Use provided generation index for ID
        return Genome(id=f"gen_{generation_index}_child_{random.randint(0, 100000)}", genes=child_genes)

    def _mutate(self, genome: Genome, adjustment_vector: Dict[str, float] = None):
        """
        Gaussian Jitter Mutation.
        adjustment_vector: Bias to apply to specific genes.
        """
        for gene, (min_val, max_val) in self.gene_ranges.items():

            # 1. Apply Adjustment Vector (Directed Mutation)
            if adjustment_vector and gene in adjustment_vector:
                current_val = genome.genes[gene]
                bias = adjustment_vector[gene]
                new_val = current_val + bias
                # Clamp
                new_val = max(min_val, min(new_val, max_val))
                genome.genes[gene] = new_val
                # Skip random mutation if adjusted explicitly? Or allow both?
                # Let's allow random mutation on top to explore around the bias.

            # 2. Random Mutation
            if random.random() < self.mutation_rate:
                current_val = genome.genes[gene]

                # Apply Jitter
                if isinstance(min_val, int):
                    # For binary flags (0, 1), flip it
                    if min_val == 0 and max_val == 1:
                        new_val = 1 - int(current_val)
                    else:
                        jitter = random.randint(-2, 2)
                        new_val = int(current_val + jitter)
                else:
                    jitter = random.gauss(0, (max_val - min_val) * 0.05) # 5% StdDev
                    new_val = current_val + jitter

                # Clamp
                new_val = max(min_val, min(new_val, max_val))
                genome.genes[gene] = new_val

    def save_champions(self):
        """
        Saves the best genome for each asset to a JSON file.
        """
        champions = {}
        for sym, pop in self.populations.items():
            if not pop: continue
            best = max(pop, key=lambda x: x.fitness)
            champions[sym] = best.to_dict()

        try:
            os.makedirs(os.path.dirname(self.champions_file), exist_ok=True)
            with open(self.champions_file, 'w') as f:
                json.dump(champions, f, indent=4)
        except Exception as e:
            print(f"Failed to save champions: {e}")

    def load_champions(self):
        """
        Loads champions from file and injects them into populations.
        """
        if not os.path.exists(self.champions_file):
            return

        try:
            with open(self.champions_file, 'r') as f:
                data = json.load(f)

            for sym, genome_dict in data.items():
                champion = Genome.from_dict(genome_dict)
                self.register_asset(sym) # Ensure population exists
                # Inject champion at index 0 (Elitism)
                self.populations[sym][0] = champion
                print(f"[{sym}] Loaded Champion: {champion.id} (Fitness: {champion.fitness:.2f})")
        except Exception as e:
            print(f"Failed to load champions: {e}")
