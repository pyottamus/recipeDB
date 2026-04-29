from .recipeDB import *
from .solver import *
from collections.abc import Sequence
from pathlib import Path
import re
from enum import IntEnum
from .recipe_lexer import *
from .recipeDB_parser_types import *
from .recipeDB_types import *
from dataclasses import dataclass


class CommentFilter:
    def __init__(self, tokstream):
        self.tokstream = iter(tokstream)

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            nxt = next(self.tokstream)
            if isinstance(nxt, Comment):
                continue
            else:
                return nxt


class LA:
    @property
    def entered(self):
        return self.lexer.entered

    @property
    def pos(self):
        return self.lexer.pos

    @property
    def line(self):
        return self.lexer.line

    @property
    def linetab(self):
        return self.lexer.linetab

    @property
    def data(self):
        return self.lexer.data

    def increase_linetab(self, amount):
        return self.lexer.increase_linetab(amount)

    def decrease_linetab(self, amount):
        return self.lexer.decrease_linetab(amount)

    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.tokstream = None
        self.la = None
        self.previous = None

    def __enter__(self):
        self.lexer.__enter__()
        self.tokstream = CommentFilter(self.lexer.lex())
        try:
            self.la = next(self.tokstream)
        except StopIteration:
            self.la = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.lexer.__exit__(exc_type, exc_val, exc_tb)

    def __iter__(self):
        return self

    def peek(self):
        if self.la is None:
            return None
        return self.la

    def advance(self):
        return self.__next__()

    def __next__(self):
        if self.la is None:
            raise StopIteration
        self.previous = self.la
        ret = self.la
        try:
            self.la = next(self.tokstream)
        except StopIteration:
            self.la = None
        return ret


class Parser:
    built_in = {"workbench": Station, fluid: Component}

    def __init__(self, file: Path, print_recipes: bool = False):
        self.file = file
        self.lexer = LA(Lexer(file))
        self.db = RecipeDB()
        self.solver = None
        self.print_recipes = print_recipes

    def __enter__(self):
        self.lexer.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.lexer.__exit__(exc_type, exc_val, exc_tb)

    def get_line_pos(self, start_line: int, end_line: int) -> tuple[int, int]:
        if (end_line + 1) > len(self.lexer.linetab):
            increased = self.lexer.increase_linetab(end_line + 1 - self.lexer.line)
        else:
            increased = 0
        line_start_pos = self.lexer.linetab[start_line - 1]
        line_end_pos = self.lexer.linetab[end_line + 1 - 1]
        self.lexer.decrease_linetab(increased)
        return line_start_pos, line_end_pos

    def ext_error(self, msg, got, *expected):
        if len(expected) == 1:
            expects = f"'{expected[0].__name__}'"
        elif len(expected) == 2:
            expects = f"'{expected[0].__name__}' or '{expected[1].__name__}'"
        else:
            names = [f"'{x.__name__}'" for x in expected]
            car = ', '.join(names[:-1])
            cdr = f', or {names[-1]}'
            expects = f'{car}{cdr}'
        start_line = got.start_line
        end_line = got.end_line
        pos = got.pos
        line_start_pos, line_end_pos = self.get_line_pos(start_line, end_line)

        col = pos - line_start_pos

        line1 = f"Expected {expects}, got '{got.__class__.__name__}'"
        line2 = msg
        line3 = f"\tError Occured on line {start_line}, offset {col}"
        line4 = f"Full lines follows After line break"
        line5 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}\n")

    def redeclaration_of_builtin(self, token: Lexeme, typ: str):
        start_line = token.start_line
        end_line = token.end_line
        pos = token.pos
        built_in_type = self.built_in[token.name].__name__
        prev_decl = self.db.prev_decl[token.name]
        line_start_pos, line_end_pos = self.get_line_pos(start_line, end_line)

        col = pos - line_start_pos

        line1 = f"Redelclaration of built-in token of type {built_in_type} redeclared as type {typ}"
        line2 = f"\tError Occured on line {start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n")

    def undeclared_error(self, token: Lexeme, typ: str):
        start_line = token.start_line
        end_line = token.end_line
        pos = token.pos
        line_start_pos, line_end_pos = self.get_line_pos(start_line, end_line)
        line1 = f"Use of undefined token {token.name} used as type {typ}"
        line2 = f"Full lines follows After line break"
        line3 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n")

    def redeclaration_of_builtin_star(self, materialized_star_item: MaterialzeStarItem):
        raise NotImplementedError

    def redeclaration_star(self, component: Varname, material: Varname, materialized_star: MaterializeStar):
        item = MaterialzeStarItem(materialized_star, component, material)
        if item.qname in self.built_in:
            return self.redeclaration_of_builtin_star(item)

        start_line = materialized_star.start.start_line
        end_line = materialized_star.end.end_line
        token_line = material.start_line
        pos = material.pos
        line_start_pos, line_end_pos = self.get_line_pos(start_line, end_line)
        col = pos - line_start_pos

        prev_decl = self.db.prev_decl[item.qname]
        prev_start_line = prev_decl.start_line
        prev_end_line = prev_decl.end_line
        prev_pos = prev_decl.pos
        prev_start_pos, prev_end_pos = self.get_line_pos(prev_start_line, prev_end_line)
        prev_col = prev_pos - prev_start_pos
        line1 = f"Redelclaration of MaterializedComponent, line {token_line}, offset {col}"
        line2 = f"Previos declaration on line {prev_start_line}, offset {prev_col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        line5 = f"Previous declaration occured on line {prev_start_line}, offset {prev_col}"
        line6 = f"Full lines follows After line break"
        line7 = self.lexer.data[prev_start_pos:prev_end_pos]

        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}\n{line6}\n{line7}\n")

    def redeclaration(self, token: Lexeme, typ: str):
        if token.name in self.built_in:
            return self.redeclaration_of_builtin(token, typ)

        start_line = token.start_line
        end_line = token.end_line
        pos = token.pos

        prev_decl = self.db.prev_decl[token.name]
        prev_start_line = prev_decl.start_line
        prev_end_line = prev_decl.end_line
        prev_pos = prev_decl.pos
        prev_start_pos, prev_end_pos = self.get_line_pos(prev_start_line, prev_end_line)
        line_start_pos, line_end_pos = self.get_line_pos(start_line, end_line)

        col = pos - line_start_pos
        prev_col = prev_pos - prev_start_pos
        prev_type = self.db._sym_table[token.name].__class__.__name__

        line1 = f"Redelclaration of token of type {prev_type} redeclared as type {typ}"
        line2 = f"Redeclaration Occured on line {start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        line5 = f"Previous declaration occured on line {prev_start_line}, offset {prev_col}"
        line6 = f"Full lines follows After line break"
        line7 = self.lexer.data[prev_start_pos:prev_end_pos]
        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}\n{line6}\n{line7}\n")

    def redeclaration_fluid(self, token: Varname, error: ValueError):
        realized = error.args[1]
        start_line = token.start_line
        end_line = token.end_line
        pos = token.pos
        line_start_pos, line_end_pos = self.get_line_pos(start_line, end_line)
        col = pos - line_start_pos
        if token.name in self.built_in:
            line1 = f"Redeclaration of built-in token {realized.qname}"
            line2 = f"Redeclaration Occured on line {start_line}, offset {col}"
            line3 = f"Full lines follows After line break"
            line4 = self.lexer.data[line_start_pos:line_end_pos]

            raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n")

        prev_decl = self.db.prev_decl[realized.qname]
        prev_start_line = prev_decl.start_line
        prev_end_line = prev_decl.end_line
        prev_pos = prev_decl.pos
        prev_start_pos, prev_end_pos = self.get_line_pos(prev_start_line, prev_end_line)
        prev_col = prev_pos - prev_start_pos
        prev_type = self.db._sym_table[token.name].__class__.__name__

        line1 = f"Redeclaration of token {realized.qname}"
        line2 = f"Redeclaration Occured on line {start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        line5 = f"Previous declaration occured on line {prev_start_line}, offset {prev_col}"
        line6 = f"Full lines follows After line break"
        line7 = self.lexer.data[prev_start_pos:prev_end_pos]
        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}\n{line6}\n{line7}\n")

    def quantified_toolname_error(self, tool: QuantifiedItem | QuantifiedFluid):
        line_start_pos, line_end_pos = self.get_line_pos(tool.original_spec.start_line, tool.item.end_line)
        col = tool.original_spec.pos - line_start_pos
        line1 = f"Declaration of tool with quantity"
        line2 = f"Declaration Occured on line {tool.original_spec.start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n")

    def err_lines(self, *lines: str | None):
        out = []
        for line in lines:
            if line is None:
                continue
            else:
                out.append(line)
                out.append('\n')
        return ''.join(out)

    def undefined_symbol_error(self, item: QuantifiedItem | QuantifiedFluid):
        if isinstance(item.original_spec, ImpliedNumber):
            original_spec = item.item
        else:
            original_spec = item.original_spec

        line_start_pos, line_end_pos = self.get_line_pos(original_spec.start_line, item.item.end_line)
        col = original_spec.pos - line_start_pos
        item = item.item
        if isinstance(item, Varname):
            line3 = None
        elif isinstance(item, (SubstitutedVarname, SubstitutedMaterializedVarname, MaterializedVarname)):
            varname_defined = self.db.get_sym(item.name) is not None
            material_defined = self.db.get_sym(item.material) is not None

            if varname_defined:
                if material_defined:
                    line3 = f"Both Varname {item.name} and Material {item.material} defined. Perhaps this is an implicit declaration?"
                else:
                    line3 = f"Material {item.material} not defined"
            else:
                if material_defined:
                    line3 = f"Varname {item.name} not defined"
                else:
                    line3 = f"Neither Varname {item.name} nor Material {item.material} defined"
        else:
            raise RuntimeError(item.__class__.__name__)
        line1 = f"Undefined symnol {item.qname}"
        line2 = f"Declaration Occured on line {original_spec.start_line}, offset {col}"
        line4 = f"Full lines follows After line break"
        line5 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(self.err_lines(line1, line2, line3, line4, line5))

    def redeclaration_fluid2(self, token: Varname, error: TypeError):
        realized = error.args[1]
        start_line = token.start_line
        end_line = token.end_line
        pos = token.pos
        line_start_pos, line_end_pos = self.get_line_pos(start_line, end_line)
        col = pos - line_start_pos
        if token.name in self.built_in:
            line1 = f"Redeclaration of built-in token {token.name}"
            line2 = f"Redeclaration Occured on line {start_line}, offset {col}"
            line3 = f"Full lines follows After line break"
            line4 = self.lexer.data[line_start_pos:line_end_pos]

            raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n")

        prev_decl = self.db.prev_decl[token.name]
        prev_start_line = prev_decl.start_line
        prev_end_line = prev_decl.end_line
        prev_pos = prev_decl.pos
        prev_start_pos, prev_end_pos = self.get_line_pos(prev_start_line, prev_end_line)
        prev_col = prev_pos - prev_start_pos
        prev_type = self.db._sym_table[token.name].__class__.__name__

        line1 = f"Redelclaration of token of type {prev_type} redeclared as type {realized.__class__.__name__}"
        line2 = f"Redeclaration Occured on line {start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        line5 = f"Previous declaration occured on line {prev_start_line}, offset {prev_col}"
        line6 = f"Full lines follows After line break"
        line7 = self.lexer.data[prev_start_pos:prev_end_pos]
        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}\n{line6}\n{line7}\n")

    def error(self, got, *expected):
        if len(expected) == 1:
            expects = f"'{expected[0].__name__}'"
        elif len(expected) == 2:
            expects = f"'{expected[0].__name__}' or '{expected[1].__name__}'"
        else:
            names = [f"'{x.__name__}'" for x in expected]
            car = ', '.join(names[:-1])
            cdr = f', or {names[-1]}'
            expects = f'{car}{cdr}'
        start_line = got.start_line
        end_line = got.end_line
        pos = got.pos
        if (end_line + 1) > len(self.lexer.linetab):
            increased = self.lexer.increase_linetab(end_line + 1 - self.lexer.line)
        else:
            increased = 0
        line_start_pos = self.lexer.linetab[start_line - 1]
        col = pos - line_start_pos
        line_end_pos = self.lexer.linetab[end_line + 1 - 1]
        self.lexer.decrease_linetab(increased)
        line1 = f"Expected {expects}, got '{got.__class__.__name__}'"
        line2 = f"\tError Occured on line {start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}")

    def materialize_fluid_error(self, token: MaterializedVarname):
        line_start_pos, line_end_pos = self.get_line_pos(token.start_line, token.end_line)
        col = token.pos - line_start_pos
        line1 = "Declaration of fluid in #Materialize expression. Use #fluid expression instead"
        line2 = f"\tError Occured on line {token.start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}")

    def materialize_star_fluid_error(self, token: Varname):
        line_start_pos, line_end_pos = self.get_line_pos(token.start_line, token.end_line)
        col = token.pos - line_start_pos
        line1 = "Declaration of fluid in #Materialize* expression. Use #fluid expression instead"
        line2 = f"\tError Occured on line {token.start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}")

    def not_a_fluid_error(self, error: NotAFluidError):
        line1 = error.args[0]
        item, sym = error.quantified_fluid, error.hit_symbol
        if isinstance(item.original_spec, ImpliedNumber):
            original_spec = item.item
        else:
            original_spec = item.original_spec

        line_start_pos, line_end_pos = self.get_line_pos(original_spec.start_line, item.item.end_line)
        col = original_spec.pos - line_start_pos
        line2 = f"\tError Occured on line {original_spec.start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f'{line1}\n{line2}\n{line3}\n{line4}\n')

    def not_a_materialized_fluid_error(self, error: NotAMaterializedFluidError):
        line1 = error.args[0]
        item = error.quantified_fluid
        if isinstance(item.original_spec, ImpliedNumber):
            original_spec = item.item
        else:
            original_spec = item.original_spec
        line_start_pos, line_end_pos = self.get_line_pos(original_spec.start_line, item.item.end_line)
        col = original_spec.pos - line_start_pos
        line2 = f"\tError Occured on line {original_spec.start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f'{line1}\n{line2}\n{line3}\n{line4}\n')

    def materialize_star_symbol_type_error(self, material: Varname, error: SymbolTypeError):
        line1 = error.args[0]
        line_start_pos, line_end_pos = self.get_line_pos(material.start_line, material.end_line)
        col = material.pos - line_start_pos
        line2 = f"\tError Occured on line {material.start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f'{line1}\n{line2}\n{line3}\n{line4}\n')

    def symbol_type_error(self, product: QuantifiedItem, error: SymbolTypeError):
        line1 = error.args[0]
        product = product.item
        line_start_pos, line_end_pos = self.get_line_pos(product.start_line, product.end_line)
        col = product.pos - line_start_pos
        line2 = f"\tError Occured on line {product.start_line}, offset {col}"
        line3 = f"Full lines follows After line break"
        line4 = self.lexer.data[line_start_pos:line_end_pos]
        raise RuntimeError(f'{line1}\n{line2}\n{line3}\n{line4}\n')

    def circuit_decl(self):
        # < already consumed by previos method

        nxt = self.lexer.advance()
        if not isinstance(nxt, Number):
            self.error(nxt, Number)
        circuit = nxt.amount
        nxt = self.lexer.advance()
        if not isinstance(nxt, GT):
            self.error(nxt, GT)
        return circuit, nxt

    def machine_spec(self):
        nxt = self.lexer.advance()
        start = nxt
        if not isinstance(nxt, Colon):
            raise RuntimeError("Fatal Logic Error")
        nxt = self.lexer.advance()
        if isinstance(nxt, Varname) and nxt.name in TierSpec.__members__:
            tier = TierSpec.__members__[nxt.name]
            nxt = self.lexer.advance()

        else:
            tier = TierSpec.ULV

        if not isinstance(nxt, Varname):
            self.error(nxt, Varname)

        tool_name = nxt.name
        end = nxt
        nxt = self.lexer.peek()

        if isinstance(nxt, LT):
            circuit_decl_start = nxt
            self.lexer.advance()
            circuit, cicuit_decl_end = self.circuit_decl()
            return MachineSpec(start, cicuit_decl_end, tier, tool_name, circuit)

        else:
            return MachineSpec(start, end, tier, tool_name, 0)

    def item_list(self):
        item_list = []
        while True:
            nxt = self.lexer.peek()
            if isinstance(nxt, (Number, FluidSpec)):
                quant = nxt
                self.lexer.advance()
                nxt = self.lexer.peek()
            else:
                quant = ImpliedNumberSingleton

            if not isinstance(nxt, (Varname, MaterializedVarname)):
                if quant is ImpliedNumberSingleton:
                    break
                else:
                    self.error(nxt, Varname, MaterializedVarname)
            self.lexer.advance()
            item = nxt
            quantitem = quantifiedValue(quant, item)
            nxt = self.lexer.peek()
            if isinstance(nxt, SemiColon):
                self.lexer.advance()
            item_list.append(quantitem)
        return item_list

    def product_list(self):
        product_list = []
        start = self.lexer.peek()
        while True:
            nxt = self.lexer.advance()
            if isinstance(nxt, (Number, FluidSpec)):
                quant = nxt
                nxt = self.lexer.advance()
            else:
                quant = ImpliedNumberSingleton

            if not isinstance(nxt, (Varname, MaterializedVarname)):
                self.error(nxt, Varname, MaterializedVarname)

            item = nxt
            quantitem = quantifiedValue(quant, item)
            product_list.append(quantitem)
            prev = nxt
            nxt = self.lexer.peek()
            if isinstance(nxt, Comma):
                self.lexer.advance()
                continue
            else:
                break
        end = prev

        return product_list, start, end

    def add_recipe(self, recipe: RecipeDeclaration | SubstitutedRecipeDeclaration):
        products = []
        for product in recipe.product_list:
            try:
                resolved = product.resolve(self.db)
            except UndefinedSymbolError:
                self.undefined_symbol_error(product)
            except SymbolTypeError as e:
                self.symbol_type_error(product, e)
            if isinstance(resolved, Tool):
                raise ValueError("Recipe cannot genreate a Tool")
            products.append(resolved)

        items = []
        tools = []
        for item in recipe.items:
            try:
                resolved = item.resolve(self.db)
            except QuantifiedToolError:
                self.quantified_toolname_error(item)
            except UndefinedSymbolError:
                self.undefined_symbol_error(item)
            except NotAFluidError as e:
                self.not_a_fluid_error(e)
            except NotAMaterializedFluidError as e:
                self.not_a_materialized_fluid_error(e)
            if isinstance(resolved, Tool):
                tools.append(resolved)
            else:
                items.append(resolved)
        if self.print_recipes:
            print(f"Recipe for {products}")
            for item in items:
                print(f'\t{item}')
            if tools:
                print("")
                for tool in tools:
                    print(f"\t{tool}")

        station = self.db.resolve_station(recipe.machine)
        real_recipe = Recipe(products, items, recipe.tier, recipe.circuit, station, tools)
        self.db.add_recipe(real_recipe)

    def recipe_decl(self):
        product_list, start, end = self.product_list()
        if isinstance(self.lexer.peek(), Colon):
            machine_spec = self.machine_spec()
        else:
            machine_spec = Workbench_spec

        nxt = self.lexer.advance()
        if not isinstance(nxt, LCurly):
            self.error(nxt, LCurly)

        items = self.item_list()
        nxt = self.lexer.advance()
        if not isinstance(nxt, RCurly):
            self.error(nxt, RCurly)
        end = nxt
        return RecipeDeclaration(start, end, product_list, machine_spec.tier, machine_spec.name, machine_spec.circuit,
                                 items)

    def comma_seperated_list_ex(self, typ: type, fin: type):

        item = self.lexer.advance()
        if not isinstance(item, typ):
            self.ext_error("Expected at least 1 item in prefix list", item, typ)
        nxt = self.lexer.advance()
        if isinstance(nxt, fin):
            return [item], nxt
        elif not isinstance(nxt, Comma):
            self.error(nxt, Comma)
        items = [item]
        while True:
            item = self.lexer.advance()
            if not isinstance(item, typ):
                self.ext_error("Expected another item in prefix list after Comma", item, typ)
            items.append(item)
            nxt = self.lexer.advance()

            if isinstance(nxt, fin):
                return items, nxt
            elif not isinstance(nxt, Comma):
                self.error(nxt, Comma)
            else:
                continue

    def varname_comma_seperated_list(self):
        return self.comma_seperated_list_ex(Varname, EOP)

    def materialized_varname_comma_seperated_list(self):
        return self.comma_seperated_list_ex(MaterializedVarname, EOP)

    def materialize_star_component_list(self):
        return self.comma_seperated_list_ex(Varname, RParen)

    def materialize_star(self, spec):
        nxt = self.lexer.advance()
        if isinstance(nxt, LParen):
            components, _ = self.materialize_star_component_list()
        elif isinstance(nxt, Varname):
            components = [nxt]
        else:
            self.error(nxt, LParen, Varname)

        nxt = self.lexer.advance()
        if not isinstance(nxt, Comma):
            self.error(nxt, Comma)
        materials, end = self.varname_comma_seperated_list()
        return MaterializeStar(spec, end, spec, components, materials)

    def prefix(self):
        spec = self.lexer.advance()
        match spec.prefix:
            case PrefixType.fluid:
                lst, end = self.varname_comma_seperated_list()
                ret = Fluids(spec, end, spec, lst)
                try:
                    for fluid in ret.items:
                        self.db.add_fluid(fluid)

                except ValueError as e:
                    self.redeclaration_fluid(fluid, e)
                except TypeError as e:
                    self.redeclaration_fluid2(fluid, e)

            case PrefixType.station:
                lst, end = self.varname_comma_seperated_list()
                ret = Stations(spec, end, spec, lst)
                try:
                    for station in ret.items:
                        self.db.add_station(station)
                except ValueError:
                    self.redeclaration(station, "Staion")
            case PrefixType.component:
                lst, end = self.varname_comma_seperated_list()
                ret = Components(spec, end, spec, lst)
                try:
                    for component in ret.items:
                        self.db.add_component(component)
                except ValueError:
                    self.redeclaration(component, "Component")
            case PrefixType.tool:
                lst, end = self.varname_comma_seperated_list()
                ret = Tools(spec, end, spec, lst)
                try:
                    for tool in ret.items:
                        self.db.add_tool(tool)
                except ValueError:
                    self.redeclatation(tool, "Tool")
            case PrefixType.named:
                lst, end = self.varname_comma_seperated_list()
                ret = Named(spec, end, spec, lst)
                try:
                    for named in ret.items:
                        self.db.add_named_item(named)
                except ValueError:
                    self.redeclatation(named, "NamedItem")
            case PrefixType.material:
                lst, end = self.varname_comma_seperated_list()
                ret = Materials(spec, end, spec, lst)
                try:
                    for material in ret.items:
                        self.db.add_material(material)
                except ValueError:
                    self.redeclatation(material, "Material")
            case PrefixType.materialize:
                lst, end = self.materialized_varname_comma_seperated_list()
                ret = Materialized(spec, end, spec, lst)
                try:
                    for materialized in ret.items:
                        if materialized.name == 'fluid':
                            self.materialize_fluid_error(materialized)
                        self.db.add_materialized_component(materialized)
                except UndefinedSymbolError:
                    self.undefined_symbol_error(materialized)

                except RedeclarationError:
                    self.redeclaration(materialized, "MaterializedComponent")
            case PrefixType.materialize_star:

                ret = self.materialize_star(spec)

                try:
                    for component in ret.components:
                        comp = self.db.resolve_component(component.name)

                        if comp is None:
                            self.undeclared_error(component, "Component")
                        if component.name == 'fluid':
                            self.materialize_star_fluid_error(component)
                        for material in ret.materials:
                            try:
                                mat = self.db.resolve_material(material.name)
                            except SymbolTypeError as e:
                                self.materialize_star_symbol_type_error(material, e)
                            if mat is None:
                                self.undeclared_error(material, "Material")
                            self.db.add_materialized_star_item(comp, mat, MaterialzeStarItem(ret, component, material))

                except ValueError:
                    self.redeclaration_star(component, material, ret)
            case _:
                assert False, f"Fatal parsing error, unknown lexeme {spec.prefix!r}"
        return ret

    def add_generic_recipe(self, generic_recipe_decl: GenericRecipeDeclaration):
        global e
        recipes = []
        e = generic_recipe_decl
        for generic in generic_recipe_decl.generic_list:
            try:
                recipe = generic_recipe_decl.substitute(generic)
            except Exception as e:
                line1 = e.args[0]
                line2 = f"Error Occured due to substitution with item {generic}"
                line_start_pos, line_end_pos = self.get_line_pos(generic_recipe_decl.start.start_line,
                                                                 generic_recipe_decl.end.end_line)
                col = generic_recipe_decl.start.pos - line_start_pos
                line3 = f"Generic recipe declared on line {generic_recipe_decl.start.start_line}, col {col}"
                line4 = f"Full lines follows After line break"
                line5 = self.lexer.data[line_start_pos:line_end_pos]

                raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}\n")

            try:
                self.add_recipe(recipe)
            except Exception as e:
                line1 = e.args[0]
                line2 = f"Error Occured due to substitution with item {generic}"
                line_start_pos, line_end_pos = self.get_line_pos(generic_recipe_decl.start.start_line,
                                                                 generic_recipe_decl.end.end_line)
                col = generic_recipe_decl.start.pos - line_start_pos
                line3 = f"Generic recipe declared on line {generic_recipe_decl.start.start_line}, col {col}"
                line4 = f"Full lines follows After line break"
                line5 = self.lexer.data[line_start_pos:line_end_pos]
                raise RuntimeError(f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}\n")

    def generic_recipe_decl(self):
        generic = self.lexer.advance()
        generic_t = self.lexer.advance()
        if not isinstance(generic_t, Varname):
            self.error(generic_t, Varname)
        lt = self.lexer.advance()
        if not isinstance(lt, LT):
            self.error(lt, LT)

        generic_list, end = self.comma_seperated_list_ex((MaterializedVarname, Varname), GT)

        recipe = self.recipe_decl()

        for i in range(len(recipe.product_list)):
            product = recipe.product_list[i]
            if isinstance(product.item, MaterializedVarname):
                if product.item.material == generic_t.name:
                    recipe.product_list[i].item = GenericMaterialMaterializedVarname(product.item, product.item.name)
                elif product.item.component == generic_t.name:
                    recipe.product_list[i].item = GenericComponentMaterializedVarname(product.item,
                                                                                      product.item.material)
            else:
                if product.item.name == generic_t.name:
                    recipe.product_list[i].item = GenericItem(product.item)
        for i in range(len(recipe.items)):
            item = recipe.items[i]
            if isinstance(item.item, MaterializedVarname):
                if item.item.material == generic_t.name:
                    recipe.items[i].item = GenericMaterialMaterializedVarname(item.item, item.item.name)
                elif item.item.component == generic_t.name:
                    recipe.items[i].item = GenericComponentMaterializedVarname(item.item, item.item.material)
            else:
                if item.item.name == generic_t.name:
                    recipe.items[i].item = GenericItem(item.item)
        ret = GenericRecipeDeclaration(generic, recipe.end, generic_list, recipe.product_list, recipe.tier,
                                       recipe.machine, recipe.circuit, recipe.items, generic_t)
        self.add_generic_recipe(ret)
        return ret

    def expression(self):
        nxt = self.lexer.peek()
        if isinstance(nxt, Prefix):
            return self.prefix()
        elif isinstance(nxt, (Number, Varname, MaterializedVarname)):
            ret = self.recipe_decl()
            self.add_recipe(ret)
            return ret
        elif isinstance(nxt, GenericDecl):
            return self.generic_recipe_decl()
        else:
            self.error(nxt, Prefix, RecipeDeclaration)

    def parse(self):
        exprs = []
        while True:
            nxt = self.lexer.peek()
            if isinstance(nxt, EOF):
                self.lexer.advance()
                break
            else:
                exprs.append(self.expression())
        self.solver = Solver(self.db.get_items(), self.db)
        return exprs


from recipeDB2.solver import Solver

if __name__ == "__main__":
    file = Path(r"C:\Users\josep\Desktop\recipes.txt")
    l = Parser(file)
    with l:
        elems = l.parse()
    print("Test")
    l.db.solve()

    l.db.load_symbols()
    # solved = l.solver.union_calc([crab])
    # solved.pretty_print()
    print("#" * 80)
    itemizer_2 = l.solver.solve_solver2([water_pump_multi_block])
    solved2 = itemizer_2.solve()
    solved2.pretty_print()
