import os, zlib, json, click, math
from itertools import cycle
from base64 import b64encode
from rich.prompt import Prompt
from rich.console import Console
from homoglyphs import Homoglyphs
from pyperclip import copy as set_clipboard
from typing import Optional, Union, Dict, List, Tuple

from .utils.web import Teoxoy
from .utils.vector2 import Vector2
from .utils.blueprint import Blueprint
from .utils.model import braille_charmap

class Ascii2FactorioBlueprint:
    def __init__(self, **kwargs) -> None:
        # Important args
        self.ascii_input: str = kwargs.pop("ascii_input")
        self.blocks: List = kwargs.pop("blocks")
        self.charmap: Dict = kwargs.pop("charmap")

        # Config args
        self.blueprint_name: str = kwargs.pop("blueprint_name")
        self.mode: str = kwargs.pop("mode")
        self.size: float = kwargs.pop("size")

        # Defaulted args
        self.normalize: bool = kwargs.pop("homoglyph_normalize")
        self.remap_similar_chars: int = kwargs.pop("remap_similar_chars")
        
        # Additional args
        self.verbose: bool = kwargs.pop("verbose")
        self.log_level: int = kwargs.pop("log_level")
        self.console = Console()

        # Validate
        if kwargs.pop("using_default_blocks"):
            self.log(f"No blocks passed, using default block list: {self.blocks}", _type="info")
        else:
            self.log(f"Using blocks: {self.blocks}", _type="info")

        if kwargs.pop("using_default_charmap"):
            self.log(f"No charmap passed, using default charmap: {self.charmap}", _type="info")

        if self.mode == "default":
            self.mode = self.predict_mode(self.ascii_input, self.charmap)
            self.log(f"Mode set as default, attempted to predict mode, assumed mode: '{self.mode}'", _type="info")

    @staticmethod
    def compress_and_encode(data: Dict) -> str:
        return "0" + b64encode(
            zlib.compress(json.dumps(data, separators=(",", ":")).encode("utf-8"), level=9)
        ).decode("utf-8")

    @staticmethod
    def predict_mode(ascii_input: str, charmap: Dict) -> str:
        unique_chars = set(ascii_input)
        charmap_keys = list(charmap.keys())
        if all(char in list(braille_charmap.keys()) + charmap_keys for char in unique_chars):
            return "brail"
        return "generic"

    @staticmethod
    def homoglyph_normalize(ascii_input: str) -> str:
        homoglyphs = Homoglyphs()
        for char in set(ascii_input):
            glyph = homoglyphs.get_combinations(char)[0]
            ascii_input = ascii_input.replace(char, glyph)
        return ascii_input

    def log(self, msg, _type: str = "debug", _format: bool = True, pretty: bool = True, **kwargs) -> None:
        if not self.verbose or _type != "error":
            if self.log_level < 1:
                return None
            elif _type == "warning" and self.log_level < 2:
                return None
            elif _type in ("success", "info") and self.log_level < 3:
                return None
            elif _type == "debug" and self.log_level < 4:
                return None
        prefixes = {
            "error": "[red][!]",
            "warning": "[yellow][?]",
            "debug": "[purple][*]",
            "info": "[blue][+]",
            "success": "[green][>]",
        }
        prefix = prefixes.get(_type)
        if not prefix:
            self.log(f"Bad type '{_type}' passed to logging function.", _type="error")
            return None
        formatted = f"{prefix}[/]: {msg}" if _type and _format else msg
        if not pretty:
            print(formatted)
            return None
        self.console.print(formatted, **kwargs)

    def map_chars(
        self,
        ascii_input: str, 
        blocks: List,
        charmap: Dict, 
        remap_similar_chars: int = 0, 
        **kwargs
    ) -> Dict:
        """
        Map chars to item in block map.
        ascii_input: ascii input to map.
        blocks: List of blocks to map to based on char frequency.
        charmap: Dict of intial character mappings, expanded by this function.
        remap_similar_chars: (Dangerous) Remap character with previously seen character if it is "close" in unicode.
        """
        unique_chars = set(ascii_input)
        blocks = cycle(blocks)
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
                    if diff <= remap_similar_chars and abs(closest_match - char_int) >= diff:
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
        mode: str,
        size: float,
        charmap: Dict,
        **kwargs
    ) -> Optional[Blueprint]:
        
        
        col, line = 0.0, 0.0
        bp = Blueprint(label=name)
        col_offset, line_offset = 3, 5
        if mode.startswith("brail"):
            col_offset *= 2
            line_offset *= 2
            vector_offset = Vector2(2 * size, 2 * size)
        col_offset *= size
        line_offset *= size

        for char in text:
            mapped_name = charmap[char]
            if not mapped_name:
                col += col_offset
                continue
            if mapped_name == "new_line":
                col = 0
                line += line_offset
                continue
            if mapped_name == "tab":
                col += (col_offset / 2)

            global_pos = Vector2(col,line)
            vectors = braille_charmap.get(char)

            if mode.startswith("brail"):
                for y in range(8):
                    vector = vectors[y]
                    if not vector:
                        continue
                    x = 0 if y < 4 else 1
                    current_pos = Vector2(x, y % 4) * vector_offset
                    bp.add_data(name=mapped_name, pos=current_pos + global_pos)
            elif mode == "generic":
                for x in range(math.ceil(4 * size)):
                    for y in range(math.ceil(6 * size)):
                        bp.add_data(name=mapped_name, pos=Vector2(x, y) + global_pos)
            else:
                self.log(f"Unknown mode: '{mode}'", _type="error")
                return None
                        
            col += col_offset
            self.log(f"({col}, {line}) '{mapped_name}' {char} {vectors}", _type="debug")

        return bp

    def convert(self) -> Tuple[Optional[str], bool]:        
        if self.normalize:
            self.ascii_input = self.homoglyph_normalize(self.ascii_input)

        self.log("Attempting to generate charmap...", _type="debug")
        charmap = self.map_chars(
            ascii_input=self.ascii_input, 
            blocks=self.blocks,
            charmap=self.charmap,
            remap_similar_chars=self.remap_similar_chars
        )
        
        self.log(f"Final charmap: {charmap}", _type="debug")
        blueprint = self.map_ascii(
            name=self.blueprint_name,
            text=self.ascii_input,
            mode=self.mode,
            size=self.size,
            charmap=charmap,
        )
        if not blueprint:
            self.log("No ascii map!", _type="error")
            return None, False

        self.log(f"Ascii map: {blueprint}", _type="debug")
        self.log(blueprint.as_dict, _type="debug", _format=False, pretty=False)
        compressed = self.compress_and_encode(blueprint.as_dict)
        return compressed, True

def get_input() -> str:
    print("Paste your Input.\nCtrl-D or Ctrl-Z ( windows ) to save it.")
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
@click.option("--blueprint-name", "-n", default="unamed", help="Name of the blueprint.")
@click.option("--size", "-s", default=1.0, show_default=True, help="Size of blueprint, lower this number if blueprint is too large.")
@click.option("--verbose", "-v", default=False, help="Enable verbose output for more detailed logs.")
@click.option("--mode", "-m", default="default", show_default=True, help="Mode of the blueprint generator. (See https://github.com/Ciarands/ascii-to-factorio-blueprint#modes for reference.)")
@click.option("--log-level", "-log", default=3, help="Output log level (All logs = 4, Errors only = 1). Overriden by '--verbose'.")
@click.option("--use-blocks", "-blocks", default=None, help="File or Array of blocks to use.")
@click.option("--charmap-file", "-charmap", default=None, help="JSON file with character mappings.")
@click.option("--remap-similar-chars", "-remap", default=0, help="(Dangerous) Remap character with previously seen character if it is 'close' in unicode.")
@click.option("--homoglyph_normalize", "-normalize", default=False, help="(Dangerous) Attempts to remap characters to their first homoglyph (e.g 𝒒 -> q)")
def main(**kwargs):
    # Set ascii input Ascii2FactorioBlueprint.ascii_input
    _input = kwargs.pop("input")
    if not _input:
        ascii_input = get_input()
    else:
        try:
            with open(_input, "r", encoding="utf-8") as f:
                ascii_input = f.read()
        except FileNotFoundError:
            print("Input file doesnt exist!")
            return None
    if not ascii_input:
        print("No valid input!")
        return None
    kwargs.update(ascii_input=ascii_input)

    # Set blocks to use Ascii2FactorioBlueprint.blocks
    using_default_blocks = False
    blocks = kwargs.pop("use_blocks")
    if blocks:
        try:
            with open(blocks, "r", encoding="utf-8") as f:
                blocks = json.load(f)
        except FileNotFoundError:
            blocks = blocks.split(",")
        if not blocks:
            print(f"Could not retrieve any blocks '{blocks}' was a bad file or wrongly formatted string.")
            return None
    else:
        blocks = [
            "stone-path", # "concrete",
            "hazard-concrete-right", # "hazard-concrete-left",
        ]
        using_default_blocks = True
    kwargs.update(blocks=blocks)
    kwargs.update(using_default_blocks=using_default_blocks)

    # Set charmap
    using_default_charmap = False
    charmap = kwargs.pop("charmap_file")
    if charmap:
        with open(charmap, "r", encoding="utf-8") as f:
            charmap = json.load(f)
    else:
        charmap = {
            "\t": "tab",
            "\n": "new_line",
            " ": None,
            "⠀": None # (blank Braille)
        }
        using_default_charmap = True
    kwargs.update(charmap=charmap)
    kwargs.update(using_default_charmap=using_default_charmap)

    # Generate blueprint
    afb = Ascii2FactorioBlueprint(**kwargs)
    converted, success = afb.convert()
    if not success:
        afb.log("Failed to create blueprint!", _type="error")
        return None

    # Handle output method
    output = kwargs.pop("output")
    if not output:
        afb.log(f"Successfully created blueprint:", _type="success")
        afb.log(converted, _type="success", _format=False, pretty=False)
    elif output == "clipboard":
        afb.log("Successfully created blueprint, writing data to clipboard.", _type="success")
        set_clipboard(converted)
    elif output == "browser":
        afb.log(f"Successfully created blueprint, opening in browser.", _type="success")
        paste_url = Teoxoy.create_paste(converted)
        Teoxoy.open_in_browser(paste_url)
    else:
        afb.log(f"Successfully created blueprint, writing contents to '{output}'...", _type="success")
        with open(output, "w", encoding="utf-8") as f:
            f.write(converted)
    
if __name__ == "__main__":
    main()