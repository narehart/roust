import unittest
from e58_units import source_units


class Units(unittest.TestCase):
    def test_edit_above_functions_preserves_function_content(self):
        before = "use a;\n\nfn one() {\n work();\n}\n\nfn two() {\n other();\n}\n"
        after = "use b;\n" + before
        a = {s for _, _, s in source_units("x.rs", before)}
        b = {s for _, _, s in source_units("x.rs", after)}
        self.assertIn("fn one() {\n work();\n}\n", a & b)
        self.assertIn("fn two() {\n other();\n}\n", a & b)

    def test_units_cover_nonempty_source_lines_including_gaps(self):
        source = "use a;\n\nfn outer() {\n fn inner() {}\n}\n\nconst X: i32 = 1;\n"
        units = source_units("x.rs", source)
        covered = {i for a, b, _ in units for i in range(a, b + 1)}
        self.assertTrue({i for i, line in enumerate(source.splitlines(), 1) if line.strip()} <= covered)
        self.assertEqual(len(units), 3)


if __name__ == "__main__":
    unittest.main()
