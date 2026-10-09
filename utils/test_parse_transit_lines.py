import unittest

from parse_transit_lines import COLUMNS, parse_transit_text


class TransitParserTests(unittest.TestCase):
    def test_directionality(self):
        for oneway, expected in (
            ("T", [(2412, 2413), (2413, 2415)]),
            ("F", [(2412, 2413), (2413, 2415), (2415, 2413), (2413, 2412)]),
            ("Y", [(2412, 2413), (2413, 2415)]),
            ("N", [(2412, 2413), (2413, 2415), (2415, 2413), (2413, 2412)]),
        ):
            with self.subTest(oneway=oneway):
                dataframe = parse_transit_text(
                    f'LINE NAME="example", MODE=30, ONEWAY={oneway}, '
                    "N=2412, 2413, 2415"
                )
                self.assertEqual(list(dataframe.columns), COLUMNS)
                self.assertEqual(list(zip(dataframe.A, dataframe.B)), expected)
                self.assertTrue((dataframe["LINE NAME"] == "example").all())
                self.assertTrue((dataframe.MODE == 30).all())
                self.assertTrue((dataframe.ONEWAY == oneway).all())

    def test_comments_attributes_and_multiple_lines(self):
        dataframe = parse_transit_text('''
            ; LINE NAME="ignored", MODE=99, ONEWAY=T, N=9, 8
            LINE NAME="first", LONGNAME="Name, with; punctuation",
                FREQ[1]=30.5, MODE=30, ONEWAY=F,
                N=1, ACCESS=1, -2, ; 999 must not be a node
                N=-3, ACCESS=2, 4
            LINE NAME="second", MODE=31, ONEWAY=T, N=5, 6
        ''')
        self.assertEqual(
            list(zip(dataframe.A, dataframe.B)),
            [(1, 2), (2, 3), (3, 4), (4, 3), (3, 2), (2, 1), (5, 6)],
        )
        self.assertEqual(dataframe.iloc[-1]["LINE NAME"], "second")
        self.assertEqual(dataframe.iloc[-1]["MODE"], 31)

    def test_repeated_traversals_are_preserved(self):
        dataframe = parse_transit_text(
            'LINE NAME="loop", MODE=30, ONEWAY=T, N=1, 2, 1, 2'
        )
        self.assertEqual(list(zip(dataframe.A, dataframe.B)), [(1, 2), (2, 1), (1, 2)])

    def test_invalid_attributes_raise(self):
        for text in (
            'LINE NAME="bad", ONEWAY=T, N=1, 2',
            'LINE NAME="bad", MODE=30, ONEWAY=X, N=1, 2',
            'LINE NAME="bad", MODE=30, ONEWAY=T',
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_transit_text(text)

    def test_missing_oneway_warns_and_uses_configurable_default(self):
        text = 'LINE NAME="missing", MODE=21, N=1, 2'
        with self.assertWarnsRegex(UserWarning, "missing ONEWAY; using F"):
            dataframe = parse_transit_text(text)
        self.assertEqual(list(zip(dataframe.A, dataframe.B)), [(1, 2), (2, 1)])
        self.assertTrue((dataframe.ONEWAY == "F").all())
        with self.assertWarnsRegex(UserWarning, "missing ONEWAY; using T"):
            dataframe = parse_transit_text(text, default_oneway="T")
        self.assertEqual(list(zip(dataframe.A, dataframe.B)), [(1, 2)])

    def test_sources_apply_to_multiple_lines(self):
        dataframe = parse_transit_text(r'''
            LINE NAME="no_source", MODE=30, ONEWAY=T, N=1, 2
            ;######################### From: M:\Model One\trn\first.tpl
            LINE NAME="first", MODE=30, ONEWAY=F, N=2, 3
            LINE NAME="second", MODE=31, ONEWAY=T, N=3, 4
            ;######################### From: M:\Model One\trn\second.tpl
            LINE NAME="third", MODE=32, ONEWAY=T, N=4, 5
        ''')
        self.assertEqual(dataframe["source"].tolist(), [
            "",
            r"M:\Model One\trn\first.tpl",
            r"M:\Model One\trn\first.tpl",
            r"M:\Model One\trn\first.tpl",
            r"M:\Model One\trn\second.tpl",
        ])
        self.assertEqual(str(dataframe["source"].dtype), "string")

    def test_empty_input(self):
        dataframe = parse_transit_text("; only a comment")
        self.assertTrue(dataframe.empty)
        self.assertEqual(list(dataframe.columns), COLUMNS)


if __name__ == "__main__":
    unittest.main()