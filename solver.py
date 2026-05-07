import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Sequence, Set

from multimethod import multimethod

from .quantified import quantify_list, QuantifiedDict, Quantified
from .recipeDB import *
from .recipeDB_parser_types import TierSpec
from .recipeDB_types import *
from .recipe_graph import *
from .recipes import *

__all__ = ["RecipeSolver", "Solver", "ItemizerResult2", "ItemizerResult", "Itemizer2", "Itemizer"]
type prebuilt_type = QuantifiedDict[NamedItemBase] | Sequence[Quantified[NamedItemBase] | NamedItemBase] | None


def ceil_round(a, b):
    return ((a + b - 1) // b) * b


def digit_len(num: int):
    """Length of string form of number. Assumes num is positive integer"""
    if num < 0:
        raise ValueError(f"Expected positive integer, got {num}")
    if num == 0:
        return 1
    else:
        return math.floor(math.log10(num) + 1)


def print_list(lst: Sequence[Any], sort=True, pre_tab=0, empty_text="*NONE*"):
    if len(lst) == 0:
        print(empty_text)
        return
    if sort:
        lst = sorted(lst)
    for item in lst:
        print(f'{"\t" * pre_tab}{item}')


def normal_print_tbl(item_table: QuantifiedDict[Item], sort=True, pre_tab=0, empty_text="*NONE*"):
    if len(item_table) == 0:
        print(empty_text)
        return

    if isinstance(item_table, QuantifiedDict):
        item_table = item_table.to_list()
        if sort:
            item_table.sort()
    else:
        print(item_table)
        raise RuntimeError

    out = []
    max_len = 0
    max_digit_len = 1

    for item in item_table:
        item_name = str(item.val)
        max_len = max(max_len, len(item_name))
        count = item.count_repr

        max_digit_len = max(max_digit_len, len(count))
        out.append((item_name, count))

    pad = ceil_round(max_len + 4, 4)
    dpad = max_digit_len
    dpad += 1
    dpad = ceil_round(dpad, 4)
    for item, count in out:
        print(f'{"\t" * pre_tab}{item:{pad}}{count:>{dpad}}')


def print_double_wide_table(item_table: Sequence[tuple[NamedItemBase, int, int]], sort=True, pre_tab=0,
                            empty_text="*NONE*"):
    if len(item_table) == 0:
        print(empty_text)
        return
    if sort:
        item_table = sorted(item_table)

    out = []
    max_len = 0
    max_digit_len = 1
    for item, wanted_produced, prebuilt in item_table:
        item_name = str(item)
        max_len = max(max_len, len(item_name))
        count_wanted = Quantified(wanted_produced, item).count_repr
        count_prebuilt = Quantified(prebuilt, item).count_repr

        max_digit_len = max(max_digit_len, len(count_wanted))
        out.append((item_name, count_wanted, count_prebuilt))
    pad = ceil_round(max_len + 4, 4)
    dpad = max_digit_len
    dpad += 1
    dpad = ceil_round(dpad, 4)
    for item, count_wanted, count_prebuilt in out:
        print(f'{"\t" * pre_tab}{item:{pad}}{count_wanted:>{dpad}}\t{count_prebuilt}')


class OrderedSet[T]:
    __slots__ = "_set",
    _set: dict[T, None]

    def __init__(self):
        self._set = {}

    def insert(self, value: T):
        self._set[value] = None

    def __contains__(self, value: T):
        return value in self._set

    @property
    def set(self):
        return tuple(self._set.keys())


class StationList(OrderedSet[CircuitedTieredStation]):
    @multimethod
    def insert(self, circuited_tiered_station: CircuitedTieredStation):
        if CircuitedTieredStation.station is NullStation:
            return
        self._set[circuited_tiered_station] = None

    @multimethod
    def insert(self, station: Station, tier: TierSpec, circuit: int = 0):
        circuited_tiered_station = CircuitedTieredStation(station, tier, circuit)
        self._set[circuited_tiered_station] = None

    @property
    def stations(self):
        return tuple(self._set.keys())


class ToolList(OrderedSet[Tool]):
    @property
    def tools(self):
        return tuple(self._set.keys())


@dataclass(slots=True, frozen=True)
class ItemizerResult2:
    unit_out: QuantifiedDict[Item]
    extra_out: QuantifiedDict[Item]
    produced: QuantifiedDict[Item]
    prebuilt_out: QuantifiedDict[Item]
    stations: StationList
    tools: ToolList

    def pretty_print(self):
        print("UNITS")
        normal_print_tbl(self.unit_out)
        print("\nEXTRA")
        normal_print_tbl(self.extra_out)

        print("\nPARTS")
        # normal_print_tbl(self.produced)
        # return
        parts_print = [(k, v, self.prebuilt_out.get(k, 0)) for
                       k, v in self.produced.items()]
        print_double_wide_table(parts_print, sort=False)
        print("\nSTATIONS")
        print_list(self.stations.stations, sort=False)
        print("\nTOOLS")
        print_list(self.tools.tools, sort=False)


@dataclass(slots=True, frozen=True)
class ItemizerResult:
    unit_out: QuantifiedDict[Item]
    extra_out: QuantifiedDict[Item]
    prebuilt_out: QuantifiedDict[Item]
    out: QuantifiedDict[Item]

    def pretty_print(self):
        print("UNITS")
        normal_print_tbl(self.unit_out)
        print("\nEXTRA")
        normal_print_tbl(self.extra_out)
        print("\nPARTS")

        parts_print = [(k, v - self.prebuilt_out.get(k, 0) - self.extra_out.get(k, 0), self.prebuilt_out.get(k, 0)) for
                       k, v in (self.out + self.prebuilt_out).items()]
        print_double_wide_table(parts_print, sort=False)


@dataclass(slots=True)
class RecipeSolver:
    db: RecipeDB
    graph: RecipeGraph
    fake_item: Item
    fake_recipe: RecipeBase

    @property
    def root(self) -> RecipeBase:
        return self.fake_recipe

    def __init__(self, db: RecipeDB, items: Sequence[NamedItemBase] | set[NamedItemBase]):
        self.fake_item = Item()
        self.fake_recipe = Recipe([Quantified(1, self.fake_item)], items, TierSpec.ULV, 0, NullStation, [])
        self.graph = RecipeGraph(self.fake_recipe)
        self.db = db
        self._process()

    def _process(self):
        stack_set = {self.root}
        stack = [(self.root, iter(self.root.items))]
        while stack:
            root, items = stack[-1]
            try:
                item = next(items)
            except StopIteration:
                stack.pop()
                stack_set.discard(root)
                continue

            if (recipe := self.db.get_recipe(item)) is None:
                continue
            if recipe in stack_set:
                print([elem[0] for elem in stack] + [recipe])
                raise RuntimeError("Cycle detected")
            stack_set.add(recipe)

            self.graph.try_add_node(recipe)
            self.graph.add_edge(root, recipe)
            stack.append((recipe, iter(recipe.items)))


class Itemizer2:
    root: RecipeBase
    db: RecipeDB
    graph: RecipeGraph

    def __init__(self, root: RecipeBase, db: RecipeDB):
        self.root = root
        self.db = db
        self.graph = RecipeGraph(root)
        self._process()
        self.topological_order = self.graph.topological_sort()[1:]

    def _process(self):
        stack = [(self.root, iter(self.root.items))]
        while stack:
            root, items = stack[-1]
            # get next item
            try:
                item = next(items)
            except StopIteration:
                stack.pop()
                continue
            # check if is unit and get recipe
            if (recipe := self.db.get_recipe(item)) is None:
                continue

            self.graph.try_add_node(recipe)
            self.graph.add_edge(root, recipe)
            # add an edge for each side product from the main recipe to this recipe
            for product in recipe.products[1:]:

                primary = self.db.get_recipe(product)
                if primary is None:
                    continue
                if recipe in primary.dependencies:
                    # this would cause a cycle
                    continue

                if primary not in self.graph.recipe_map:
                    self.graph.add_node(primary)
                # print(f"adding weak edge {primary}->{recipe}")
                self.graph.add_edge(recipe, primary)

            stack.append((recipe, iter(recipe.items)))

    def solve(self, prebuilt: prebuilt_type = None):
        if prebuilt is None:
            prebuilt = QuantifiedDict[NamedItemBase]()
        elif isinstance(prebuilt, QuantifiedDict):
            prebuilt = prebuilt
        else:
            assert isinstance(prebuilt,
                              (Sequence,
                               Set)), f"Expected QuantifiedDict[NamedItemBase] or Sequence[Quantified[NamedItemBase] | NamedItemBase], got {type(prebuilt).__name__}"
            prebuilt = QuantifiedDict[NamedItemBase].from_list(prebuilt)

        stations = StationList()
        tools = ToolList()
        needed = QuantifiedDict.from_list(self.root.items)
        produced = QuantifiedDict[NamedItemBase]()
        units = QuantifiedDict[NamedItemBase]()
        extra = QuantifiedDict[NamedItemBase]()
        prebuilt_out = QuantifiedDict[NamedItemBase]()
        for recipe in self.topological_order:
            circuited_tiered_station = CircuitedTieredStation(recipe.station, recipe.tier, recipe.circuit)
            stations.insert(circuited_tiered_station)
            for tool in recipe.tools:
                tools.insert(tool)
            main_product: Quantified[NamedItemBase] = recipe.products[0]
            needed_item = needed[main_product.val]

            count = ceil_round(needed_item, main_product.count)
            mult = count // main_product.count
            if mult == 0:
                continue
            for product in recipe.products:
                if product.val in needed:
                    produced[product.val] += needed[product.val]
                    rem = needed.reduce(product.val, mult * product.count)

                    if rem:
                        extra[product.val] += rem
                else:
                    extra[product.val] += mult * product.count
            for item in recipe.items:
                item: Quantified[NamedItemBase] = item.copy()
                item.count *= mult
                # check if item already prebuilt and remove the prebuilt count from what needs to be built
                if item.val in prebuilt:
                    prebuilt_count = prebuilt[item.val]
                    if prebuilt_count > item.count:
                        prebuilt_out[item.val] += item.count
                        prebuilt[item.val] -= item.count
                        continue
                    elif prebuilt_count == item.count:
                        prebuilt_out[item.val] += item.count
                        del prebuilt[item.val]
                        continue
                    else:
                        item = item.copy()
                        prebuilt_out[item.val] += prebuilt_count
                        item.count -= prebuilt_count
                        del prebuilt[item.val]
                # check if item in extra and remove the already built count from what needs to be built
                if item in extra:
                    count = extra[item.val]
                    if count > item.count:
                        rem = count - item.count
                        extra[item.val] = rem
                        continue
                    elif count == item.count:
                        del extra[item.val]
                        continue
                    else:
                        item = item - extra[item.val]
                    item = item.copy()
                    item -= extra[item.val]

                if self.db.is_unit(item):
                    # no primary recipe for item
                    units[item.val] += item.count
                    continue
                else:
                    needed += item

        return ItemizerResult2(units, extra, produced, prebuilt_out, stations, tools)


class Itemizer:
    prebuilt_out: QuantifiedDict[Item]
    prebuilt: QuantifiedDict[Item]

    @staticmethod
    def _real_count(sitem, count):
        pcount = sitem.recipe.get_product_count(sitem.item)
        tot_count = ceil_round(count, pcount)
        extra = 0
        if tot_count > count:
            extra = tot_count - count
        return tot_count, pcount, extra

    def __init__(self, count: int, root: BaseSolverItem, item_map: dict[NamedItemBase, BaseSolverItem],
                 prebuilt: prebuilt_type = None):
        if prebuilt is None:
            prebuilt = QuantifiedDict[NamedItemBase]()
        elif isinstance(prebuilt, QuantifiedDict):
            prebuilt = prebuilt
        else:
            assert isinstance(prebuilt,
                              Sequence), f"Expected QuantifiedDict[NamedItemBase] or Sequence[Quantified[NamedItemBase] | NamedItemBase], got {type(prebuilt).__name__}"
            prebuilt = QuantifiedDict[NamedItemBase].from_list(prebuilt)

        self.prebuilt = prebuilt
        self.prebuilt_out = QuantifiedDict[NamedItemBase]()
        self.item_map = item_map
        self.out = QuantifiedDict[Item]()
        self.unit_out = QuantifiedDict[Item]()
        self.partial = QuantifiedDict[Item]()
        self.extra_out = QuantifiedDict[Item]()

        self.deferred = root.deferred.copy()
        self.stack = []
        self.push_item(root, count, 1)

    def push_item(self, sitem: BaseSolverItem, item_count: int, recipe_count: int):
        total_count = item_count * recipe_count + self.partial.pop(sitem.item)
        if total_count:
            total_count_rem = self.prebuilt.reduce_sub(total_count, sitem.item, self.prebuilt_out)
        else:
            total_count_rem = total_count

        if total_count_rem:
            sitem_pcount = sitem.recipe.get_product_count(sitem.item)
            real_count = ceil_round(total_count_rem, sitem_pcount)

            if real_count > total_count_rem:
                self.extra_out[sitem.item] = real_count - total_count_rem
            # add extra outputs
            # for product in sitem.recipe.products:
            #    if product
            # self.extra_out[sitem.item] = total_count_rem
            sitem_rcount = real_count // sitem_pcount
            self.out[sitem.item] += real_count
        else:
            sitem_rcount = 0

        self.stack.append((sitem, sitem_rcount, iter(sitem.direct_deps.items())))

    def calc(self) -> ItemizerResult:

        out = self.out
        unit_out = self.unit_out
        item_map = self.item_map

        prebuilt_out = self.prebuilt_out

        extra_out = self.extra_out
        deferred = self.deferred
        stack = self.stack

        partial = self.partial

        while self.stack:
            sitem, rcount, it = self.stack[-1]
            for item, icount in it:
                dsitem = item_map[item]
                if deferred.dec_jz(dsitem.item):
                    self.push_item(dsitem, icount, rcount)
                    break
                partial[dsitem.item] += icount * rcount
                deferred.sub(dsitem.deferred)


            else:
                if rcount != 0:
                    for unit, unit_count in sitem.direct_units.items():
                        unit_out[unit] += unit_count * rcount
                stack.pop()
        assert (not deferred and not partial)
        return ItemizerResult(unit_out, extra_out, prebuilt_out, out)


class BaseSolverItem:
    __slots__ = 'is_unit', 'item', 'db', 'recipe', 'deps', 'direct_deps', 'rdeps', \
        'deferred', 'solved', 'direct_units', 'units', 'unsolved_direct_deps', \
        'dep_order'
    is_unit: bool
    item: Item
    db: RecipeDB
    recipe: RecipeBase | None
    rdeps: set[Item]
    deps: set[Item]
    direct_deps: QuantifiedDict[Item]
    deferred: QuantifiedDict[Item]
    solved: bool
    direct_units: QuantifiedDict[Item]
    units: QuantifiedDict[Item]
    unsolved_direct_deps: set[Item]
    dep_order: list[Item]

    def _add_deps(self):
        db = self.db
        recipe = self.recipe
        direct_deps = self.direct_deps
        units = self.direct_units

        for item in recipe.items:
            count, item = item.count, item.val
            if db.is_unit(item):
                units[item] += count
            else:
                direct_deps[item] += count

    def __init__(self, item: Item, db: RecipeDB, is_unit: bool, recipe: RecipeBase | None = None):
        if is_unit:
            if recipe is not None:
                raise ValueError("recipe must be None if is_unit")
        else:
            if recipe is None:
                raise ValueError("recipe must not be None if not is_unit")
        self.is_unit = is_unit
        self.rdeps = set()
        self.deferred = QuantifiedDict[Item]()
        self.solved = is_unit
        self.item = item
        self.db = db
        self.recipe = recipe

        self.direct_units = QuantifiedDict[Item]()
        self.direct_deps = QuantifiedDict[Item]()

        if not is_unit:
            self._add_deps()

        self.dep_order = list(self.direct_deps)
        self.unsolved_direct_deps = set(self.direct_deps.keys())
        self.deps = set(self.direct_deps.keys())
        self.units = self.direct_units.copy()


class UnionSolverItem(BaseSolverItem):
    __slots__ = 'fake_item', 'fake_recipe', 'fake_sitem'
    fake_item: Item
    fake_recipe: RecipeBase
    fake_sitem: SolverItem

    def __init__(self, items: Sequence[Quantified[NamedItemBase] | NamedItemBase] | set[
        Quantified[NamedItemBase] | NamedItemBase], db):
        if len(items) == 0:
            raise ValueError("UnionSolverItem must have at least 1 item")

        self.fake_item = Item()
        self.fake_recipe = RecipeBase([Quantified(1, self.fake_item)], quantify_list(items), TierSpec.ULV, 0,
                                      NullStation, [])
        self.fake_sitem = SolverItem(self.fake_item, db, False, self.fake_recipe)
        super().__init__(self.fake_item, db, False, self.fake_recipe)


class SolverItem(BaseSolverItem):
    __slots__ = ()

    def __init__(self, item: Item, db, is_unit: bool | None = None, recipe: RecipeBase | None = None):
        if is_unit:
            recipe = None
        elif recipe is None:
            recipe = db.get_recipe(item)
            if recipe is None:
                raise RuntimeError(f"No recipe to build item {item}")

        super().__init__(item, db, is_unit, recipe)


class DeferMap:
    def __init__(self):
        self.defer_map = {}
        self.stack_map = defaultdict(list)
        self.stack = []
        self.it_stack = []

    @classmethod
    def gen_init(cls, sitem):
        return iter(reversed(sitem.dep_order))

    def raw_push(self, sitem):
        self.stack.append(sitem)
        self.it_stack.append(self.gen_init(sitem))

    def do_defer(self, sitem):
        if not self.stack:
            return
        top = self.stack[-1]
        top.deferred[sitem.item] += 1
        top.deferred += sitem.deferred

    def __bool__(self):
        return not not self.stack

    def __iter__(self):
        return self

    def __next__(self):
        if not self.stack:
            raise StopIteration
        return self.stack[-1], self.it_stack[-1]

    def defer_push(self, sitem):
        if sitem.solved:
            self.do_defer(sitem)
            return True

        self.raw_push(sitem)
        return False

    def pop(self):
        sitem = self.stack.pop()
        self.it_stack.pop()
        sitem.solved = True
        self.do_defer(sitem)


class Solver:
    __slots__ = 'db', 'units', 'solved', 'item_map', 'item_set', 'unsolved', 'fake_sitem'
    unsolved: set[NamedItemBase]
    solved: set[NamedItemBase]
    db: RecipeDB
    units: set[NamedItemBase]
    item_set: set[NamedItemBase]
    fake_sitem: UnionSolverItem
    item_map: dict[NamedItemBase, BaseSolverItem]

    def union_calc(self, items: list[NamedItemBase], prebuilt=None):
        items = quantify_list(items)
        # print(items)
        fake_sitem = UnionSolverItem(items, self.db)
        self.isolve(fake_sitem)
        result = self.sitem_calc(fake_sitem, prebuilt)
        del result.out[fake_sitem.item]
        return result

    def sitem_calc(self, sitem: BaseSolverItem, prebuilt: prebuilt_type = None) -> ItemizerResult:
        return Itemizer(1, sitem, self.item_map, prebuilt).calc()

    def calc(self, item: NamedItemBase | Quantified[NamedItemBase], prebuilt=None):
        if isinstance(item, Quantified):
            assert isinstance(item.val, NamedItemBase)
            quantity = item.count
            item = item.val
        else:
            quantity = 1

        return Itemizer(quantity, self.item_map[item], self.item_map, prebuilt).calc()

    def add_init_items(self, items_list: Sequence[NamedItemBase]):
        db = self.db
        units = self.units
        solved = self.solved
        item_map = self.item_map
        item_set = self.item_set
        is_unit = db.is_unit

        for item in items_list:
            if is_unit(item):
                units.add(item)
                solved.add(item)
                item_map[item] = SolverItem(item, db, True, None)
                item_set.add(item)
            else:
                self.unsolved.add(item)
                item_set.add(item)
                item_map[item] = SolverItem(item, db, False)
        self.fake_sitem = UnionSolverItem(self.unsolved, db)

    def add_item(self, item):
        db = self.db

        self.item_set.add(item)
        if is_unit := db.is_unit(item):
            self.units.add(item)

        sitem = SolverItem(item, db, is_unit)
        self.item_map[item] = sitem
        return sitem

    def get_item(self, item):
        if (ret := self.item_map.get(item)) is not None:
            return ret
        return self.add_item(item)

    def take_unsolved(self):
        return self.take_unsolved_from(self.unsolved)

    def take_unsolved_from(self, uset):
        while uset:
            item = uset.pop()
            if item not in self.item_map:
                self.add_init_items((item,))
            if item in self.solved:
                continue

            sitem = self.item_map[item]

            # unsolved =
            sitem.unsolved_direct_deps -= self.solved
            if not sitem.unsolved_direct_deps:
                sitem.solved = True
                self.solved.add(item)
                continue
            return sitem
        return None

    def solve(self):
        self.isolve(self.fake_sitem)

    def isolve(self, sitem):
        """Solve the deferred map for `sitem`."""
        dstack = DeferMap()
        dstack.raw_push(sitem)
        stack_set = {sitem.item, }

        for sitem, it in dstack:
            for item in it:

                if item in stack_set:
                    raise RuntimeError("Cycle Detected")

                dsitem = self.get_item(item)
                if dsitem.is_unit:
                    continue

                if dstack.defer_push(dsitem):
                    continue
                else:
                    stack_set.add(item)
                    break
            else:
                # self.solved.add(sitem.item)
                dstack.pop()
                stack_set.discard(sitem.item)
                continue

    def __init__(self, items: list[NamedItemBase], db: RecipeDB):

        self.db = db

        self.units = set()
        # self.items = set()
        self.solved = set()
        self.unsolved = set()
        self.item_map = dict()
        self.item_set = set()
        self.add_init_items(items)
