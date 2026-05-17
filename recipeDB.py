import inspect
from collections import defaultdict
from collections.abc import Sequence, Set

from multimethod import multimethod

from .quantified import QuantifiedDict, quantify_tuple
from .recipeDB_parser_types import *
from .recipeDB_types import *
from .recipes import *
from .solver import RecipeSolver, Itemizer2

__all__ = ["RecipeDB", "prev_decl_type"]
type prev_decl_type = MaterializeStarItem | Varname | MaterializedVarname | Implicit
type input_list = NamedItemBase | \
                  Quantified[NamedItemBase] | \
                  Sequence[NamedItemBase | Quantified[NamedItemBase]] | \
                  Set[NamedItemBase | Quantified[NamedItemBase]] | \
                  QuantifiedDict[NamedItemBase]


def _conv_input_list(inp: input_list) -> tuple[Quantified[NamedItemBase], ...]:
    if isinstance(inp, NamedItemBase):
        inp = [inp]
    elif isinstance(inp, Quantified):
        inp = [inp]

    if isinstance(inp, (Sequence, Set)):
        return quantify_tuple(inp)
    elif isinstance(inp, QuantifiedDict):
        return inp.to_tuple()
    else:
        raise TypeError(type(inp))


class RecipeDB:
    _sym_table: dict[str, Symbol]
    __slots__ = ("materials", "components", "materialized_components", "_sym_table", "named_items",
                 "tools", "stations", "recipes", "clean", "solved", "prev_decl", "fluids")

    materials: dict[str, Material]
    components: dict[str, Component]
    materialized_components: defaultdict[Component, dict[Material, MaterializedComponent]]
    _sym_table: dict[str, Symbol]
    named_items: dict[str, NamedItem]
    tools: dict[str, Tool]
    stations: dict[str, Station]
    recipes: defaultdict[Item, list[Recipe]]
    fluids: dict[str, FluidBase]
    prev_decl: dict[str, prev_decl_type]
    typ_index = {Tool: 0,
                 Station: 1,
                 NamedItem: 2,
                 GeneralizedItem: 3,
                 Material: 4,
                 Component: 5,
                 MaterializedComponent: 6
                 }

    tbl_map = {Tool: 'tools',
               Station: 'stations',
               NamedItem: 'named_items',
               GeneralizedItem: 'generalized_items',
               Material: 'materials',
               Component: 'components',
               MaterializedComponent: 'materialized_components'
               }
    dst_map = {Tool: 'tools',
               Station: 'stations'
               }

    def __init__(self):
        self.materials = {}
        self.components = {}
        self.stations = {}
        self.materialized_components = defaultdict(dict)
        # self.generalized_items = {}
        self.named_items = {}
        self.tools = {}
        self.stations = {}
        self.recipes = defaultdict(list)
        # self.component_recipes = defaultdict(list)
        # self.materialized_recipes = defaultdict(lambda: defaultdict(list))
        self._sym_table = {}

        # self.fdeps = {}
        # self.rdeps = defaultdict(list)
        # self.template_deps = {}
        # self.fdeps_template = {}
        # self.rdeps_template = defaultdict(list)

        self.clean = False
        self.solved = False
        # self.disalowed_comp_mat = {}
        # self._item_list = []

        self.add_sym(workbench)
        self.add_sym(fluid)
        self.prev_decl = {}
        self.fluids = {}

    def conv(self, key, typ):
        if isinstance(key, typ):
            return key
        elif isinstance(key, str):
            loc = self.dst_map[typ]
            src = getattr(self, loc)
            return src.get(key)
        return None

    def _get_sym_checked(self, key, typ):
        if (ret := self._sym_table.get(key)) is None:
            return None
        elif type(ret) is not typ:
            raise TypeError(
                f"Cannot create {typ.__name__}({key!r}):\n\t{key!r} already defined as a {type(ret).__name__}.")
        else:
            return ret

    def _add_sym(self, sym):
        key = sym.name
        if isinstance(sym, MaterializedComponent):
            self.materialized_components[sym.component][sym.material] = sym
        else:
            dst = self.tbl_map[type(sym)]
            dst = getattr(self, dst)
            dst[key] = sym
        self._sym_table[key] = sym

    def add_sym(self, sym):
        if (prev_decl := self._sym_table.get(sym.qname)) is not None:
            raise RedeclarationError(
                f"Symbol '{sym.qname}' of type {type(sym).__name__} already in use as type {type(prev_decl).__name__}",
                sym.qname)

        return self._add_sym(sym)

    """
    def add_materialized_recipe(self, materialized_recipe):
        self.clean = False
        
        component = materialized_recipe.component
        material = materialized_recipe.material

        #self.unitary.discard(component)
        #self.unitary.discard(component[material])
        
        self.materialized_recipes[component][material].append(materialized_recipe)

    def add_component_recipe(self, crecipe):
        self.clean = False
        #self.unitary_specified_component.pop(crecipe.product.val, None)
        #self.unitary_component.discard(crecipe.product.val)
        self.component_recipes[crecipe.product.val].append(crecipe)
    """

    def add_recipe(self, recipe):
        self.clean = False
        self.recipes[recipe.products[0].val].append(recipe)

        # for item in recipe.items:
        # if isinstance(item.val, MaterializedComponent):
        # self.ensure_materialized_recipies(item.val)

    def get_named_item(self, key: str | NamedItem):
        if isinstance(key, NamedItem):
            return key
        return self.named_items.get(key)

    def get_station(self, key: str | Station):
        if isinstance(key, Station):
            return key

        return self.stations.get(key)

    def add_materialized_fluid2(self, material: Material, prev_decl: prev_decl_type) -> MaterializedFluid:
        val = MaterializedFluid(material)
        self._sym_table[val.qname] = val
        self.fluids[val.qname] = val
        self.prev_decl[val.qname] = prev_decl
        self.clean = False
        return val

    def add_named_fluid2(self, name: str, prev_decl: prev_decl_type) -> NamedFluid:
        val = NamedFluid(name)
        self._sym_table[name] = val
        self.fluids[name] = val
        self.prev_decl[name] = prev_decl
        self.clean = False
        return val

    def add_prefix_fluid(self, name: Varname):

        if (sym := self.get_sym(name.name)) is not None:

            if isinstance(sym, Material):
                val = MaterializedFluid(sym)
                if val.qname in self._sym_table:
                    raise RedeclarationError(f"Redeclaration of MaterializedFluid {val.qname!r}", val.qname)
            else:
                raise SymbolTypeError(
                    f"Symbol {name.name!r} already exists as type {type(sym).__name__}. Attempted redeclaration as fluid",
                    sym, MaterializedFluid)
        else:
            val = NamedFluid(name.name)

        self._sym_table[val.qname] = val
        self.fluids[val.qname] = val
        self.prev_decl[val.qname] = name
        self.clean = False

    def resovle_type[T](self, name: str, expected_type: type[T]) -> T:
        x = self.get_sym(name)
        if x is None:
            raise UndefinedSymbolError(f"Undefined symbol {name}", name)
        if not isinstance(x, expected_type):
            raise SymbolTypeError(f"Symbol {name} is not a {expected_type.__name__}, but a {type(x).__name__}",
                                  expected_type,
                                  type(x))
        return x

    def resolve_component(self, name: str) -> Component:
        return self.resovle_type(name, Component)

    def resolve_station(self, name: str) -> Station:
        return self.resovle_type(name, Station)

    def resolve_material(self, name: str) -> Material:
        return self.resovle_type(name, Material)

    def resolve_materialized_component(self, name: str) -> MaterializedComponent:
        return self.resovle_type(name, MaterializedComponent)

    def resolve_tool(self, name: str) -> Tool:
        return self.resovle_type(name, Tool)

    def resolve_named_item(self, name: str) -> NamedItem:
        return self.resovle_type(name, NamedItem)

    def resolve_fluid(self, name: str) -> FluidBase:
        return self.resovle_type(name, FluidBase)

    def resolve_item(self, name: str):
        return self.resovle_type(name, Item)

    def get_specified_component(self, component: str | Component, material: str | Material):
        if isinstance(component, str):
            component = self.resolve_component(component)

        if isinstance(material, str):
            material = self.resolve_material(material)

        if (part := self.materialized_components.get(component)) is None:
            raise
        return part.get(material)

    def get_named_items(self) -> list[NamedItem]:
        return list(self.named_items.values())

    def get_materialized_components(self) -> list[MaterializedComponent]:
        return [x for y in self.materialized_components.values() for x in y.values()]

    def get_items(self) -> list[NamedItem | MaterializedComponent]:
        return self.get_named_items() + self.get_materialized_components()

    def get_stations(self):
        return list(self.stations.values())

    def get_tools(self):
        return list(self.tools.values())

    def is_unit(self, item: Item | Quantified[Item]):
        if isinstance(item, Quantified):
            item = item.val
        return self.recipes.get(item) is None

    def get_sym(self, key: str) -> Symbol | None:
        return self._sym_table.get(key)

    def get_item(self, key: Item | str):
        if isinstance(key, Item):
            return key

        item = self._sym_table.get(key)
        if item is None:
            return None
        if not isinstance(item, Item):
            raise SymbolTypeError(f"Symbol {key!r} is not a {Item.__name__}", Item, type(key))
        return item

    def get_recipe(self, product: str | Item | Quantified[Item] | RecipeBase) -> RecipeBase | None:
        # if isinstance(product, (Recipe, ComponentRecipe)):
        if isinstance(product, RecipeBase):
            return product
        elif isinstance(product, str):
            product = self.resolve_item(product)
        elif isinstance(product, Item):
            product = product
        elif isinstance(product, Quantified):
            product = product.val

        if (ret := self.recipes.get(product)) is None:
            return None
        else:
            return ret[-1]

    def load_symbols(self, clobber=False):
        locals = inspect.currentframe().f_back.f_locals
        for name, symbol in self._sym_table.items():
            if "[" in name:
                # symbol is a MaterializedComponent
                continue
            if name in locals and not clobber:
                continue
            locals[name] = symbol

    def add_material2(self, name: str, prev_decl: prev_decl_type) -> Material:
        val = Material(name)
        self.add_sym(val)
        self.prev_decl[name] = prev_decl
        self.clean = False
        return val

    def add_material(self, varname: Varname):
        return self.add_material2(varname.name, varname)

    def add_materialized_component2(self, component: Component, material: Material,
                                    prev_decl: prev_decl_type) -> MaterializedComponent:
        val = MaterializedComponent(component, material)
        self.add_sym(val)
        self.prev_decl[val.qname] = prev_decl
        self.clean = False
        return val

    @multimethod
    def add_materialized_component(self, materialized_varname: MaterializedVarname, component: Component,
                                   material: Material) -> MaterializedComponent:
        return self.add_materialized_component2(component, material, materialized_varname)

    @multimethod
    def add_materialized_component(self, materialized_varname: MaterializedVarname) -> MaterializedComponent:
        component = self.resolve_component(materialized_varname.name)
        material = self.resolve_material(materialized_varname.material)

        return self.add_materialized_component(materialized_varname, component, material)

    def add_materialized_star_item(self, component: Component, material: Material,
                                   item: MaterializeStarItem) -> MaterializedComponent:
        val = MaterializedComponent(component, material)
        self.add_sym(val)
        self.prev_decl[item.qname] = item
        self.clean = False
        return val

    def add_named_item2(self, name: str, prev_decl: prev_decl_type) -> NamedItem:
        val = NamedItem(name)
        self.add_sym(val)
        self.prev_decl[name] = prev_decl
        self.clean = False
        return val

    def add_named_item(self, varname: Varname) -> NamedItem:
        return self.add_named_item2(varname.name, varname)

    def add_tool(self, varname: Varname) -> Tool:
        val = Tool(varname.name)
        self.add_sym(val)
        self.prev_decl[varname.name] = varname
        self.clean = False
        return val

    def add_station2(self, name: str, prev_decl: prev_decl_type) -> Station:
        val = Station(name)
        self.add_sym(val)
        self.prev_decl[name] = prev_decl
        self.clean = False
        return val

    def add_station(self, varname: Varname) -> Station:
        return self.add_station2(varname.name, varname)

    def add_component2(self, name: str, prev_decl: prev_decl_type) -> Component:
        val = Component(name)
        self.add_sym(val)
        self.prev_decl[name] = prev_decl
        self.clean = False
        return val

    def add_component(self, varname: Varname) -> Component:
        return self.add_component2(varname.name, varname)

    def _clean(self):
        for recipe_list in self.recipes.values():
            for recipe in recipe_list:
                recipe.clean()
        self.clean = True

    def _solve(self):
        RecipeSolver(self, self.get_items())
        self.solved = True

    def solve(self):
        if self.clean and self.solved:
            # clean and solved, no solving nessasary
            return
        elif not self.clean and self.solved:
            self._clean()
            self._solve()
        elif self.clean and not self.solved:
            # clean and never solved. just do a solve
            self._solve()
        elif not self.clean and not self.solved:
            # not clean, but never solved. no need to do a clean.
            self._solve()

    def calc(self, to_build: input_list, prebuilt: input_list = None) -> Itemizer2:
        # self.solve()
        # solve not nessasary since this function calls itemize whichs calls solve
        if prebuilt is not None:
            prebuilt = _conv_input_list(prebuilt)

        itemizer = self.itemize(to_build)
        return itemizer.solve(prebuilt)

    def itemize(self, to_build: input_list) -> Itemizer2:
        self.solve()

        to_build = _conv_input_list(to_build)

        fake_item = Item()
        fake_recipe = RecipeBase([Quantified(1, fake_item)], to_build, TierSpec.ULV,
                                 0, NullStation, [])
        return Itemizer2(fake_recipe, self)
#TODO Add tier-restricted solving and get_recipe
