from collections import defaultdict
from dataclasses import dataclass
from .recipeDB_types import Item
from .recipes import *

__all__ = ["RecipeGraph", "RecipeGraphNode"]
@dataclass(slots=True)
class RecipeGraphNode:
    recipe: RecipeBase
    out_edges: list[RecipeGraphNode]
    mark: int
    def __init__(self, recipe: RecipeBase):
        self.recipe = recipe
        self.out_edges = []
        #self.in_edges = []
        self.mark = 0
    @property
    def perminant_mark(self) -> bool:
        return self.mark == 2
    @property
    def temporary_mark(self):
        return self.mark == 1
    def add_out_edge(self, target: RecipeGraphNode):
        self.out_edges.append(target)

    #def add_in_edge(self, target: RecipeGraphNode):
    #    self.in_edges.append(target)

@dataclass(slots=True)
class RecipeGraph:
    nodes: list[RecipeGraphNode]
    #edges: list[tuple[int, int]]
    recipe_map: dict[RecipeBase, tuple[RecipeGraphNode, int]]
    product_map: defaultdict[Item, list[RecipeBase]]
    def __init__(self, root: RecipeBase):

        self.nodes = [RecipeGraphNode(root)]
        self.recipe_map = {root: (self.nodes[0], 0)}
        self.product_map = defaultdict(list)
        for product in root.products:
            self.product_map[product.val] = [root]
        #self.edges = []
    def add_node(self, node: RecipeGraphNode | RecipeBase):
        if (ret := self.try_add_node(node)) is None:
            raise RuntimeError("Duplicate Recipe")
        return ret
    def try_add_node(self, node: RecipeGraphNode | RecipeBase) -> int | None:
        """Returns true if this is a new node, otherwise false."""
        if isinstance(node, RecipeBase):
            recipe = node
            node = RecipeGraphNode(recipe)
        else:
            recipe = node.recipe
        if recipe in self.recipe_map:
            return None
        ret = len(self.nodes)
        self.recipe_map[recipe] = (node, ret)
        self.nodes.append(node)
        for product in recipe.products:
            self.product_map[product.val].append(recipe)
        return ret
    def _resolve_node_recipe_pos(self, node: RecipeGraphNode | RecipeBase) -> tuple[RecipeGraphNode, RecipeBase, int]:
        if isinstance(node, RecipeBase):
            recipe = node
            node, pos = self.recipe_map[recipe]
        else:
            recipe = node.recipe
            pos = self.recipe_map[recipe][1]
        return node, recipe, pos
    def add_edge(self, from_node: RecipeGraphNode | RecipeBase, to_node: RecipeGraphNode | RecipeBase):
        from_node, from_recipe, from_pos = self._resolve_node_recipe_pos(from_node)
        to_node, to_recipe, to_pos = self._resolve_node_recipe_pos(to_node)
        #from_recipe.add_dependency(to_recipe)
        #self.edges.append((from_pos, to_pos))
        from_node.out_edges.append(to_node)
        #to_node.in_edges.append(from_node)
    def topological_sort(self):
        L = []
        unvisited = self.nodes.copy()
        def visit(node: RecipeGraphNode):
            if node.perminant_mark:
                return
            if node.temporary_mark:
                return [node.recipe.products[0].val]
                #raise RuntimeError("Cycle detected")
            node.mark = 1
            for subnode in node.out_edges:
                if (cycle := visit(subnode)) is not None:
                    cycle.append(node.recipe.products[0].val)
                    return cycle

            node.mark = 2

            L.append(node.recipe)

        while unvisited:
            node = unvisited.pop()
            if node.mark != 0:
                continue
            if (ret := visit(node)) is not None:
                raise RuntimeError("Cycle detected", ret)
        L.reverse()
        return L
