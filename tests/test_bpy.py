
import unittest


class TestBpy(unittest.TestCase):

    def test_import(self):
        """Sanity check to importing bpy"""
        import bpy      # type: ignore # noqa
