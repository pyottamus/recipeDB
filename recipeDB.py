#from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar
from collections.abc import Sequence
import inspect
from .recipeDB_parser_types import *

from collections import defaultdict
from .quantified import dequantify, QuantifiedDict, Quantified, quantify

from .recipeDB_types import *
from .recipeDB_conv import *
from .recipes import *
from .recipeLexer import *
from functools import wraps
from typing import TypeVar

T = TypeVar("T")

class RecipeDB:
    _sym_table: dict[str, Symbol]
    __slots__ = ("materials", "components", "materialized_components", "_sym_table", "generalized_items", "named_items",
                 "tools", "stations", "recipes", "component_recipes", "materialized_recipes", "fdeps", "rdeps",
                 "fdeps_template", "rdeps_template", "template_deps", "clean", "_item_list", 'disalowed_comp_mat',
                 'prev_decl', 'fluids')

 
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
            raise TypeError(f"Cannot create {typ.__name__}({key!r}):\n\t{key!r} already defined as a {type(ret).__name__}.")
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
                    
    def _add_usym(self, item):
        #self.unitary.add(item)
        self._add_sym(item)

    def add_sym(self, sym):
        if (prev_decl := self._sym_table.get(sym.name)) is not None:
            raise RedeclarationError(f"Symbol '{sym.qname}' of type {sym.__class__.__name__} already in use as type {prev_decl.__class__.__name__}", sym.qname)
        if isinstance(sym, (Item, Component)):
            return self._add_usym(sym)
        return self._add_sym(sym)
    

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

    def add_recipe(self, recipe):
        self.clean = False
        self.recipes[recipe.products[0].val].append(recipe)


        #for item in recipe.items:
            #if isinstance(item.val, MaterializedComponent):
                #self.ensure_materialized_recipies(item.val)

    def key_get_named_item(self, key):
        return self._get_sym_checked(key, NamedItem)

    def get_named_item(self, key):
        if isinstance(key, NamedItem):
            return key

        return self.named_items.get(key)


    def key_get_station(self, key):
        return self.stations.get(key)

    def get_station(self, key):
        if isinstance(key, Station):
            return key

        return self.stations.get(key)

    def add_fluid(self, name: Varname):

        if (sym := self.get_sym(name.name)) is not None:

            if isinstance(sym, Material):
                val = MaterializedFluid(sym)
                if val.qname in self._sym_table:
                    raise RedeclarationError(f"Redeclaration of MaterializedFluid {val.qname!r}", val.qname)
            else:
                raise SymbolTypeError(f"Symbol {name.name!r} already exists as type {sym.__class__.__name__}. Attempted redeclaration as fluid", sym, MaterializedFluid)
        else:
            val = NamedFluid(name.name)

        self._sym_table[val.qname] = val
        self.fluids[val.qname] = val
        self.prev_decl[val.qname] = name
    def resovle_type(self, name: str, expected_type: type[T]) -> T:
        x = self.get_sym(name)
        if x is None:
            raise UndefinedSymbolError(f"Undefined symbol {name}", name)
        if not isinstance(x, expected_type):
            raise SymbolTypeError(f"Symbol {name} is not a {expected_type.__name__}, but a {x.__class__.__name__}", expected_type,
                                  x.__class__)
        return x
    def resolve_component(self, name: str) -> Component:
        return self.resovle_type(name, Component)
    def resolve_station(self, name: str) -> Station:
        return self.resovle_type(name, Station)
    def resolve_material(self, name: str) -> Material:
        return self.resovle_type(name, Material)
    def resolve_materialized_component(self, name: str) -> MaterializedComponent:
        return self.resovle_type(name, MaterializedComponent)

    def get_generalized_item(self, key):
        if isinstance(key, GeneralizedItem):
            return key
        elif isinstance(key, str):
            return self.generalized_items.get(key)
        return None

    
    def get_specified_component(self, component: str | Component, material: str | Material):
        if isinstance(component, str):
            component = self.components[component]

        if isinstance(material, str):
            material = self.materials[material] 
        
        if (part := self.materialized_components.get(component)) is None:
            return None
        return part.get(material)
    @wraps(Recipe.__init__)
    def createRecipe(self, *args, **kwargs):
        recipe = Recipe(*args, **kwargs)
        self.add_recipe(recipe)
        return recipe
    def get_specified_component_items(self):
        return [x for y in self.materialized_components.values() for x in y.values()]

    def get_named_items(self):
        return list(self.named_items.values())

    def get_generalized_items(self):
        return list(self.generalized_items.values())

    def get_stations(self):
        return list(self.stations.values())
    def get_tools(self):
        return list(self.tools.values())
    
    def __init__(self):
        self.materials = {}
        self.components = {}
        self.stations = {}
        self.materialized_components = defaultdict(dict)
        self.generalized_items = {}
        self.named_items = {}
        self.tools = {}
        self.stations = {}
        self.recipes = defaultdict(list)
        self.component_recipes = defaultdict(list)
        self.materialized_recipes = defaultdict(lambda: defaultdict(list))
        self._sym_table = {}

        self.fdeps = {}
        self.rdeps = defaultdict(list)
        self.template_deps = {}
        self.fdeps_template = {}
        self.rdeps_template = defaultdict(list)
        
        self.clean = False
        self.disalowed_comp_mat = {}
        self._item_list = []

        self.add_sym(workbench)
        self.add_sym(fluid)
        self.prev_decl = {}
        self.fluids = {}
    def is_unit(self, item):
        return self.recipes.get(item) is None
    def get_items(self):
        return self.get_named_items() + self.get_specified_component_items() + self.get_generalized_items()
    def items_partitioned(self):
        return
    
    def get_sym(self, key: str) -> Symbol:
        return self._sym_table.get(key)

    def get_item(self, key):
        if isinstance(key, Item):
            return key

        if (ret := self.get_specified_component(key)) is not None:
            return ret
        elif (ret := self.get_generalized_item(key)) is not None:
            return ret
        elif (ret := self.get_named_item(key)) is not None:
            return ret
        return None

    def get_component_recipes(self, item):
        return self.component_recipes.get(item)

    def get_component_recipe(self, item):
        val = self.get_component_recipes(item)
        if val is not None and len(val):
            return val[0]
        return None
    
    def pick_best_recipe(self, recipes, target, count):
        if recipes is None or not recipes:
            return None

        if count is None:
            return recipes[0]

        count = [(recipe._get_product(target).count, recipe) for recipe in recipes]
        rounded_mul = [(((count + c - 1) // c), c, recipe) for c, recipe in count]
        rounded_rem = [((c * m) - count, m, recipe) for m, c, recipe in rounded_mul]
        rounded_rem.sort()
        return Quantified(rounded_rem[1], rounded_rem[2])
                
    def make_materialized_recipes(self, component, material):
        if (recipes := self.get_component_recipes(component)) is None:
            return None
        ret = [recp._materialize(material) for recp in recipes]
        return ret
    def _materialize(self, recipe, materials):

        out = []
        component = recipe.component
        for mat in materials:
            if (recipes := self.get_materialized_recipes(component, mat)) is not None:
                hit = False
                for rec in recipes:
                    if rec.base is recipe:
                        hit = True
                        out.append(rec)
                        break
                if hit:
                    continue

            # create new recipe
            rec = recipe._materialize(mat)
            out.append(rec)
            self.add_materialized_recipe(rec)
        return out
    def materialize(self, recipe, material, *materials):
        return self._materialize(recipe, [material, *materials])
    
    def make_materialized_recipe(self, component, material, count):
        if (recipes := self.make_materialized_recipes(component, material)) is None:
            return None

        return self.pick_best_recipe(recipes, component[material], count)

    def ensure_materialized_recipies(self, specified_component):
        self.make_materialized_recipes(specified_component.component, specified_component.material)

    def get_materialized_recipes(self, component, material):
        if (ret := self.materialized_recipes.get(component)) is not None:
            if (ret := ret.get(material)) is not None:
                return ret
        #return self.make_materialized_recipes(component, material)

    def get_materialized_recipe(self, component, material):
        component, count = dequantify(component)
        #if isinstance(component, Quantified):
        #    count = component.count
        #    component = component.val
        #else:
        #    count = None
        recipes = self.get_materialized_recipes(component, material)
        if recipes is None or len(recipes) == 0:
            return None
        return self.pick_best_recipe(recipes, component[material], count)

    def get_recipes(self, recipe):
        recipe, _ = dequantify(recipe)
        #if isinstance(recipe, Quantified):
        #    recipe = recipe.val
        
        if isinstance(recipe, (Recipe, ComponentRecipe)):
            return [recipe]
        
        if isinstance(recipe, str):
            recipe = self._sym_table[recipe]
            
        if isinstance(recipe, Component):
            return self.component_recipes.get(recipe)
        elif isinstance(recipe, MaterializedComponent):
            return self.get_materialized_recipes(recipe.component, recipe.material)
        elif isinstance(recipe, Item):
            return self.recipes.get(recipe)
        else:
            return None
    """
    def _normalize_get_recipe(self, product):
        count = None
        if isinstance(product, Quantified):
            product = product.val
            count = product.count
        return count, ComponentProductItem(product)
    """
    def lookup_materialized_component(self, component: Component | str, material: Material | str) -> MaterializedComponent:
        if isinstance(component, str):
            component = self.resolve_component(component)
            if component is None:
                raise ValueError(f"Undefined component {component!r}")
        if isinstance(material, str):
            material = self.resolve_material(material)
            if material is None:
                raise ValueError(f"Undefined material {material!r}")
        qname = f'{component.name}[{material.name}]'
        ret = self._sym_table.get(qname)
        if ret is None or not isinstance(ret, MaterializedComponent):
            raise ValueError(f"Undefined MaterializedComponent {qname!r}")
        return ret
    def get_recipe(self, product):
        count = None
        
        #if isinstance(product, (Recipe, ComponentRecipe)):
            
        if isinstance(product, str):
            product = self._sym_table[product]

        
        if isinstance(product, Quantified):
            product = product.val
            count = product.count
        else:
            count = None
        if isinstance(product, Recipe):
            return product

        if (ret := self.recipes.get(product)) is None:
            return None
        else:
            return ret[-1]
    def load_symbols(self):
        locals = inspect.currentframe().f_back.f_locals
        for name, symbol in self._sym_table.items():
            if "[" in name:
                continue
            if name in locals:
                continue
            locals[name] = symbol

    def _mk_cls(self, cls, dst, *args):

        for name in args:
            val = cls(name)
            self.add_sym(val)

    def mk_materials(self, *args):
        self._mk_cls(Material, 'material', *args)

    def add_material(self, varname: Varname):
        self._mk_cls(Material, 'material', varname.name)
        self.prev_decl[varname.name] = varname
    def add_materialized_component(self, materialized_varname: MaterializedVarname):
        component = self.resolve_component(materialized_varname.name)
        material = self.resolve_material(materialized_varname.material)



        val = MaterializedComponent(component, material)
        self.add_sym(val)
        self.prev_decl[f'{materialized_varname.name}[{materialized_varname.material}]'] = materialized_varname

    def add_materialized_star_item(self, component: Component, material: Material, item: MaterialzeStarItem):
        val = MaterializedComponent(component, material)
        self.add_sym(val)
        self.prev_decl[item.qname] = item



    def mk_components(self, *args):
        self._mk_cls(Component, 'component', *args)

    
    def mk_generalized(self, *args):
        self._mk_cls(GeneralizedItem, 'generalized_item', *args)



    def mk_named(self, *args):
        self._mk_cls(NamedItem, 'named_item', *args)

    def add_named(self, varname: Varname):
        self._mk_cls(NamedItem, 'named_item', varname.name)

        self.prev_decl[varname.name] = varname
    def get_or_mk_tool(self, name):
        if (ret := self.tools.get(name)) is not None:
            return ret
        else:
            ret = Tool(name)
            self.add_sym(ret)
            return ret
    def mk_tool(self, name: str):
        val = Tool(name)
        self.add_sym(val)
        return val
    def add_tool(self, varname: Varname):
        val = Tool(varname.name)
        self.add_sym(val)
        self.prev_decl[varname.name] = varname
    def mk_tools(self, *args):
        self._mk_cls(Tool, 'tool', *args)

    def mk_stations(self, *args):
        self._mk_cls(Station, 'station', *args)

    def add_station(self, varname: Varname):
        self._mk_cls(Station, 'station', varname.name)
        self.prev_decl[varname.name] = varname
    def add_component(self, varname: Varname):
        self._mk_cls(Component, 'component', varname.name)
        self.prev_decl[varname.name] = varname
    
