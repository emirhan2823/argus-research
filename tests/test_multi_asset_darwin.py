import unittest
import os
import shutil
import json
from src.core.darwin_engine import DarwinEngine, Genome

class TestMultiAssetDarwin(unittest.TestCase):

    def setUp(self):
        self.test_dir = "tests/darwin_test"
        os.makedirs(self.test_dir, exist_ok=True)
        self.champions_file = os.path.join(self.test_dir, "champs.json")

        self.engine = DarwinEngine(
            population_size=10,
            champions_file=self.champions_file
        )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_multi_asset_registration(self):
        # Register BTC
        self.engine.register_asset("BTC/USDT")
        self.assertIn("BTC/USDT", self.engine.populations)
        self.assertEqual(len(self.engine.populations["BTC/USDT"]), 10)

        # Register XAU
        self.engine.register_asset("XAU/USDT")
        self.assertIn("XAU/USDT", self.engine.populations)

        # Independent Evolution Check
        # Set fitness for BTC pop[0]
        self.engine.populations["BTC/USDT"][0].fitness = 100.0

        # Verify XAU pop[0] is unaffected
        self.assertEqual(self.engine.populations["XAU/USDT"][0].fitness, 0.0)

    def test_persistence(self):
        self.engine.register_asset("BTC/USDT")

        # Create a "Champion"
        champ = self.engine.populations["BTC/USDT"][0]
        champ.fitness = 999.0
        champ.genes["rsi_period"] = 123.0 # Unique marker

        # Save
        self.engine.save_champions()
        self.assertTrue(os.path.exists(self.champions_file))

        # New Engine Instance
        new_engine = DarwinEngine(champions_file=self.champions_file)
        new_engine.load_champions()

        # Verify Load
        self.assertIn("BTC/USDT", new_engine.populations)
        loaded_champ = new_engine.populations["BTC/USDT"][0]

        self.assertEqual(loaded_champ.fitness, 999.0)
        self.assertEqual(loaded_champ.genes["rsi_period"], 123.0)

    def test_dynamic_genes(self):
        self.engine.register_asset("TEST")
        genome = self.engine.populations["TEST"][0]

        # Check for new genes
        self.assertIn("use_rsi", genome.genes)
        self.assertIn("use_bollinger", genome.genes)
        self.assertIn("bb_std", genome.genes)

if __name__ == '__main__':
    unittest.main()
