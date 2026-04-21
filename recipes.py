from .recipeDB_parser_types import TierSpec
from .recipeDB_types import *
from .recipeDB_conv import *
from .quantified import QuantifiedDict

def seperate_tools(items):
    real_items = []
    tools = []

    for item in QuantifiedRecipeItem.list_conv(items):
        if isinstance(item.val, Tool):
            tools.append(item)
        else:
            real_items.append(item)

    return real_items, tools

def unify(items):
    sum_items = QuantifiedDict()
    for item in items:
        sum_items.add(item)
    
    return sum_items.to_list()
class RecipeBase:
    def get_product_count(self, product):
        for item in self.products:
            if item.val == product:
                return item.count
        raise KeyError
    @classmethod
    def _direct_init(cls, products, items, station, tools):
        self = super().__new__(cls)
        self._init(products, items, station, tools)
        return self
    def _init(self, products: list[Quantified[NamedItemBase]],
              items: list[Quantified[NamedItemBase]], tier: TierSpec,
              station: Station, tools: list[Tool]):
        self.tools = tools
        self.items = unify(items)
        self.tier = tier
        self.station = station
        self.products = unify(products)

    def __init__(self, products: list[Quantified[NamedItemBase]],
                 items: list[Quantified[NamedItemBase]],
                 tier: TierSpec,
                 station,
                 tools: list[Tool]):
        products = products
        station = station
        self._init(products, items, tier, station, tools)

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
    def __init__(self, products, items, tier: TierSpec, station=workbench, tools=None):
        super().__init__(products, items, tier, station, tools)
        #RecipeDB.add_recipe(self)

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

