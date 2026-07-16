import unittest

from polyglot_quiz.models import TargetLanguage
from polyglot_quiz.profiles import PROFILES, get_profile


class ProfileTests(unittest.TestCase):
    def test_all_target_languages_have_profiles(self) -> None:
        self.assertEqual(set(PROFILES), set(TargetLanguage))

    def test_cefr_and_jlpt_boundaries(self) -> None:
        self.assertEqual(get_profile(TargetLanguage.ENGLISH, "c2").level_system, "CEFR")
        self.assertEqual(get_profile(TargetLanguage.JAPANESE, "n1").level_system, "JLPT")
        self.assertEqual(get_profile(TargetLanguage.SPANISH, "a1").level_system, "CEFR")
        with self.assertRaises(ValueError):
            get_profile(TargetLanguage.JAPANESE, "B1")


if __name__ == "__main__":
    unittest.main()
