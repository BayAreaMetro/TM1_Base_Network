"""Convert Cube transit LINE records into a pandas DataFrame of directed links."""

import argparse
from pathlib import Path
import re
import shlex
import warnings

import pandas as pd


DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "trn" / "transitLines.lin"
COLUMNS = ["LINE NAME", "MODE", "ONEWAY", "A", "B", "source"]


def parse_transit_text(text: str, default_oneway: str = "F") -> pd.DataFrame:
    """Parse LINE records, treating negative node IDs as non-stop nodes.

    Endpoints use absolute node IDs. Repeated traversals are retained; reverse
    traversals for two-way lines follow all forward traversals in route order.
    Missing ONEWAY uses default_oneway with a warning; Y/N also mean T/F.
    Source paths come from From headers; records before any header use empty text.
    """
    default_oneway = default_oneway.upper()
    if default_oneway not in {"T", "F", "Y", "N"}:
        raise ValueError(f"Invalid default ONEWAY: {default_oneway!r}")
    sections = re.split(r"^[ \t]*;#+[ \t]*From:[ \t]*([^\r\n]*)", text, flags=re.MULTILINE)
    tokens = []
    for section_index in range(0, len(sections), 2):
        source = sections[section_index - 1].strip() if section_index else ""
        lexer = shlex.shlex(sections[section_index], posix=True, punctuation_chars="=")
        lexer.whitespace += ","
        lexer.whitespace_split = True
        lexer.commenters = ";"
        tokens.extend((token, source) for token in lexer)
    rows = []
    attributes: dict[str, str] = {}
    nodes: list[int] = []
    in_line = False
    in_nodes = False
    line_source = ""

    def append_links() -> None:
        if not in_line:
            return
        missing = {"NAME", "MODE"} - attributes.keys()
        if missing:
            raise ValueError(f"LINE is missing attributes: {sorted(missing)}")
        name = attributes["NAME"]
        mode = int(attributes["MODE"])
        if "ONEWAY" not in attributes:
            warnings.warn(
                f"LINE {name!r}: missing ONEWAY; using {default_oneway}",
                stacklevel=2,
            )
        oneway = attributes.get("ONEWAY", default_oneway).upper()
        if oneway not in {"T", "F", "Y", "N"}:
            raise ValueError(f"LINE {name!r}: invalid ONEWAY {oneway!r}")
        if not nodes:
            raise ValueError(f"LINE {name!r}: missing N node list")
        links = list(zip(nodes, nodes[1:]))
        if oneway in {"F", "N"}:
            links += [(end, start) for start, end in reversed(links)]
        rows.extend((name, mode, oneway, start, end, line_source) for start, end in links)

    position = 0
    while position < len(tokens):
        token, source = tokens[position]
        if token.upper() == "LINE":
            append_links()
            attributes = {}
            nodes = []
            in_line = True
            in_nodes = False
            line_source = source
            position += 1
        elif position + 1 < len(tokens) and tokens[position + 1][0] == "=":
            if not in_line or position + 2 >= len(tokens):
                raise ValueError(f"Unexpected or incomplete assignment: {token!r}")
            key = token.upper()
            value = tokens[position + 2][0]
            if key == "N":
                nodes.append(abs(int(value)))
                in_nodes = True
            else:
                attributes[key] = value
            position += 3
        elif in_nodes and re.fullmatch(r"[+-]?\d+", token):
            nodes.append(abs(int(token)))
            position += 1
        else:
            raise ValueError(f"Unexpected token in transit file: {token!r}")
    append_links()
    return pd.DataFrame(rows, columns=COLUMNS).astype(
        {"MODE": "int64", "A": "int64", "B": "int64", "source": "string"}
    )


def parse_transit_lines(
    path: str | Path = DEFAULT_INPUT, default_oneway: str = "F"
) -> pd.DataFrame:
    """Read a .lin file and return LINE NAME, MODE, ONEWAY, A, B, source columns."""
    return parse_transit_text(
        Path(path).read_text(encoding="utf-8-sig"), default_oneway=default_oneway
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("-o", "--output", type=Path, help="Optional output CSV path")
    parser.add_argument(
        "--default-oneway", choices=["T", "F"], default="F",
        help="Directionality for records missing ONEWAY (default: F)",
    )
    args = parser.parse_args()
    dataframe = parse_transit_lines(args.input, default_oneway=args.default_oneway)
    print(dataframe.head(10).to_string(index=False))
    print(f"\n{len(dataframe):,} links from {dataframe['LINE NAME'].nunique():,} lines")
    if args.output:
        dataframe.to_csv(args.output, index=False)
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()