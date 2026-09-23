from pathlib import Path
import zipfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "docs" / "evidence" / "release-fixture" / "synthetic-finops-assessment.pptx"


class PresentationEvidenceTests(unittest.TestCase):
    def test_release_deck_contains_the_expected_slides_and_titles(self) -> None:
        with zipfile.ZipFile(DECK) as package:
            slide_parts = sorted(
                name for name in package.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            )
            content = "\n".join(package.read(name).decode("utf-8") for name in slide_parts)

        self.assertEqual(len(slide_parts), 4)
        for title in (
            "Cloud data FinOps assessment",
            "Scope and access boundary",
            "Synthetic findings",
            "Verification and next scope",
        ):
            self.assertIn(title, content)


if __name__ == "__main__":
    unittest.main()
