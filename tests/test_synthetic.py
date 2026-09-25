import unittest

from cloud_data_finops.contracts import validate_specification
from cloud_data_finops.policies import RULES, evaluate
from cloud_data_finops.synthetic import DEFAULT_SEED, generate_assessment, render_assessment
from cloud_data_finops.workflow import collect_fixture_telemetry
from tests.helpers import FIXTURE


class SyntheticGeneratorTests(unittest.TestCase):
    def test_same_seed_gives_identical_output(self) -> None:
        self.assertEqual(render_assessment(7), render_assessment(7))

    def test_checked_in_fixture_is_the_default_seed_output(self) -> None:
        self.assertEqual(FIXTURE.read_bytes(), render_assessment(DEFAULT_SEED).encode("utf-8"))

    def test_different_seeds_change_only_background_records(self) -> None:
        first, second = generate_assessment(1), generate_assessment(2)
        self.assertNotEqual(first["gcp"]["jobs"], second["gcp"]["jobs"])
        self.assertEqual(first["gcp"]["jobs"][:5], second["gcp"]["jobs"][:5])

    def test_generated_specifications_are_valid_and_labelled_synthetic(self) -> None:
        for seed in (1, 2, 3, DEFAULT_SEED):
            specification = generate_assessment(seed)
            validate_specification(specification)
            self.assertEqual(specification["scope"]["data_origin"], "synthetic")
            self.assertEqual(specification["scope"]["generator"]["seed"], seed)

    def test_planted_scenarios_exercise_every_rule_for_any_seed(self) -> None:
        for seed in range(10):
            findings = evaluate(collect_fixture_telemetry(generate_assessment(seed)))
            self.assertEqual({finding["rule_id"] for finding in findings}, set(RULES), seed)
            self.assertEqual(len(findings), 11, seed)

    def test_generator_output_is_detached_from_module_state(self) -> None:
        first = generate_assessment()
        first["gcp"]["jobs"].clear()
        self.assertTrue(generate_assessment()["gcp"]["jobs"])


if __name__ == "__main__":
    unittest.main()
