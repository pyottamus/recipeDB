from dataclasses import dataclass
from pathlib import Path
from .recipeDB_lexemes import *
                    
class Lexer:
    def __init__(self, file: Path):
        self.file = file
        self.entered = False
        self.io = None
        self.line = 1
        self.linetab = [0]
        self.pos = 0
        self.data = None
    def __enter__(self):
        self.entered = True
        self.io = self.file.open("r", newline='')
        return self
    def newline(self):
        self.line += 1
        self.linetab.append(self.pos)
    def inc_linetab(self):
        linetab_len = len(self.linetab)
        while self.pos < len(self.data) and self.data[self.pos] != '\n':
            self.pos += 1
        if self.pos != len(self.data):
            self.pos += 1
        self.line += 1
        self.linetab.append(self.pos)
    def increase_linetab(self, amount: int):
        for _ in range(amount):
            self.inc_linetab()
            
        return amount
    def decrease_linetab(self, amount: int):
        for i in range(amount):
            del self.linetab[-1]
    def advance(self):
        pos = self.pos
        
        if pos == len(self.data):
            return ""
        else:
            self.pos += 1
            return self.data[pos]
    def peek(self):
        pos = self.pos
        if pos == len(self.data):
            return ""
        else:
            return self.data[pos]
    def read_to_delim(self):
        """ Reads until first of SP, NL, ',', '>', '<', '{', '}', ';' or EOF """
        start = self.pos
        
        while self.pos < len(self.data) and self.data[self.pos] not in DELIM_CHARS:
            self.pos += 1
        return self.data[start:self.pos]
    def read_to_sp(self):
        """ Reads until first space char or EOF"""
        start = self.pos
        
        while self.pos < len(self.data) and self.data[self.pos] not in SPACE_CHARS:
            self.pos += 1
        return self.data[start:self.pos]
    def read_to_nl(self):
        """ Reads until first newline char or EOF"""
        start = self.pos
        while self.pos < len(self.data) and self.data[self.pos] != '\n':
            self.pos += 1
        return self.data[start:self.pos]
    def error(self, start_line: int, start_pos: int, msg: str):
        start_pos += 1
        end_line_inclusive = self.line
        end_pos = self.pos
        line_start_pos = self.linetab[start_line - 1]
        if end_line_inclusive == len(self.linetab):
            increased = self.increase_linetab(1)
        else:
            increased = 0
        line_end_pos = self.linetab[end_line_inclusive + 1 - 1]
        self.decrease_linetab(increased)
        start_col = start_pos - line_start_pos 
        raise RuntimeError(f"{msg}\n\tError Occured on line {start_line}, offset {start_col}\nFull lines follows After line break\n{self.data[line_start_pos:line_end_pos]}")
    def skip_sp_special(self):
        """ Skips whitespace. Takes care of line continuation ( "text \\\n moretext"). Returns True if end of prefix is found."""
        while self.pos < len(self.data):
            c = self.peek()
            if c in SPACE_CHARS:
                self.advance()
                if c == '\n':
                    self.newline()
                    return True
            elif c == '/':
                return True
            elif c == '\\':
                self.advance()
                if self.pos == len(self.data):
                    self.error(self.line, self.pos, "Expected newline after '\\', got EOF")
                c = self.peek()
                if c == '\r':
                    self.advance()
                    if self.pos == len(self.data):
                        self.error(self.line, self.pos, "Expected newline after '\\', got EOF")
                    c = self.peek()
                if c == '\n':
                    self.advance()
                    self.newline()
                    continue
                else:
                    self.error(self.line, self.pos, f"Expected newline after '\\', got {c!r}")
                
            else:
                break
        if self.pos == len(self.data):
            return True
        return False

    def match_after_prefix(self):
        if self.skip_sp_special():
            yield EOP(self.line, self.line, self.pos, 0)
            return

        while True:
            c = self.advance()
            match c:
                case '(':
                    yield LParen(self.line, self.line, self.pos - 1, 1)
                case ')':
                    yield RParen(self.line, self.line, self.pos - 1, 1)
                case ',':
                    yield Comma(self.line, self.line, self.pos - 1, 1)
                case _:
                    if c.isidentifier():
                        yield self.match_varname_or_materialized_varname(c)
                    else:
                        self.error(self.line, self.pos - 1, f"Unexpected Token {c!r}")

            if self.skip_sp_special():
                yield EOP(self.line, self.line, self.pos, 0)
                return

    def match_prefix(self, c: str):
        start = self.pos - 1
        target = self.read_to_sp()
        orig = target
        target = target.lower()
        start_line = self.line
        match target:
            case "fluid":
                prefix = FluidPrefix(self.line, self.line, start, self.pos - start)
            case "material":
                prefix = MaterialPrefix(self.line, self.line, start, self.pos - start)
            case "tool":
                prefix = ToolPrefix(self.line, self.line, start, self.pos - start)
            case "named":
                prefix = NamedPrefix(self.line, self.line, start, self.pos - start)
            case "component":
                prefix = ComponentPrefix(self.line, self.line, start, self.pos - start)
            case "station":
                prefix = StationPrefix(self.line, self.line, start, self.pos - start)

            case "materialize":
                prefix = MaterializePrefix(self.line, self.line, start, self.pos - start)
            case "materialize*":
                prefix = MaterializeStarPrefix(self.line, self.line, start, self.pos - start)
            case _:
                self.error(self.line, start, f"Unexpected # declaration {orig!r}")

        yield prefix
        yield from self.match_after_prefix()
    def get_fluid_suffix(self, num: str):
        prefix = ""
        suffix = ""
        for i, c in enumerate(num):
            if c.isdigit():
                prefix += c
            else:
                suffix = num[i:]
                break
        return prefix, suffix

    def fluid_spec_suffix_test(self, start: int, num: str):
        prefix, suffix = self.get_fluid_suffix(num)
        if len(suffix) > 2:
            self.error(self.line, start, f"Expected FluidSuffix, got {suffix!r}")
        match suffix:
            case "L":
                take = 1
                suffix = FluidSuffix.L
            case "B":
                take = 1
                suffix = FluidSuffix.L
            case "mB":
                take = 2
                suffix = FluidSuffix.mB
            case _:
                self.error(self.line, start, f"Expected FluidSuffix, got {suffix!r}")

        return FluidSpec(self.line, self.line, start, len(num), int(prefix), suffix)

     
    def match_number_or_fluid_spec(self, c: str):
        start = self.pos - 1
        num = c
        num += self.read_to_delim()
        if num.isdigit():
            return Number(self.line, self.line, start, len(num), int(num))
        else:
            return self.fluid_spec_suffix_test(start, num)
    def match_multi_line_comment(self):
        start = self.pos - 1
        start_line = self.line
        self.pos += 1
        text_start = self.pos
        while self.pos < len(self.data) - 1:
            if self.data[self.pos] == '*' and self.data[self.pos + 1] == '/':
                break
            if self.data[self.pos] == '\n':
                self.newline()
            self.pos += 1

        if self.pos >= len(self.data) - 1:
            self.error(self.line, start, "Unterminated multi-line comment")
        assert self.data[self.pos:self.pos+2] == "*/", f"critical assertion error, expected '*/, {self.line} {self.pos}'"
        text = self.data[text_start:self.pos]
        self.pos += 2
        
        return MultiLineComment(start_line, self.line, start, len(text) + 4, text)
    def match_single_line_comment(self):
        start = self.pos - 1
        self.pos += 1
        text = self.read_to_nl()
        return SingleLineComment(self.line, self.line, start, len(text) + 2, text)
    def match_comment(self, c: str):
        start = self.pos - 1
        match self.peek():
            case "/":
                return self.match_single_line_comment()
            case "*":
                return self.match_multi_line_comment()
            case "":
                self.error(self.line, self.pos, f"Expected '*' or '/' to follow '/', got EOF")
            case _:
                self.error(self.line, self.pos, f"Expected '*' or '/' to follow '/', got {self.peek()!r}")
    def match_material(self):
        start = self.pos
        c = self.data[self.pos]
        if not c.isidentifier():
            self.error(self.line, self.pos, f"Expected a material name after '[', got {c!r}")
        self.pos += 1
        while self.pos < len(self.data) and f'a{self.data[self.pos]}'.isidentifier():
            self.pos += 1
        material = self.data[start:self.pos]
        if self.pos == len(self.data):
            self.error(self.line, self.pos, f"Expected terminating ']', got EOF")
        elif self.data[self.pos] != ']':
            self.error(self.line, self.pos, f"Expected terminating ']', got {self.data[self.pos]!r}")
        self.pos += 1
        return material
    def match_varname_or_materialized_varname(self, c: str):
        start = self.pos - 1
        while self.pos < len(self.data) and f'a{self.data[self.pos]}'.isidentifier():
            self.pos += 1
        name = self.data[start:self.pos]
        if self.pos == len(self.data):
            return Varname(self.line, self.line, start, len(name), name)

        
        if self.data[self.pos] != '[':
            return Varname(self.line, self.line, start, len(name), name)
        else:
            self.pos += 1
            material = self.match_material()
            return MaterializedVarname(self.line, self.line, start, len(name) + len(material) + 2, name, material)
    def match_dolarsign(self, c: str):
        start = self.pos - 1
        target = self.read_to_sp()
        orig = target
        target = target.lower()
        start_line = self.line


        match target:
            case "generic":
                return GenericDecl(start_line, self.line, start, self.pos - start)
            case _:
                self.error(self.line, start, f"Unrecognized dolarsign declaration {target}")

    def lex(self):
        self.data = self.io.read()

        while True:
            c = self.advance()
            match c:
                case "\t" | "\r" | " ":
                    continue
                case "\n":
                    self.newline()
                case "$":
                    yield self.match_dolarsign(c)
                case "":
                    yield EOF(self.line, self.line, self.pos, 0)
                    break
                case "#":
                    yield from self.match_prefix(c)
                case "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9":
                    yield self.match_number_or_fluid_spec(c)
                case "/":
                    yield self.match_comment(c)
                case ":":
                    yield Colon(self.line, self.line, self.pos - 1, 1)
                case ";":
                    yield SemiColon(self.line, self.line, self.pos - 1, 1)
                case "<":
                    yield LT(self.line, self.line, self.pos - 1, 1)
                case ">":
                    yield GT(self.line, self.line, self.pos - 1, 1)
                case '{':
                    yield LCurly(self.line, self.line, self.pos - 1, 1)
                case '}':
                    yield RCurly(self.line, self.line, self.pos - 1, 1)
                case ',':
                    yield Comma(self.line, self.line, self.pos - 1, 1)
                case _:
                    if c.isidentifier():
                        yield self.match_varname_or_materialized_varname(c)
                    else:
                        self.error(self.line, self.pos - 1, f"Unexpected Token {c!r}")
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.io is not None:
            self.io.close()
            del self.data

if __name__ == "__main__":
    file = Path(r"C:\Users\josep\Desktop\recipes.txt")
    l = Lexer(file)
    with l:
        lexemes = list(l.lex())
        for lexeme in lexemes:
            print(lexeme)

