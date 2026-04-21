from dataclasses import dataclass
from enum import IntEnum

class Lexeme:
    __slots__ = "start_line", "end_line", "pos", "length"
    def __init__(self, start_line: int, end_line: int, pos: int, length: int):
        self.start_line = start_line
        self.end_line = end_line
        self.pos = pos
        self.length = length
    def __repr__(self):
        return f'{self.__class__.__name__}()'
class Colon(Lexeme):
    __slots__ = ()
class SemiColon(Lexeme):
    __slots__ = ()
class LT(Lexeme):
    __slots__ = ()

class GT(Lexeme):
    __slots__ = ()
class LCurly(Lexeme):
    __slots__ = ()
class RCurly(Lexeme):
    __slots__ = ()
class LParen(Lexeme):
    __slots__ = ()
class RParen(Lexeme):
    __slots__ = ()
class Comma(Lexeme):
    __slots__ = ()
class GenericDecl(Lexeme):
    __slots__ = ()
class Generic(Lexeme):
    __slots__ = 'name',
    def __init__(self, start_line: int, end_line: int, pos: int, length: int, name: str):
        super().__init__(start_line, end_line, pos, length)
        self.name = name
    def __repr__(self):
        return f"{self.__class__.__name__}({self.name!r})"
class Comment(Lexeme):
    __slots__ = "text",
    def __init__(self, start_line: int, end_line: int, pos: int, length: int, text: str):
        super().__init__(start_line, end_line, pos, length)
        self.text = text
    def __repr__(self):
        return f"{self.__class__.__name__}({self.text!r})"

class SingleLineComment(Comment):
    __slots__ = ()
class MultiLineComment(Comment):
    __slots__ = ()
class Prefix(Lexeme):
    __slots__ = ()
    @property
    def prefix(self):
        raise NotImplementedError
    def __repr__(self):
        return f"{self.__class__.__name__}({self.prefix})"
class PrefixType(IntEnum):
    station = 0
    component = 1
    tool = 2
    named = 3
    material = 4
    materialize = 5
    materialize_star = 6
    fluid = 7
class MaterializeStarPrefix(Prefix):
    __slots__ = ()
    @property
    def prefix(self):
        return PrefixType.materialize_star
class MaterializePrefix(Prefix):
    __slots__ = ()
    @property
    def prefix(self):
        return PrefixType.materialize
class StationPrefix(Prefix):
    __slots__ = ()
    @property
    def prefix(self):
        return PrefixType.station
class ComponentPrefix(Prefix):
    __slots__ = ()
    @property
    def prefix(self):
        return PrefixType.component
class MaterialPrefix(Prefix):
    __slots__ = ()
    @property
    def prefix(self):
        return PrefixType.material
class FluidPrefix(Prefix):
    __slots__ = ()
    @property
    def prefix(self):
        return PrefixType.fluid
class ToolPrefix(Prefix):
    __slots__ = ()
    @property
    def prefix(self):
        return PrefixType.tool
class NamedPrefix(Prefix):
    __slots__ = ()
    @property
    def prefix(self):
        return PrefixType.named
class EOP(Lexeme):
    __slots__ = ()

class Number(Lexeme):
    __slots__ = "amount",
    def __init__(self, start_line: int, end_line: int, pos: int, length: int, amount: int):
        super().__init__(start_line, end_line, pos, length)
        self.amount = amount
    def __repr__(self):
        return f"{self.__class__.__name__}({self.amount})"
class FluidSuffix(IntEnum):
    L = 0
    mB = 1
    B  = 2
class FluidSpec(Lexeme):
    __slots__ = "amount", "suffix", "original_suffix"
    @property
    def original_amount(self) -> int:
        if self.original_suffix == FluidSuffix.B:
            return self.amount // 1000
        else:
            return self.amount
    def __init__(self, start_line: int, end_line: int, pos: int, length: int, amount: int, suffix: FluidSuffix):
        super().__init__(start_line, end_line, pos, length)
        self.amount = amount
        self.suffix = suffix
        self.original_suffix = suffix
        self.normalize()
    def normalize(self):
        if self.suffix == FluidSuffix.L:
            return
        elif self.suffix == FluidSuffix.mB:
            self.suffix = FluidSuffix.L
        elif self.suffix == FluidSuffix.B:
            self.amount *= 1000
            self.suffix = FluidSuffix.L
        else:
            raise RuntimeError(f"Unknown fluid suffix {self.suffix.name}")
    def __repr__(self):
        return f"{self.__class__.__name__}({self.amount}{self.suffix.name})"

type VarnameLike = Varname | MaterializedVarname
class Varname(Lexeme):
    __slots__ = "name",
    @property
    def material(self):
        return None
    @property
    def generic(self):
        return False
    @property
    def qname(self) -> str:
        return self.name
    def __init__(self, start_line: int, end_line: int, pos: int, length: int, name: str):
        super().__init__(start_line, end_line, pos, length)
        self.name = name
    def __repr__(self):
        return f'<Varname: {self.name}>'
    def substitute(self, item: VarnameLike):
        return self


class MaterializedVarname(Lexeme):
    __slots__ = "component", "material"
    @property
    def name(self):
        return self.component
    @property
    def qname(self) -> str:
        return f"{self.name}[{self.material}]"

    @property
    def generic(self):
        return False

    def __init__(self, start_line: int, end_line: int, pos: int, length: int, component: str, material: str):
        super().__init__(start_line, end_line, pos, length)
        self.component = component
        self.material = material

    def __repr__(self):
        return f'<MaterializedVarname: {self.name}[{self.material}]>'

    def substitute(self, item: Varname | MaterializedVarname):
        return self

class EOF(Lexeme):
    __slots__ = ()

SPACE_CHARS = {'\r', '\n', '\t', ' '}
DELIM_CHARS = {'\r', '\n', '\t', ' ', ',', '>', '<', '{', '}', ';'}
