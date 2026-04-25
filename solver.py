import math

from .recipeDB import *
from .quantified import quantify_list
from dataclasses import dataclass
import itertools as it

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

def _tcount_printer(items_count: list[tuple[NamedItemBase, int]], pad, dpad, pre_tab, drop_zero):
    for item, count in items_count:
        s = f'{item:{pad}}'
        for c in count:
            if drop_zero and c == 0:
                c = ' '
            s += f'{c:>{dpad}}'
        print(f'{"\t" * pre_tab}{s}')


def _normal_printer(items_count, pad, dpad, pre_tab, drop_zero):
    for item, count in items_count:
        print(f'{"\t" * pre_tab}{item:{pad}}{count:>{dpad}}')


def normal_print_tbl(item_table: QuantifiedDict[NamedItemBase], sort=True, pre_tab=0, empty_text="*NONE*"):
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

def print_doublewide_table(item_table: tuple[NamedItemBase, int, int], sort=True, pre_tab=0, empty_text="*NONE*"):
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


@dataclass(slots=True, frozen=True)
class ItemizerResult:
    unit_out: list[QuantifiedDict[NamedItemBase]]
    extra_out: list[QuantifiedDict[NamedItemBase]]
    prebuilt_out: list[QuantifiedDict[NamedItemBase]]
    out: list[QuantifiedDict[NamedItemBase]]

    def prety_print(self):
        print("UNITS")
        normal_print_tbl(self.unit_out)
        print("\nEXTRA")
        normal_print_tbl(self.extra_out)
        print("\nPARTS")

        parts_print = [(k, v - self.prebuilt_out.get(k, 0) - self.extra_out.get(k, 0), self.prebuilt_out.get(k, 0)) for k, v in (self.out + self.prebuilt_out).items()]
        print_doublewide_table(parts_print, sort=False)


class Itemizer:
    def _precalc(self, count, sitem):
        item_map = self.item_map
        out = self.out
        pcount = sitem.recipe.get_product_count(sitem.item)
        #print(sitem.item, pcount)
        real_count = ceil_round(count, pcount)
        #print(sitem.item, count, real_count)
        rcount = real_count // pcount
        #print(rcount)
        extra = real_count - count
        #for unit, ucount in sitem.units.items():
        #    out[unit] += ucount * rcount

        pos = iter([(x, sitem.direct_deps[x]) for x  in sitem._dep_order])
        #self.defered = sitem.defered.copy()
        return extra, rcount, pos

    @staticmethod
    def _real_count(sitem, count):
        pcount = sitem.recipe.get_product_count(sitem.item)        
        tot_count = ceil_round(count, pcount)
        extra = 0
        if tot_count > count:
            extra = tot_count - count
        return tot_count, pcount, extra
    
    def __init__(self, count, root, item_map, prebuilt: QuantifiedDict[NamedItemBase] | Sequence[Quantified[NamedItemBase] | NamedItemBase] | None=None):
        if prebuilt is None:
            prebuilt = QuantifiedDict()
        elif isinstance(prebuilt, QuantifiedDict):
            prebuilt = prebuilt
        else:
            assert isinstance(prebuilt, Sequence), f"Expected QuantifiedDict[NamedItemBase] or Sequence[Quantified[NamedItemBase] | NamedItemBase], got {type(prebuilt).__name__}"
            prebuilt = QuantifiedDict.from_list(prebuilt)


        self.prebuilt = prebuilt
        self.prebuilt_out = QuantifiedDict()
        self.item_map = item_map
        self.out = QuantifiedDict()
        self.unit_out = QuantifiedDict()
        self.partial = QuantifiedDict()
        self.extra_out = QuantifiedDict()
        
        self.defered = root.defered.copy()
        self.stack = []
        self.push_item(root, count, 1)

    def push_item(self, sitem, item_count, recipe_count):
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
            #add extra outputs
            #for product in sitem.recipe.products:
            #    if product
            #self.extra_out[sitem.item] = total_count_rem
            sitem_rcount = real_count // sitem_pcount
            self.out[sitem.item] += real_count
        else:
            real_count = 0
            sitem_rcount = 0

        self.stack.append((sitem, sitem_rcount, iter(sitem.direct_deps.items())))

    def calc(self):
        import time

        out = self.out
        unit_out = self.unit_out
        item_map = self.item_map

        prebuilt = self.prebuilt
        prebuilt_out = self.prebuilt_out

        extra_out = self.extra_out
        defered = self.defered
        stack = self.stack

        partial = self.partial
        
        while self.stack:
            sitem, rcount, it = self.stack[-1]
            for item, icount in it:
                dsitem = item_map[item]
                if defered.dec_jz(dsitem.item):
                    self.push_item(dsitem, icount, rcount)
                    break
                partial[dsitem.item] += icount * rcount
                defered.sub(dsitem.defered)
                
                             
            else:
                if rcount != 0:
                    for unit, unit_count in sitem.direct_units.items():
                        unit_out[unit] += unit_count * rcount
                stack.pop()
        assert (not defered and not partial)
        return ItemizerResult(unit_out, extra_out, prebuilt_out, out)

class BaseSolverItem:
    __slots__ = 'is_unit', 'item', 'db', 'recipe', 'deps', 'direct_deps', 'rdeps', \
                'defered', 'solved', 'direct_units', 'units', 'unsolved_direct_deps', \
                '_dep_order'
    is_unit: bool
    item: Item
    db: RecipeDB
    recipe: Recipe
    rdeps: set[Item]
    deps: set[Item]
    direct_deps: set[Item]
    rdeps: set[Item]
    defered: QuantifiedDict[Item]
    solved: bool
    direct_units: QuantifiedDict[Item]
    units: QuantifiedDict[Item]
    unsolved_direct_deps: set[Item]
    _dep_order: list[Item]
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
    
    def __init__(self, item, db, is_unit: bool, recipe = None):
        if is_unit:
            if recipe is not None:
                raise ValueError("recipe must be None if is_unit")
        else:
            if recipe is None:
                raise ValueError("recipe must be None if not is_unit")
        self.is_unit = is_unit
        self.rdeps = set()
        self.defered = QuantifiedDict()
        self.solved = is_unit
        self.item = item
        self.db = db
        self.recipe = recipe

        self.direct_units = QuantifiedDict()
        self.direct_deps = QuantifiedDict()

        if not is_unit:
            self._add_deps()

        self._dep_order = list(self.direct_deps)
        self.unsolved_direct_deps = set(self.direct_deps.keys())
        self.deps = set(self.direct_deps.keys())
        self.units = self.direct_units.copy()

class UnionSolverItem(BaseSolverItem):
    __slots__ = 'fake_item', 'fake_recipe', 'fake_sitem'
    
    def __init__(self, items: Sequence[NamedItemBase] | set[NamedItemBase], db):
        if len(items) == 0:
            raise ValueError("UnionSolverItem must have at least 1 item")
        
        
        self.fake_item = Item()
        self.fake_recipe = RecipeBase([Quantified(1, self.fake_item)], quantify_list(items), TierSpec.ULV, None, [])
        self.fake_sitem = SolverItem(self.fake_item, db, False, self.fake_recipe)
        super().__init__(self.fake_item, db, False, self.fake_recipe)

class SolverItem(BaseSolverItem):
    __slots__ = ()
        
    def __init__(self, item: Item, db, is_unit: bool | None = None, recipe=None):
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
        return iter(reversed(sitem._dep_order))
    
    @property
    def top(self):
        return self.stack[-1], self.it_stack[-1]
    def push(self, sitem, it):
        self.stack.append(sitem)
        self.it_stack.append(it)

    def raw_push(self, sitem):
        self.stack.append(sitem)
        self.it_stack.append(self.gen_init(sitem))
    def do_defer(self, sitem):
        if not self.stack:
            return
        top = self.stack[-1]
        top.defered[sitem.item] += 1
        top.defered += sitem.defered
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

    def defer2(self, sitem):
        top = self.stack[-1]
        
        
        self.stack_map[top].append(sitem.item)

        if not sitem.solved:
            top.defered[sitem.item] += 1
            return False
        else:
            top.defered += sitem.defered
            return True

    def defer(self, item):
        sitem = self.stack[-1]

        
        prev_decl = self.defer_map.get(item)
        if prev_decl is None:
            self.defer_map[item] = [sitem]
            ret = False
        else:

            prev_decl[-1].defered[item] += 1
            prev_decl.append(sitem)
            ret = True
        self.stack_map[sitem].append(item)

        return ret
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
    def union_calc(self, items: list[NamedItemBase], prebuilt=None):
        items = quantify_list(items)
        #print(items)
        fake_sitem = UnionSolverItem(items, self.db)
        self.isolve(fake_sitem)
        
        result = self.sitem_calc(fake_sitem, prebuilt)
        del result.out[fake_sitem.item]
        return result
    def sitem_calc(self, sitem, prebuilt=None):
        return Itemizer(1, sitem, self.item_map, prebuilt).calc()
    def calc(self, item: NamedItemBase | Quantified[NamedItemBase], prebuilt=None):
        if isinstance(item, Quantified):
            assert isinstance(item.val, NamedItemBase)
            quantity = item.count
            item = item.val
        else:
            quantity = 1

        return Itemizer(quantity, self.item_map[item], self.item_map, prebuilt).calc()
            
    def add_init_items(self, items_list: list[NamedItemBase]):
        db = self.db
        units = self.units
        solved = self.solved
        item_map = self.item_map
        item_set = self.item_set
        is_unit = db.is_unit

        to_solve = []
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
        if (is_unit := db.is_unit(item)):
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

            #unsolved = 
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
        
        #solved = self.solved
        #unsolved = self.unsolved
        item_map = self.item_map

        dstack = DeferMap()
        dstack.raw_push(sitem)
        stack_set = {sitem.item,}
        
        for sitem, it in dstack:
            for item in it:
                if item in stack_set:
                    raise RuntimeError("Cycle Detected")

                dsitem = self.get_item(item)
                if dsitem.is_unit:
                    continue
                                
                if dstack.defer_push(dsitem):
                    continue



                
                #print(dsitem.item)
                stack_set.add(item)
                break
            else:
                #self.solved.add(sitem.item)
                dstack.pop()
                stack_set.discard(sitem.item)
                continue
            

        
    def __init__(self, items: list[NamedItemBase], db=None):
        if db is None:
            db = RecipeDB

        self.db = db
        
        self.units = set()
        #self.items = set()
        self.solved = set()
        self.unsolved = set()
        self.item_map = dict()
        self.item_set = set()
        self.add_init_items(items)
