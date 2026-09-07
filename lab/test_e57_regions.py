"""Meaningful source/metric integrity checks, without loading a model."""
import unittest

from e57_regions import definitions, pack, render


class RegionIntegrity(unittest.TestCase):
    def test_many_large_line_numbers_and_reused_parser(self):
        source = "\n" * 300 + "\n".join(f"fn f{i}() {{\n work();\n}}" for i in range(200))
        for _ in range(4):
            spans = definitions("x.rs", source)
            self.assertEqual(len(spans), 200)
            self.assertEqual(min(a for a, _ in spans), 301)
            self.assertEqual(max(b for _, b in spans), 900)

    def test_rust_attributes_and_cpp_templates_are_included(self):
        self.assertEqual(definitions("x.rs", "#[inline]\nfn foo() {\n  work();\n}\n"), [(1, 4)])
        self.assertEqual(definitions("x.cpp", "template<class T>\nT foo(T x) {\n return x;\n}\n"), [(1, 4)])

    def test_budget_preserves_navigation_and_exact_source(self):
        corpus = {"a.py": "def one():\n    return 1\n\ndef two():\n    return 2\n",
                  "b.py": "# secondary file\nvalue = 42\n"}
        regions, bundle, stats = pack(corpus, {"a.py": [(1, 2)], "b.py": [(2, 2)]},
                                      [(0.9, "a.py", 4, 4)], budget=60)
        self.assertEqual(set(regions), {"a.py", "b.py"})
        self.assertTrue(any(a <= 4 and b >= 5 for a, b in regions["a.py"]))
        self.assertLessEqual(stats["bundle_tokens"], 60)
        self.assertEqual(bundle, render(regions, {p: s.splitlines() for p, s in corpus.items()}))

    def test_impossible_navigation_budget_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "navigation seats"):
            pack({"a.py": "value = 42\n"}, {"a.py": [(1, 1)]}, [], budget=1)


if __name__ == "__main__":
    unittest.main()
