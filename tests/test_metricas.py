"""Verifica definições e o limiar ótimo contra contagens por força bruta."""
import itertools
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from metricas import analyze, minimum_deadline, ns, windows


class MetricsTest(unittest.TestCase):
    def test_equal_deadline_and_no_losses(self):
        r = analyze([100, 200, 200], 200, (2,))
        self.assertEqual(r["perdas"], 0)
        self.assertIsNone(r["skip_factor"])
        self.assertEqual(r["janelas"][2]["m"], 2)

    def test_single_loss(self):
        r = analyze([1, 3, 1], 2, (2,))
        self.assertEqual(r["perdas_isoladas"], 1)
        self.assertIsNone(r["skip_factor"])

    def test_runs_gaps_and_last_window(self):
        r = analyze([1, 3, 3, 1, 3, 1, 3, 3, 3], 2, (3,))
        self.assertEqual(r["ativacoes_perdidas"], [2, 3, 5, 7, 8, 9])
        self.assertEqual(r["distancias"], [1, 2, 2, 1, 1])
        self.assertEqual(r["skip_factor"], 1)
        self.assertEqual(r["quantidade_rajadas"], 2)
        self.assertEqual(r["maior_rajada"], 3)
        self.assertEqual(r["perdas_isoladas"], 1)
        self.assertEqual(r["janelas"][3]["primeira_pior_janela_inicio"], 7)
        self.assertEqual(r["janelas"][3]["m"], 0)

    def test_hwm_99_is_trimmed_maximum(self):
        r = analyze(list(range(1, 201)), 200, (20,))
        self.assertEqual(r["hwm_99_descartadas"], 2)
        self.assertEqual(r["hwm_99_us"], 0.198)
        self.assertEqual(ns("32440.800"), 32440800)

    def test_all_short_binary_sequences(self):
        for losses in itertools.product((0, 1), repeat=6):
            for k in range(1, 7):
                expected = [sum(losses[i:i + k]) for i in range(7 - k)]
                self.assertEqual(windows(losses, k)["contagens"], expected)

    def test_minimum_deadline_against_exhaustive_search(self):
        generator = random.Random(2026)
        for _ in range(50):
            times = [generator.randrange(1, 10) for _ in range(12)]
            for k in (1, 3, 5):
                for m in range(k + 1):
                    expected = next(d for d in range(10) if all(
                        sum(t <= d for t in times[i:i + k]) >= m
                        for i in range(len(times) - k + 1)))
                    self.assertEqual(minimum_deadline(times, m, k), expected)


if __name__ == "__main__":
    unittest.main()
