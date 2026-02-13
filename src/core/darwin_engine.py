import numpy as np
import random
import concurrent.futures
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Optional
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

class DarwinEngine:
    """
    Evolutionary Optimization Engine.
    """
    def __init__(self,
                 population_size: int = 64,
                 mutation_rate: float = 0.1,
                 crossover_rate: float = 0.5,
                 max_drawdown_limit: float = 0.15):
        self.pop_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.max_dd_limit = max_drawdown_limit

        # Default Gene Config (Strategy Parameters)
        self.gene_ranges = {
            'ema_short': (10, 100),
            'ema_long': (100, 300),
            'rsi_period': (7, 21),
            'rsi_upper': (60, 90),
            'rsi_lower': (10, 40),
            'sl_atr_mult': (1.0, 5.0),
            'tp_atr_mult': (1.5, 10.0)
        }

        self.population: List[Genome] = []
        self.generation = 0

    def initialize_population(self):
        """
        Generates initial random population.
        """
        self.population = [Genome.random(self.gene_ranges) for _ in range(self.pop_size)]

    def evaluate_population(self, backtest_func: Callable):
        """
        Runs backtests in parallel.
        backtest_func: Function that takes a Genome and returns metrics dict.
        """
        with concurrent.futures.ProcessPoolExecutor() as executor:
            # Map genomes to futures
            future_to_genome = {executor.submit(backtest_func, genome): genome for genome in self.population}

            for future in concurrent.futures.as_completed(future_to_genome):
                genome = future_to_genome[future]
                try:
                    metrics = future.result()
                    genome.metrics = metrics
                    genome.fitness = self.calculate_fitness(metrics)
                except Exception as e:
                    print(f"Backtest Error for {genome.id}: {e}")
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

    def evolve(self):
        """
        Creates the next generation.
        """
        sorted_pop = sorted(self.population, key=lambda x: x.fitness, reverse=True)

        # Elitism: Keep top 2
        next_gen = sorted_pop[:2]

        while len(next_gen) < self.pop_size:
            parent_a = self._tournament_selection(self.population)
            parent_b = self._tournament_selection(self.population)

            child = self._crossover(parent_a, parent_b)
            self._mutate(child)

            next_gen.append(child)

        self.population = next_gen
        self.generation += 1

    def _tournament_selection(self, pop: List[Genome], k: int = 4) -> Genome:
        """
        Selects the best from k random individuals.
        """
        tournament = random.sample(pop, k)
        return max(tournament, key=lambda x: x.fitness)

    def _crossover(self, parent_a: Genome, parent_b: Genome) -> Genome:
        """
        Uniform Crossover.
        """
        child_genes = {}
        for gene in self.gene_ranges:
            if random.random() < 0.5:
                child_genes[gene] = parent_a.genes[gene]
            else:
                child_genes[gene] = parent_b.genes[gene]

        return Genome(id=f"gen_{self.generation}_child_{random.randint(0, 100000)}", genes=child_genes)

    def _mutate(self, genome: Genome):
        """
        Gaussian Jitter Mutation.
        """
        for gene, (min_val, max_val) in self.gene_ranges.items():
            if random.random() < self.mutation_rate:
                current_val = genome.genes[gene]

                # Apply Jitter
                if isinstance(min_val, int):
                    jitter = random.randint(-2, 2)
                    new_val = int(current_val + jitter)
                else:
                    jitter = random.gauss(0, (max_val - min_val) * 0.05) # 5% StdDev
                    new_val = current_val + jitter

                # Clamp
                new_val = max(min_val, min(new_val, max_val))
                genome.genes[gene] = new_val
