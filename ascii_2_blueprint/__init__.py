import os, zlib, json, click
from itertools import cycle
from base64 import b64encode
from rich.prompt import Prompt
from rich.console import Console
from homoglyphs import Homoglyphs
from .utils.vector2 import Vector2
from .utils.blueprint import Blueprint
from typing import Optional, Union, Dict, List, Tuple

class Ascii2FactorioBlueprint:
    def __init__(self, **kwargs) -> None:
        self.step: int = kwargs.pop("size")
        self.ascii_name: str = kwargs.pop("name")
        self.verbose: bool = kwargs.pop("verbose")
        self.log_level: int = kwargs.pop("log_level")
        self.ascii_input: str = kwargs.pop("ascii_input")
        self.charmap: Optional[Dict] = kwargs.pop("charmap")
        self.normalize: bool = kwargs.pop("homoglyph_normalize")
        self.block_priority: List = kwargs.pop("block_priority")
        self.remap_similar_chars: bool = kwargs.pop("remap_similar_chars")
        self.remap_chars_agressiveness: int = kwargs.pop("remap_chars_agressiveness")
        self.console = Console()

        if kwargs.pop("using_default_blocks"):
            self.log(f"No block_priority passed, using default block priorities: {self.block_priority}", _type="warning")
    
    @staticmethod
    def compress_and_encode(data: Dict) -> str:
        return "0" + b64encode(
            zlib.compress(json.dumps(data, separators=(",", ":")).encode("utf-8"), level=9)
        ).decode("utf-8")

    @staticmethod
    def homoglyph_normalize(ascii_input: str) -> str:
        homoglyphs = Homoglyphs()
        for char in set(ascii_input):
            glyph = homoglyphs.get_combinations(char)[0]
            ascii_input = ascii_input.replace(char, glyph)
        return ascii_input

    def log(self, msg, _type: Optional[str] = None, _format: bool = True, pretty: bool = True, **kwargs) -> None:
        prefix = {
            "error": "[red][!]",
            "warning": "[yellow][?]",
            "debug": "[purple][*]",
            "info": "[blue][+]",
            "success": "[green][>]",
        }

        if _type and _type not in prefix.keys():
            self.log(f"Bad type '{_type}' passed to logging function.", _type="warning")
            return None

        if not self.verbose or _type != "error":
            if self.log_level < 1:
                return None
            elif _type == "warning" and self.log_level < 2:
                return None
            elif _type == "info" or _type == "success" and self.log_level < 3:
                return None
            elif _type == "debug" and self.log_level < 4:
                return None

        formatted = f"{prefix.get(_type)}[/]: {msg}" if _type and _format else msg
        if not pretty:
            print(formatted)
            return None

        self.console.print(formatted, **kwargs)

    def map_chars(
        self,
        ascii_input: str, 
        block_priority: List,
        charmap: Optional[Dict], 
        remap_similar_chars: bool = False, 
        remap_chars_agressiveness: int = 5,
        **kwargs
    ) -> Optional[Dict]:
        """
        Map chars to item in block map.
        ascii_input: ascii input to map.
        block_priority: List of blocks to map to based on char frequency.
        remap_similar_chars: Remap character with previously seen character if it is "close" in unicode.
        remap_chars_range (dangerous): limit how "close" of a match we replace.
        """
        self.log("Attempting to generate charmap...", _type="debug")

        charmap = {
            "\t": "tab",
            "\n": "new_line",
            " ": None,
        } if not charmap else charmap
        unique_chars = set(ascii_input)
        blocks = cycle(block_priority)
        sorted_by_frequency = sorted([(i, ascii_input.count(i)) for i in unique_chars], key=lambda x: x[1], reverse=True)

        for char, count in sorted_by_frequency:
            if char in charmap.keys():
                continue
            if remap_similar_chars:
                closest_match = 0
                char_int = ord(char)
                for sub_char in charmap.keys():
                    sub_char_int = ord(sub_char)
                    diff = abs(sub_char_int - char_int)
                    if diff <= remap_chars_agressiveness and abs(closest_match - char_int) >= diff:
                        closest_match = sub_char_int
                if closest_match:
                    charmap.update({char: charmap[chr(closest_match)]})
                    continue
            charmap.update({char: next(blocks)})
        return charmap

    def map_ascii(
        self,
        name: str,
        text: str,
        charmap: Dict,
        step: int = 2,
        **kwargs
    ) -> Blueprint:

        col, line = 0, 0
        bp = Blueprint(label=name)

        for char in text:
            mapped_name = charmap[char]
            if mapped_name == "new_line":
                col = 0
                line += step
                continue
            elif mapped_name == "tab":
                col += 2

            self.log(f"({col}, {line}) '{mapped_name}' {char}", _type="debug")
            for x in range(step):
                for y in range(step):
                    bp.add_data(name=mapped_name, pos=Vector2(col+x, line+y))
            col += step

        return bp

    def convert(self) -> Tuple[Optional[str], bool]:        
        if self.normalize:
            self.ascii_input = self.homoglyph_normalize(self.ascii_input)
        charmap = self.map_chars(
            ascii_input=self.ascii_input, 
            block_priority=self.block_priority,
            charmap=self.charmap,
            remap_similar_chars=self.remap_similar_chars,
            remap_chars_agressiveness=self.remap_chars_agressiveness
        )
        if not charmap:
            self.log("No charmap!", _type="error")
            return None, False
        self.log(f"Charmap: {charmap}", _type="info")
        mapped_ascii = self.map_ascii(
            name=self.ascii_name, 
            text=self.ascii_input, 
            charmap=charmap, 
            step=self.step
        )
        if not mapped_ascii:
            self.log("No ascii map!", _type="error")
            return None, False
        self.log(f"Ascii map: {mapped_ascii}", _type="info")
        self.log(mapped_ascii.as_dict, _type="debug", _format=False, pretty=False)
        compressed = self.compress_and_encode(mapped_ascii.as_dict)
        return compressed, True


def get_input() -> str:
    print("Paste your ascii.\nCtrl-D or Ctrl-Z ( windows ) to save it.")
    contents = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line and line[-1].encode() == b'\x1a':
            contents.append(line[:-1])
            break
        contents.append(line)
    return "\n".join(contents)


@click.command()
@click.option("--input", "-i", default=None, help="Input file to convert to blueprint.")
@click.option("--output", "-o", default=None, help="Output file to write blueprint (outputs to terminal if not set).")
@click.option("--name", "-n", default="unamed", help="Name of the blueprint.")
@click.option("--size", "-s", default=4, help="Size of blueprint, lower this number if blueprint is too large.")
@click.option("--verbose", "-v", default=False, help="Enable verbose output for more detailed logs.")
@click.option("--log-level", "-log", default=3, help="Output log level (All logs = 4, Errors only = 1). Overriden by '--verbose'.")
@click.option("--blockpriority-file", "-blockpriority", default=None, help="JSON file with blocks to map to chars that appears with the highest frequency.")
@click.option("--charmap-file", "-charmap", default=None, help="JSON file with character mappings.")
@click.option("--homoglyph_normalize", "-normalize", default=True, help="Attempts to remap characters to their first homoglyph (e.g 𝒒 -> q)")
@click.option("--remap-similar-chars", "-remap", default=False, help="Remap character with previously seen character if it is 'close' in unicode.")
@click.option("--remap-chars-agressiveness", "-remap-magnitude", default=5, help="How agressive the remapping of characters is. (its recommended to not touch this setting)")
def main(**kwargs):
    _input = kwargs.pop("input")
    if not _input:
        ascii_input = get_input()
    else:
        with open(_input, "r", encoding="utf-8") as f:
            ascii_input = f.read()
    if not ascii_input:
        raise ValueError("No valid input!")
    kwargs.update(ascii_input=ascii_input)

    using_default_blocks = False
    blocks = kwargs.pop("blockpriority_file")
    if blocks:
        with open(blocks, "r", encoding="utf-8") as f:
            blocks = json.load(f)
    else:
        blocks = [
            "stone-path",
            "hazard-concrete-right",
            "hazard-concrete-right",
            "concrete",
            "hazard-concrete-left",
            "hazard-concrete-left",
        ]
        using_default_blocks = True

    kwargs.update(block_priority=blocks)
    kwargs.update(using_default_blocks=using_default_blocks)

    charmap = kwargs.pop("charmap_file")
    if charmap:
        with open(charmap, "r", encoding="utf-8") as f:
            charmap = json.load(f)
    kwargs.update(charmap=charmap)

    afb = Ascii2FactorioBlueprint(**kwargs)
    convert, success = afb.convert()
    if not success:
        afb.log("Failed to create blueprint!", _type="error")
        return None
    output = kwargs.pop("output")
    if not output:
        afb.log(f"Sucessfully created blueprint:", _type="success")
        afb.log(convert, _format=False, pretty=False)
    else:
        afb.log(f"Sucessfully created blueprint, writing contents to '{output}'...", _type="success")
        with open(output, "w", encoding="utf-8") as f:
            f.write(convert)
    

if __name__ == "__main__":
    main()