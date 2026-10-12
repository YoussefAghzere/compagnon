import unittest
from compagnon.core import TeamsWindow


class DetectionTests(unittest.TestCase):
    def test_default_meeting_title(self):
        self.assertTrue(TeamsWindow('Réunion | Microsoft Teams').matches())
        self.assertTrue(TeamsWindow('CALL | Microsoft Teams').matches())

    def test_process_identifies_teams_without_brand_in_title(self):
        self.assertTrue(TeamsWindow('Réunion de projet', r'C:\Apps\ms-teams.exe').matches())

    def test_named_call_needs_explicit_fragment(self):
        window = TeamsWindow('Youssef Aghzere', r'C:\Apps\ms-teams.exe')
        self.assertFalse(window.matches())
        self.assertTrue(window.matches('  youssef  '))

    def test_main_window_does_not_trigger_default_capture(self):
        self.assertFalse(TeamsWindow('Chat | Microsoft Teams').matches())
        self.assertFalse(TeamsWindow('Microsoft Teams').matches())

    def test_custom_fragment_replaces_default_keywords(self):
        self.assertFalse(TeamsWindow('Meeting | Microsoft Teams').matches('Youssef'))
        self.assertTrue(TeamsWindow('Youssef | Microsoft Teams').matches('Youssef'))

    def test_unrelated_process_and_title_do_not_trigger_capture(self):
        self.assertFalse(TeamsWindow('Youssef', r'C:\Apps\notepad.exe').matches('Youssef'))
        self.assertFalse(TeamsWindow('Meeting', r'C:\Apps\notepad.exe').matches())
