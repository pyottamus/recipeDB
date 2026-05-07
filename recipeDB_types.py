from .quantified import QuantifiedMixin
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .recipeDB_parser_types import QuantifiedValue, TierSpec

__all__ = ["Item", "NamedResource", "Material", "Component", "fluid", "NamedItemBase", "MaterializedComponent",
           "GeneralizedItem", "NamedItem", "FluidBase", "NamedFluid", "MaterializedFluid", "Tool", "Station",
           "workbench", "Symbol", "NotAMaterializedFluidError", "NotAFluidError", "UndefinedSymbolError",
           "SymbolTypeError", "RedeclarationError", "QuantifiedToolError", "CircuitedTieredStation", "hand",
           "NullStation"
          ]
class NameStrMixin:
    __slots__ = ()
    def __str__(self):
        return self.name
    def __repr__(self):
        return f'{type(self).__name__}({self.name})'


        
@dataclass(slots=True, frozen=True, repr=False)
class Item(QuantifiedMixin):
    @property
    def fluid(self):
        return False

@dataclass(slots=True, frozen=True, repr=False)
class NamedResource(NameStrMixin):
    name: str
    @property
    def qname(self) -> str:
        return self.name
    @staticmethod
    def _check_name(name: Any) -> bool:
        if not isinstance(name, str):
            return False
        if name.isidentifier():
            return True

        if name[-1] == ']':
            prefix, suffix = name[:-1].split('[', 1)
            return prefix.isidentifier() and suffix.isidentifier()
        else:
            return False
    @property
    def fluid(self) -> bool:
        return False

    def __lt__(self, other: NamedResource):
        return self.qname < other.qname
    def __eq__(self, other):
        if not isinstance(other, NamedResource):
            return NotImplemented
        return other.name == self.name
    def __hash__(self):
        return hash((type(self), self.name))
    @classmethod
    def conv(cls, key):
        if isinstance(key, cls):
            return key
        elif isinstance(key, str):
            return cls(key)
        else:
            raise TypeError(type(key))

    def __init__(self, name: str):
        if not self._check_name(name):
            if not isinstance(name, str):
                raise TypeError
            raise ValueError(f"name '{name}' is not a valid identifier")
        object.__setattr__(self, "name", name)
class Material(NamedResource):
    __slots__ = ()
class Component(NamedResource):
    __slots__ = ()
    @property
    def qname(self) -> str:
        return self.name
    def __getitem__(self, material: str | Material):
        #rdb = CRecipeDB.get()
        if isinstance(material, str):
            material = Material(material)
        ret = MaterializedComponent(self, material)
        #rdb.add_specified_component(ret)
        return ret

fluid = Component('fluid')

@dataclass(slots=True, frozen=True, repr=False)
class NamedItemBase(NamedResource, Item):
    def __lt__(self, other):
        if isinstance(other, NamedItemBase):
            return self.name < other.name
        return NotImplemented





@dataclass(slots=True, frozen=True, repr=False)
class MaterializedComponent(NamedItemBase):
    component: Component
    material: Material
    def __init__(self, component: Component, material: Material):
        object.__setattr__(self, "component", component)
        object.__setattr__(self, "material", material)
        super().__init__(str(self))
    @property
    def qname(self) -> str:
        return f"{self.component.name}[{self.material.name}]"
    def __lt__(self, other):
        if isinstance(other, MaterializedComponent):
            if self.component == other.component:
                return self.material.name < other.material.name
            return self.component.name < other.component.name
        elif isinstance(other, NamedItemBase):
            return self.qname < other.qname
        return NotImplemented
    def __gt__(self, other):
        if isinstance(other, MaterializedComponent):
            if self.component == other.component:
                return self.material.name > other.material.name
            return self.component.name > other.component.name
        elif isinstance(other, NamedItemBase):
            return self.qname > other.qname
        return NotImplemented
    def __str__(self):
        return f'{self.component.name}[{self.material.name}]'
    def __repr__(self):
        return str(self)

class GeneralizedItem(NamedItemBase):
    __slots__ = ()

class NamedItem(NamedItemBase):

    @property
    def qname(self) -> str:
        return f"{self.name}"
    def __repr__(self):
        return self.name
@dataclass(slots=True, repr=False, frozen=True)
class FluidBase(NamedItemBase):
    @property
    def fluid(self):
        return True
@dataclass(slots=True, repr=False, frozen=True)
class NamedFluid(FluidBase):
    pass
@dataclass(slots=True, repr=False, frozen=True)
class MaterializedFluid(FluidBase):
    component: Component
    material: Material
    @property
    def qname(self) -> str:
        return f"fluid[{self.material.name}]"
    def __repr__(self) -> str:
        return f"{type(self).__name__}[{self.material.name}]"
    def __init__(self, material: Material):
        object.__setattr__(self, 'component', fluid)
        object.__setattr__(self, 'material', material)
        super().__init__(self.qname)



class Tool(NamedResource):
    __slots__ = ()

class Station(NamedResource):
    __slots__ = ()

    @classmethod
    def NullStationInit(cls):
        s = cls.__new__(cls)
        object.__setattr__(s, "name", "")
        return s

workbench = Station('workbench')
hand = Station("hand")
NullStation = Station.NullStationInit()

type Symbol = Tool | Station | Component | MaterializedComponent | NamedItem | MaterializedFluid | NamedFluid

class NotAMaterializedFluidError(ValueError):
    __slots__ = "quantified_fluid"
    def __init__(self, msg: str, quantified_fluid: QuantifiedValue):
        super().__init__(msg)
        self.quantified_fluid = quantified_fluid
class NotAFluidError(ValueError):
    __slots__ = "quantified_fluid", "hit_symbol"
    def __init__(self, msg: str, quantified_fluid: QuantifiedValue, hit_symbol: Symbol):
        super().__init__(msg)
        self.quantified_fluid = quantified_fluid
        self.hit_symbol = hit_symbol

class UndefinedSymbolError(ValueError):
    __slots__ = "symbol_name",
    def __init__(self, msg, symbol_name: str):
        super().__init__(msg)
        self.symbol_name = symbol_name
class SymbolTypeError(TypeError):
    __slots__ = "expected_type", "got_type"
    def __init__(self, msg: str, expected_type, got_type):
        super().__init__(msg)
        self.expected_type = expected_type
        self.got_type = got_type


class RedeclarationError(ValueError):
    __slots__ = 'symbol_name',
    def __init__(self, msg: str, symbol_name: str):
        super().__init__(msg)
        self.symbol_name = symbol_name

class QuantifiedToolError(ValueError):
    __slots__ = "tool_name",
    def __init__(self, msg: str, tool_name: str):
        super().__init__(msg)
        self.tool_name = tool_name

@dataclass(slots=True, frozen=True, order=True)
class CircuitedTieredStation:
    station: Station
    tier: TierSpec
    circuit: int = 0
    def __str__(self):
        if self.circuit != 0:
            circuit_spec = f"<{self.circuit}>"
        else:
            circuit_spec = ""

        return f"{self.tier.name} {self.station.name}{circuit_spec}"
    def __init__(self, station: Station, tier: TierSpec, circuit: int=0):
        if not isinstance(circuit, int):
            raise TypeError(f"Circuit must be an integer, not {type(circuit)}")
        if circuit > 24 or circuit < 0:
            raise RuntimeError(f"Invalid circuit {circuit}")
        object.__setattr__(self, 'station', station)
        object.__setattr__(self, 'tier', tier)
        object.__setattr__(self, 'circuit', circuit)
    def __repr__(self):
        ret = f"{type(self).__name__}(station={self.station.name}, tier={self.tier.name}"
        if self.circuit != 0:
            ret += f", circuit={self.circuit})"
        else:
            ret += ")"
        return ret