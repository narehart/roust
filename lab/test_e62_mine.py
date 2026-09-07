import unittest
from e62_mine import commits, rank


class AncillarySignals(unittest.TestCase):
    def test_nul_history_framing_preserves_paths_and_commits(self):
        raw = b"\0" + b"a" * 40 + b"\0\0\nsource.rs\0notes with spaces.md\0"
        raw += b"\0" + b"b" * 40 + b"\0\0\n\nleading-newline.md\0"
        self.assertEqual(commits(raw), [{"source.rs", "notes with spaces.md"}, {"\nleading-newline.md"}])

    def test_bulk_commits_and_unrelated_paths_do_not_create_edges(self):
        history = [{"source.rs", "target.md"}, {"other.rs", "unrelated.md"},
                   {"source.rs", "bulk.md"} | {f"p{i}" for i in range(50)}]
        result = rank("target", {"source.rs"}, {"target.md", "unrelated.md", "bulk.md"}, history)
        self.assertEqual(result["history"], ["target.md"])
        self.assertEqual(result["path-history-rrf"], ["target.md"])


if __name__ == "__main__":
    unittest.main()
