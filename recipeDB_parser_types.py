from dataclasses import dataclass
from enum import IntEnum

from .recipeDB_types import NamedItem, MaterializedFluid, Tool, UndefinedSymbolError, QuantifiedToolError, \
    SymbolTypeError, MaterializedComponent, NotAFluidError, NotAMaterializedFluidError, Symbol, Component, Material
from .quantified import Quantified
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .recipeDB import RecipeDB
from .recipeDB_lexemes import *

@dataclass(slots=True)
class SubstitutedVarname:
    original: Varname
    alt: Varname
    @property
    def start_line(self):
        return self.original.start_line
    @property
    def end_line(self):
        return self.original.end_line
    @property
    def pos(self):
        return self.original.pos
    @property
    def name(self) -> str:
        return self.alt.name
    @property
    def qname(self) -> str:
        return self.alt.name
    @property
    def generic(self):
        return False
    @property
    def material(self):
        return None

    def __repr__(self):
        return f'<SubstitutedVarname: {self.name}>'
    def substitute(self, item: VarnameLike):
        return self


@dataclass(slots=True)
class SubstitutedMaterializedVarname:
    original: GenericMaterialMaterializedVarname | GenericComponentMaterializedVarname | Varname
    alt: Varname | MaterializedVarname
    component: str
    material: str
    @property
    def start_line(self):
        return self.original.start_line
    @property
    def end_line(self):
        return self.original.end_line
    @property
    def pos(self):
        return self.original.pos
    @property
    def name(self):
        return self.component
    @property
    def qname(self):
        return f'{self.component}[{self.material}]'
    @property
    def generic(self):
        return False
    def __repr__(self):
        return f'<SubstitutedMaterializedVarname: {self.name}[{self.material}]>'
    def substitute(self, item: Varname | MaterializedVarname):
        return self

@dataclass(slots=True)
class GenericItem:
    original: Varname
    @property
    def qname(self) -> str:
        return "$"
    @property
    def name(self) -> str:
        return "$"
    @property
    def material(self):
        return None
    def substitute(self, item: Varname | MaterializedVarname) -> SubstitutedVarname | SubstitutedMaterializedVarname:
        if isinstance(item, Varname):
            return SubstitutedVarname(self.original, item)
        else:
            return SubstitutedMaterializedVarname(self.original, item, item.component, item.material)

class GenericComponentMaterializedVarname:
    __slots__ = "original", "material",
    @property
    def start_line(self):
        return self.original.start_line
    @property
    def end_line(self):
        return self.original.end_line
    @property
    def pos(self):
        return self.original.pos
    @property
    def generic(self):
        return True
    @property
    def name(self) -> str:
        return "$"
    @property
    def qname(self) -> str:
        return f"$[{self.material}]"
    def __init__(self, original: MaterializedVarname, material: str):
        self.original = original
        self.material = material
    def __repr__(self):
        return f'{self.__class__.__name__}({self.material!r})'
    def substitute(self, item: Varname | MaterializedVarname) -> SubstitutedMaterializedVarname:

        if isinstance(item, MaterializedVarname):
            raise ValueError("Cannot substitute a MaterializedVarname into a GenericComponentMaterializedVarname")
        return SubstitutedMaterializedVarname(self, item, item.name, self.material)


class GenericMaterialMaterializedVarname:
    __slots__ = "original", "component",
    @property
    def start_line(self):
        return self.original.start_line
    @property
    def end_line(self):
        return self.original.end_line
    @property
    def pos(self):
        return self.original.pos
    @property
    def generic(self):
        return True
    @property
    def name(self) -> str:
        return self.component
    @property
    def qname(self) -> str:
        return f"{self.name}[$]"
    @property
    def material(self) -> str:
        return "$"
    def __init__(self, original: MaterializedVarname, component: str):
        self.original = original
        self.component = component
    def __repr__(self):
        return f'{self.__class__.__name__}({self.name!r})'
    def substitute(self, item: Varname | MaterializedVarname) -> SubstitutedMaterializedVarname:
        if isinstance(item, MaterializedVarname):
            raise ValueError("Cannot substitute a MaterializedVarname into a GenericMaterialtMaterializedVarname")
        return SubstitutedMaterializedVarname(self, item, self.name, item.name)

class Expression:
    __slots__ = "value"
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"<Exrpression {self.value!r}>"
@dataclass(slots=True)
class Parsed:
    start: Lexeme
    end: Lexeme
    
class TierSpec(IntEnum):
    ULV = 0
    LV = 1
    MV = 2
    HV = 3
    EV = 4
    IV = 5
    LuV = 6
    ZPM = 7
    UV = 8
    UHV = 9
    UEV = 10
    UIV = 11
    UMV = 12
    UXV = 13
@dataclass(slots=True)
class RecipeDeclaration(Parsed):
    product_list: list[QuantifiedValue]
    tier: TierSpec
    machine: str
    circuit: int
    items: list[QuantifiedValue]

    def substitute(self, item: Varname | MaterializedVarname) -> RecipeDeclaration:
        return self
@dataclass(slots=True)
class SubstitutedRecipeDeclaration:
    original: GenericRecipeDeclaration
    product_list: list[QuantifiedValue]
    tier: TierSpec
    machine: str
    circuit: int
    items: list[QuantifiedValue]

    @property
    def start(self):
        return self.original.start
    @property
    def end(self):
        return self.original.end
    def substitute(self, item: Varname | MaterializedVarname) -> SubstitutedRecipeDeclaration:
        return self
@dataclass(slots=True)
class GenericRecipeDeclaration(Parsed):
    generic_list: list[Varname]
    product_list: list[QuantifiedValue]
    tier: TierSpec
    machine: str
    circuit: int
    items: list[QuantifiedValue]
    generic_name: Varname
    def substitute(self, item: Varname | MaterializedVarname) -> SubstitutedRecipeDeclaration:
        products = [prdocut.substitute(item) for prdocut in self.product_list]
        items = [recipe_item.substitute(item) for recipe_item in self.items]
        return SubstitutedRecipeDeclaration(self, products, self.tier, self.machine, self.circuit, items)

@dataclass(slots=True)
class ResolvedGenericRecipeDeclaration:
    generic: GenericRecipeDeclaration
    generic_list: list[Symbol]
    product_list: list
@dataclass(slots=True)
class ResolvedVarname:
    varname: Varname
    symbol: Named
    @property
    def start_line(self) -> int:
        return self.varname.start_line
    @property
    def end_line(self) -> int:
        return self.varname.end_line
    @property
    def pos(self) -> int:
        return self.varname.pos
    @property
    def length(self) -> int:
        return self.varname.length
    @property
    def name(self) -> str:
        return self.varname.name

@dataclass(slots=True)
class ResolvedMaterializedVarname:
    materialized_varname: MaterializedVarname
    symbol: MaterializedComponent
    @property
    def start_line(self) -> int:
        return self.materialized_varname.start_line
    @property
    def end_line(self) -> int:
        return self.materialized_varname.end_line
    @property
    def pos(self) -> int:
        return self.materialized_varname.pos
    @property
    def length(self) -> int:
        return self.materialized_varname.length
    @property
    def name(self) -> str:
        return self.materialized_varname.name
    @property
    def material(self) -> str:
        return self.materialized_varname.material
    @property
    def component(self) -> str:
        return self.materialized_varname.component



@dataclass(slots=True)
class PartialGenericRecipe:
    generic_recipe_declaration: GenericRecipeDeclaration
    generic_list: list[Varname]
@dataclass(slots=True)
class MachineSpec(Parsed):
    tier: TierSpec    
    name: str
    circuit: int
    start: Lexeme
    end: Lexeme
Workbench_spec = MachineSpec(None, None, TierSpec.ULV, 'workbench', 0)

class ImpliedNumber:
    __slots__ = ()
    @property
    def amount(self):
        return 1
ImpliedNumberSingleton = ImpliedNumber()

class QuantifiedValue:
    __slots__ = "quantity", "item", "original_spec"
    @property
    def generic(self):
        return self.item is GenericItem or isinstance(self.item, (GenericMaterialMaterializedVarname, GenericComponentMaterializedVarname))
    @property
    def name(self):
        return self.item.name
    @property
    def material(self):
        return self.item.material
    def __init__(self, quantity: Number | ImpliedNumber | FluidSpec, item: Varname | MaterializedVarname | GenericItem | GenericMaterialMaterializedVarname | GenericComponentMaterializedVarname):
        self.item = item
        self.quantity = quantity.amount
        self.original_spec = quantity
    def substitute(self, item: Varname | MaterializedVarname) -> QuantifiedValue:
        return type(self)(self.original_spec, self.item.substitute(item))
class QuantifiedItem(QuantifiedValue):
    __slots__ = ()
    def __init__(self, quantity: Number | ImpliedNumber, item: Varname | MaterializedVarname | GenericItem | GenericMaterialMaterializedVarname | GenericComponentMaterializedVarname):
        super().__init__(quantity, item)
    def __repr__(self):
        return f"QuantifiedItem({self.quantity}, {self.item}"

    def resolve(self, db: RecipeDB):
        if self.generic:
            raise NotImplementedError

        item = db.get_sym(self.item.qname)
        if item is None:
            raise UndefinedSymbolError(f"Undefined item {self.item.name!r}", self.item.qname)

        if isinstance(item, Tool):
            if not isinstance(self.original_spec, ImpliedNumber):
                raise QuantifiedToolError("Cannot define a tool with quantity", self.item.qname)
            return item
        elif isinstance(item, (NamedItem, MaterializedComponent)):
            return Quantified(self.quantity, item)
        else:
            raise SymbolTypeError(f"Invalid type for quantified item {item.__class__.__name__!r}", NamedItem | Tool | MaterializedVarname, item.__class__)

class QuantifiedFluid(QuantifiedValue):
    __slots__ =  ()
    @property
    def units(self) -> FluidSuffix:
        return FluidSuffix.L
    def __init__(self, quantity: FluidSpec, item: Varname | MaterializedVarname | GenericItem | MaterializedGeneric):
        super().__init__(quantity, item)
    def resolve(self, db: RecipeDB):
        if self.generic:
            raise NotImplementedError
        if isinstance(self.item,  Varname):
            sym = db.get_sym(self.item.name)
            if sym is None:
                raise UndefinedSymbolError(f"Undefined fluid {self.item.name!r}", self.item.name)
            elif not sym.fluid:
                raise NotAFluidError(f"Cannot convert non-fluid {sym.qname!r} defined as type {sym.__class__.__name__} into a fluid", self, sym)
            return Quantified(self.quantity, sym)
        else:
            if self.item.name != 'fluid':
                raise NotAMaterializedFluidError(f"Cannot convert non-fluid {self.item.qname!r} into a fluid", self)
            sym = db.get_sym(self.item.qname)
            if sym is None:
                raise UndefinedSymbolError(f"Undefined fluid {self.item.name!r}", self.item.qname)
            elif not isinstance(sym, MaterializedFluid):
                raise NotAFluidError(f"Cannot convert non-fluid {self.item.qname!r} into a fluid", self, sym)
            return Quantified(self.quantity, sym)

def quantifiedValue(quantity: Number | ImpliedNumber | FluidSpec, item  : Varname | MaterializedVarname | GenericItem | GenericComponentMaterializedVarname | GenericMaterialMaterializedVarname) -> QuantifiedFluid | QuantifiedItem:
    if isinstance(quantity, FluidSpec):
        return QuantifiedFluid(quantity, item)
    else:
        return QuantifiedItem(quantity, item)
@dataclass(slots=True)
class NormalPrefixSpec(Parsed):
    spec: Prefix
    items: list[Varname]
    def __repr__(self):
        return f"{self.__class__.__name__}({self.items})"
class Named(NormalPrefixSpec):
    __slots__ = ()
class Tools(NormalPrefixSpec):
    __slots__ = ()
class Materials(NormalPrefixSpec):
    __slots__ = ()
class Components(NormalPrefixSpec):
    __slots__ = ()
class Stations(NormalPrefixSpec):
    __slots__ = ()
class Fluids(NormalPrefixSpec):
    __slots__ = ()
@dataclass(slots=True)
class Materialized(Parsed):
    spec: Prefix
    items: list[Varname]
    def __repr__(self):
        return f"{self.__class__.__name__}({self.items})"
@dataclass(slots=True)
class MaterializeStar(Parsed):
    spec: Prefix
    components: list[Varname]
    materials: list[Varname]
    def __repr__(self):
        return f"{self.__class__.__name__}({self.components}, {self.materials})"

@dataclass(slots=True)
class MaterialzeStarItem:
    @property
    def qname(self):
        return f'{self.component.name}[{self.material.name}]'
    @property
    def start_line(self):
        return self.materialize_star.start.start_line
    @property
    def end_line(self):
        return self.materialize_star.end.end_line
    @property
    def pos(self):
        return self.material.pos

    materialize_star: MaterializeStar
    component: Varname
    material: Varname

