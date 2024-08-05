import os, zlib, json, click
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
        self.blocks: List = kwargs.pop("block_list")
        self.log_level: int = kwargs.pop("log_level")
        self.ascii_input: str = kwargs.pop("ascii_input")
        self.charmap: Optional[Dict] = kwargs.pop("charmap")
        self.block_priority: str = kwargs.pop("block_priority")
        self.normalize: bool = kwargs.pop("homoglyph_normalize")
        self.remap_similar_chars: bool = kwargs.pop("remap_similar_chars")
        self.remap_chars_agressiveness: int = kwargs.pop("remap_chars_agressiveness")
        self.console = Console()
    
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
        block_list: List, 
        block_priority: Optional[str] = None, 
        remap_similar_chars: bool = False, 
        remap_chars_agressiveness: int = 5,
        **kwargs
    ) -> Optional[Dict]:
        """
        Map chars to item in block map.
        ascii_input: ascii input to map.
        block_list: list of blocks to map to.
        block_priority: block to map to char that appears with the highest frequency.
        remap_similar_chars: Remap character with previously seen character if it is "close" in unicode.
        remap_chars_range (dangerous): limit how "close" of a match we replace.
        """
        self.log("Attempting to generate charmap...", _type="debug")

        charmap = {
            "\t": "tab",
            "\n": "new_line",
            " ": None,
        }
        unique_chars = set(ascii_input)
        blocks = block_list.copy()

        if block_priority:
            priority = blocks.pop(blocks.index(block_priority))
            char, freqency = max([(i, ascii_input.count(i)) for i in unique_chars], key=lambda x: x[1])
            self.log(f"{char} appears {freqency} times, setting to: '{priority}'", _type="info")
            charmap.update({char: priority})

        for char in unique_chars:
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
            
            try:
                charmap.update({char: blocks.pop(0)})
            except IndexError:
                self.log("Ran out of blocks to use in charmap!", _type="error")
                return None

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
        charmap = self.charmap or self.map_chars(
            ascii_input=self.ascii_input, 
            block_list=self.blocks, 
            block_priority=self.block_priority,
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
@click.option("--blocklist-file", "-blocklist", default="./default_blocks.txt", help="Text file which contains list of allowed blocks")
@click.option("--block-priority", "-priority", default=None, help="Block to map to char that appears with the highest frequency.")
@click.option("--charmap-file", "-charmap", default=None, help="JSON file with character mappings.")
@click.option("--name", "-n", default="unamed", help="Name of the blueprint.")
@click.option("--size", "-s", default=4, help="Size of blueprint, lower this number if blueprint is too large.")
@click.option("--verbose", "-v", default=False, help="Enable verbose output for more detailed logs.")
@click.option("--log-level", "-log", default=3, help="Output log level (All logs = 4, Errors only = 1). Overriden by '--verbose'.")
@click.option("--homoglyph_normalize", "-normalize", default=True, help="Attempts to remap characters to their first homoglyph (e.g 𝒒 -> q)")
@click.option("--remap-similar-chars", "-remap", default=True, help="Remap character with previously seen character if it is 'close' in unicode.")
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

    blocklist = kwargs.pop("blocklist_file")
    if not blocklist:
        raise ValueError("No blocklist passed!")
    with open(blocklist, "r", encoding="utf-8") as f:
        blocks = [line.strip() for line in f.readlines()]
    kwargs.update(block_list=blocks)

    priority = kwargs.pop("block_priority")
    if not priority:
        priority = blocks[0]
    if priority not in blocks:
        raise ValueError("Priority block does not exist in blocklist!")
    kwargs.update(block_priority=priority)

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