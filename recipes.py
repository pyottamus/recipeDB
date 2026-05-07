from collections.abc import Sequence

from .quantified import Quantified, QuantifiedDict
from .quantified import SemiQuantifiedIterable, quantify_tuple
from .recipeDB_parser_types import TierSpec
from .recipeDB_types import *

__all__ = ["Recipe", "RecipeBase"]


def unify(items):
    sum_items = QuantifiedDict()
    for item in items:
        sum_items.add(item)

    return sum_items.to_tuple()


class RecipeBase:
    products: tuple[Quantified[NamedItemBase], ...]
    items: tuple[Quantified[NamedItemBase], ...]
    station: Station
    tools: tuple[Tool, ...]
    tier: TierSpec
    circuit: int
    dependencies: set[RecipeBase]
    solved: bool

    def clean(self):
        self.solved = False
        self.dependencies = set[RecipeBase]()

    def __repr__(self):
        if len(self.products) == 1:
            products = repr(self.products[0])
        else:
            products = repr(self.products)

        return f"<RecipeBase: {products}>"

    def __eq__(self, other: RecipeBase):
        return self.products == other.products and self.items == other.items and self.station == other.station and self.tools == other.tools and self.tier == other.tier

    def __hash__(self):
        return hash((type(self), self.products, self.items, self.station, self.tools, self.tier, self.station))

    def get_product_count(self, product):
        for item in self.products:
            if item.val == product:
                return item.count
        raise KeyError

    def _init(self, products: tuple[Quantified[NamedItemBase], ...],
              items: tuple[Quantified[NamedItemBase], ...],
              tier: TierSpec,
              circuit: int,
              station: Station,
              tools: tuple[Tool, ...]):
        self.tools = tools
        self.items = unify(items)
        self.tier = tier
        self.circuit = circuit
        self.station = station
        self.products = unify(products)
        self.dependencies = set[RecipeBase]()
        self.solved = False

    def add_dependency(self, recipe: RecipeBase):
        self.dependencies.add(recipe)

    def __init__(self,
                 products: SemiQuantifiedIterable[NamedItemBase] | Quantified[NamedItemBase] | NamedItemBase,
                 items: SemiQuantifiedIterable[NamedItemBase],
                 tier: TierSpec,
                 circuit: int,
                 station: Station,
                 tools: Sequence[Tool] | None):
        if tools is None:
            tools = ()
        else:
            tools = tuple(tools)
        if isinstance(products, NamedItemBase):
            products = (Quantified(1, products),)
        elif isinstance(products, Quantified):
            products = (products,)
        else:
            products = quantify_tuple(products)

        items = quantify_tuple(items)

        station = station
        self._init(products, items, tier, circuit, station, tools)

    def is_main(self, product: Item):
        return self.products[0].val == product

    def __str__(self):
        o = ', '.join(map(str, self.products))

        if self.station != workbench:
            o += f' : {self.station.name}'

        o += ' {\n'

        o += ''.join([f'\t{item}\n' for item in self.items])

        if self.tools:
            o += '\n'
            o += ''.join([f'\t{item}\n' for item in self.tools])
        o += '}'
        return o

    def _get_product(self, target):
        for product in self.products:
            if product.val is target:
                return product
        return None


class Recipe(RecipeBase):
    def __init__(self, products, items, tier: TierSpec, circuit: int, station=workbench, tools=None):
        super().__init__(products, items, tier, circuit, station, tools)


"""
class MaterializedComponentRecipe(RecipeBase):
    @property
    def component(self):
        return self.base.component
    def __init__(self, base, material, products, items, station=workbench):
        super().__init__(products, items, station)
        self.base = base
        self.material = material
        #RecipeDB.add_materialized_recipe(self)
    
class ComponentRecipe:

    @property
    def component(self):
        return self.product.val
    
    def __init__(self, product, items, station=workbench):
        self.product = QuantifiedComponent(product)
        
        self.template_items = []
        self.items = []
        self.station = Station.conv(station)

        self.tools = []
        #print(items)
        for qitem in QuantifiedComponentRecipeItem.list_conv(items):

            count = qitem.count
            item = qitem.val
            if isinstance(item, Tool):
                self.tools.append(qitem)
            elif isinstance(item, Item):
                self.items.append(qitem)
            else:
                self.template_items.append(qitem)

        #RecipeDB.add_component_recipe(self)
    def _materialize(self, material):
        return MaterializedComponentRecipe(self, material, [self.product.count * self.product.val[material]], [x.count * x.val[material] for x in self.template_items] + self.items, self.station)
    def __getitem__(self, key):
        material = Material.conv(RecipeDB.get_material(key))
        #if (ret := RecipeDB.get_materialized_recipe(self.product, material)) is not None:
        #    return ret
        ret = self._materialize(material)
        return ret
"""
