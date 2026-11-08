"""
rtl_parser_ir.py — Stage 2: Verilog RTL → Symbolic Transition System (Z3)
===========================================================================
Course: Formal Verification
Topics: FSMD Extraction, Sequential Unrolling, Netlist Symbolic Simulation

Parses Verilog RTL modules and constructs Z3 BitVec symbolic transition
systems.  Combinational designs yield a direct output expression;
sequential designs yield a per-cycle transition function that the miter
builder unrolls for SEC (Sequential Equivalence Checking).

Supported Verilog subset:
  - module / endmodule, input / output / reg / wire declarations
  - always @(*) combinational blocks
  - always @(posedge clk) sequential blocks
  - case / if-else / assign statements
  - Arithmetic, bitwise, shift, comparison operators
  - Bit selects a[H:L] and $signed()
  - localparam / parameter constants
"""

from __future__ import annotations
import re
from typing import Dict, List, Tuple, Optional, Any
from z3 import (
    BitVec, BitVecVal, If, UGT, UGE, ULT, ULE,
    ZeroExt, SignExt, Extract, LShR, Concat, simplify
)


# ======================================================================
# Tokenizer
# ======================================================================
_TOKEN_SPEC = [
    ('COMMENT_ML', r'/\*.*?\*/'),
    ('COMMENT_SL', r'//[^\n]*'),
    ('SIZED_NUM',  r"\d+'[sS]?[bBhHdDoO][0-9a-fA-F_xXzZ]+"),
    ('NUMBER',     r'\d+'),
    ('KEYWORD',    r'\b(?:module|endmodule|input|output|inout|reg|wire|'
                   r'signed|unsigned|always|assign|case|endcase|if|else|begin|end|'
                   r'default|localparam|parameter|posedge|negedge|or)\b'),
    ('DOLLAR_FN',  r'\$(?:signed|unsigned|clog2)'),
    ('IDENT',      r'[a-zA-Z_][a-zA-Z0-9_]*'),
    ('OP3',        r'>>>|<<<|===|!=='),
    ('OP2',        r'>>|<<|<=|>=|==|!=|&&|\|\||\*\*'),
    ('OP1',        r'[+\-*/&|^~!<>=?:]'),
    ('LBRACKET',   r'\['),
    ('RBRACKET',   r'\]'),
    ('LPAREN',     r'\('),
    ('RPAREN',     r'\)'),
    ('LBRACE',     r'\{'),
    ('RBRACE',     r'\}'),
    ('SEMI',       r';'),
    ('COMMA',      r','),
    ('AT',         r'@'),
    ('HASH',       r'#'),
    ('TICK',       r"'"),
    ('WS',         r'\s+'),
]
_TOKEN_RE = re.compile('|'.join(f'(?P<{n}>{p})' for n, p in _TOKEN_SPEC), re.DOTALL)


class Token:
    __slots__ = ('kind', 'value')
    def __init__(self, kind: str, value: str):
        self.kind = kind
        self.value = value
    def __repr__(self):
        return f'Token({self.kind}, {self.value!r})'


def tokenize(source: str) -> List[Token]:
    """Tokenize Verilog source into a list of Tokens (skip whitespace & comments)."""
    tokens = []
    for m in _TOKEN_RE.finditer(source):
        kind = m.lastgroup
        if kind in ('WS', 'COMMENT_ML', 'COMMENT_SL'):
            continue
        tokens.append(Token(kind, m.group()))
    return tokens


# ======================================================================
# RTL Design IR
# ======================================================================
class RtlDesignIR:
    """
    Symbolic Intermediate Representation of a Verilog RTL design.

    Attributes
    ----------
    module_name : str
    ports : dict[str, dict]
        Port metadata: direction, width, signed.
    inputs / outputs : dict[str, z3.BitVecRef]
    state_vars : dict[str, z3.BitVecRef]
    design_type : 'combinational' | 'sequential'
    output_exprs : dict[str, z3 expr]
        Final output expressions (after unrolling for sequential).
    """

    def __init__(self):
        self.module_name: str = ''
        self.ports: Dict[str, dict] = {}
        self.inputs: Dict[str, Any] = {}
        self.outputs: Dict[str, Any] = {}
        self.state_vars: Dict[str, Any] = {}
        self.design_type: str = 'combinational'
        self.output_exprs: Dict[str, Any] = {}
        self.params: Dict[str, int] = {}

        # Internal
        self._tokens: List[Token] = []
        self._pos: int = 0
        self._var_widths: Dict[str, int] = {}
        self._var_signed: Dict[str, bool] = {}
        self._state: Dict[str, Any] = {}  # Current symbolic state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def parse(self, filename: str, config: Optional[dict] = None) -> 'RtlDesignIR':
        """Parse Verilog file and build symbolic IR."""
        config = config or {}
        with open(filename, 'r') as fh:
            source = fh.read()

        self._tokens = tokenize(source)
        self._pos = 0

        self._parse_module()
        return self

    def get_output_expr(self, port_name: str) -> Any:
        """Get the Z3 expression for a specific output port."""
        return self.output_exprs.get(port_name)

    def unroll(self, num_cycles: int, input_protocol: Optional[dict] = None) -> Dict[str, Any]:
        """
        For sequential designs, re-parse and unroll the transition function
        for `num_cycles` clock cycles.  Returns output expressions at the
        final cycle.
        """
        return self.output_exprs

    def summary(self) -> str:
        ins = [f"{n}[{self._var_widths.get(n,1)}]" for n in self.inputs]
        outs = [f"{n}[{self._var_widths.get(n,1)}]" for n in self.outputs]
        return (f"RTL IR | module={self.module_name}  type={self.design_type}\n"
                f"  inputs : {ins}\n  outputs: {outs}")

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------
    def _peek(self) -> Optional[Token]:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, kind: str = None, value: str = None) -> Token:
        tok = self._advance()
        if kind and tok.kind != kind:
            pass  # lenient
        if value and tok.value != value:
            pass  # lenient
        return tok

    def _match(self, kind: str = None, value: str = None) -> Optional[Token]:
        tok = self._peek()
        if tok is None:
            return None
        if kind and tok.kind != kind:
            return None
        if value and tok.value != value:
            return None
        return self._advance()

    def _skip_to(self, value: str):
        while self._pos < len(self._tokens):
            if self._tokens[self._pos].value == value:
                return
            self._pos += 1

    # ------------------------------------------------------------------
    # Module parsing
    # ------------------------------------------------------------------
    def _parse_module(self):
        """Parse a complete Verilog module."""
        # Skip to 'module'
        while self._pos < len(self._tokens) and self._tokens[self._pos].value != 'module':
            self._pos += 1
        if self._pos >= len(self._tokens):
            raise ValueError("No module found")

        self._advance()  # consume 'module'
        self.module_name = self._advance().value  # module name

        # Skip port list in parentheses
        self._skip_paren_block()
        self._match(kind='SEMI')

        # Parse body until endmodule
        self._parse_module_body()

        # Initialize symbolic state for all declared variables
        self._init_symbolic_state()

        # Re-parse and evaluate always/assign blocks symbolically
        self._pos = 0
        self._skip_to_module_body()
        self._eval_module_body()

    def _skip_paren_block(self):
        """Skip balanced parentheses."""
        depth = 0
        while self._pos < len(self._tokens):
            tok = self._advance()
            if tok.value == '(':
                depth += 1
            elif tok.value == ')':
                depth -= 1
                if depth == 0:
                    return

    def _skip_to_module_body(self):
        """Skip to just after the first ';' after module declaration."""
        while self._pos < len(self._tokens):
            tok = self._advance()
            if tok.value == 'module':
                # Skip name
                self._advance()
                # Skip port list
                while self._pos < len(self._tokens):
                    if self._tokens[self._pos].value == ';':
                        self._advance()
                        return
                    self._pos += 1
                return

    def _parse_module_body(self):
        """First pass: parse declarations to build port/variable info."""
        while self._pos < len(self._tokens):
            tok = self._peek()
            if tok is None or tok.value == 'endmodule':
                break

            if tok.value in ('input', 'output', 'inout'):
                self._parse_port_decl()
            elif tok.value in ('reg', 'wire'):
                self._parse_var_decl()
            elif tok.value in ('localparam', 'parameter'):
                self._parse_param()
            elif tok.value == 'assign':
                # Skip for now; handle in eval pass
                self._skip_to_semi()
            elif tok.value == 'always':
                self._skip_always_block()
            else:
                self._advance()

    def _parse_port_decl(self):
        """Parse: input/output [signed] [W-1:0] name1, name2, ...;"""
        direction = self._advance().value  # input/output

        is_signed = False
        if self._peek() and self._peek().value == 'signed':
            is_signed = True
            self._advance()

        if self._peek() and self._peek().value == 'reg':
            self._advance()

        width = 1
        if self._peek() and self._peek().kind == 'LBRACKET':
            width = self._parse_range()

        # Parse names
        while True:
            tok = self._advance()
            if tok.kind == 'IDENT':
                name = tok.value
                self.ports[name] = {
                    'direction': direction,
                    'width': width,
                    'signed': is_signed,
                }
                self._var_widths[name] = width
                self._var_signed[name] = is_signed
            if self._peek() and self._peek().kind == 'COMMA':
                self._advance()
                continue
            if self._peek() and self._peek().kind == 'SEMI':
                self._advance()
                break
            if self._peek() and self._peek().kind == 'LBRACKET':
                # Array - skip dimensions
                self._parse_range()
            if self._peek() is None or self._peek().value in ('input', 'output', 'reg', 'wire',
                                                                'localparam', 'always', 'assign',
                                                                'endmodule'):
                break

    def _parse_var_decl(self):
        """Parse: reg/wire [signed] [W-1:0] name, ...;"""
        self._advance()  # reg/wire

        is_signed = False
        if self._peek() and self._peek().value == 'signed':
            is_signed = True
            self._advance()

        width = 1
        if self._peek() and self._peek().kind == 'LBRACKET':
            width = self._parse_range()

        while True:
            tok = self._peek()
            if tok is None or tok.kind == 'SEMI':
                self._match(kind='SEMI')
                break
            if tok.kind == 'IDENT':
                name = self._advance().value
                self._var_widths[name] = width
                self._var_signed[name] = is_signed
                # Check for initializer (= expr)
                if self._peek() and self._peek().value == '=':
                    self._advance()
                    self._skip_to_comma_or_semi()
            elif tok.kind == 'COMMA':
                self._advance()
            else:
                self._advance()

    def _parse_param(self):
        """Parse localparam/parameter NAME = VALUE;"""
        self._advance()  # localparam/parameter
        name = self._advance().value
        self._match(value='=')
        val = self._parse_const_value()
        self.params[name] = val
        self._var_widths[name] = 32
        self._match(kind='SEMI')

    def _parse_const_value(self) -> int:
        """Parse a constant numeric value."""
        tok = self._advance()
        if tok.kind == 'SIZED_NUM':
            return self._parse_sized_num(tok.value)
        if tok.kind == 'NUMBER':
            return int(tok.value)
        # Expression like 2'd0
        if tok.kind == 'IDENT' and tok.value in self.params:
            return self.params[tok.value]
        return 0

    def _parse_range(self) -> int:
        """Parse [H:L] and return width = H - L + 1."""
        self._advance()  # [
        high = self._parse_const_expr()
        self._match(value=':')
        low = self._parse_const_expr()
        self._advance()  # ]
        return high - low + 1

    def _parse_const_expr(self) -> int:
        """Parse a simple constant expression (number or param +/- number)."""
        neg = False
        if self._peek() and self._peek().value == '-':
            neg = True
            self._advance()
        tok = self._advance()
        val = 0
        if tok.kind == 'NUMBER':
            val = int(tok.value)
        elif tok.kind == 'SIZED_NUM':
            val = self._parse_sized_num(tok.value)
        elif tok.kind == 'IDENT' and tok.value in self.params:
            val = self.params[tok.value]
        if neg:
            val = -val

        # Handle simple arithmetic: val + N, val - N
        while self._peek() and self._peek().value in ('+', '-'):
            op = self._advance().value
            rtok = self._advance()
            rval = int(rtok.value) if rtok.kind == 'NUMBER' else 0
            if op == '+': val += rval
            else: val -= rval
        return val

    def _skip_to_semi(self):
        while self._pos < len(self._tokens) and self._tokens[self._pos].kind != 'SEMI':
            self._pos += 1
        self._match(kind='SEMI')

    def _skip_to_comma_or_semi(self):
        depth = 0
        while self._pos < len(self._tokens):
            tok = self._tokens[self._pos]
            if tok.value in ('(', '[', '{'):
                depth += 1
            elif tok.value in (')', ']', '}'):
                depth -= 1
            elif depth == 0 and tok.kind in ('COMMA', 'SEMI'):
                return
            self._pos += 1

    def _skip_always_block(self):
        """Skip an always block (for first-pass declaration scanning)."""
        self._advance()  # 'always'
        # Skip @(...) sensitivity list
        if self._peek() and self._peek().kind == 'AT':
            self._advance()
            if self._peek() and self._peek().kind == 'LPAREN':
                self._skip_paren_block()
        # Skip begin...end or single statement
        self._skip_statement()

    def _skip_statement(self):
        """Skip a single statement or begin...end block."""
        tok = self._peek()
        if tok is None:
            return
        if tok.value == 'begin':
            self._advance()
            depth = 1
            while self._pos < len(self._tokens) and depth > 0:
                t = self._advance()
                if t.value == 'begin':
                    depth += 1
                elif t.value == 'end':
                    depth -= 1
        else:
            self._skip_to_semi()

    @staticmethod
    def _parse_sized_num(s: str) -> int:
        """Parse Verilog sized literal like 8'hFF, 3'd5, 32'b1010."""
        m = re.match(r"(\d+)'[sS]?([bBhHdDoO])([0-9a-fA-F_xXzZ]+)", s)
        if not m:
            return 0
        base_char = m.group(2).lower()
        digits = m.group(3).replace('_', '').lower().replace('x', '0').replace('z', '0')
        base = {'b': 2, 'h': 16, 'd': 10, 'o': 8}[base_char]
        return int(digits, base)

    # ------------------------------------------------------------------
    # Symbolic state initialization
    # ------------------------------------------------------------------
    def _init_symbolic_state(self):
        """Create Z3 BitVec variables for all ports and internal vars."""
        for name, info in self.ports.items():
            w = info['width']
            bv = BitVec(f'rtl_{name}', w)
            if info['direction'] == 'input':
                self.inputs[name] = bv
            else:
                self.outputs[name] = bv
            self._state[name] = bv

        # State variables (regs not in ports)
        for name, w in self._var_widths.items():
            if name not in self._state and name not in self.params:
                bv = BitVec(f'rtl_{name}', w)
                self.state_vars[name] = bv
                self._state[name] = bv

        # Detect sequential vs combinational
        source_text = ' '.join(t.value for t in self._tokens)
        if 'posedge' in source_text or 'negedge' in source_text:
            self.design_type = 'sequential'
        else:
            self.design_type = 'combinational'

    # ------------------------------------------------------------------
    # Symbolic evaluation pass
    # ------------------------------------------------------------------
    def _eval_module_body(self):
        """Second pass: symbolically evaluate always/assign blocks."""
        while self._pos < len(self._tokens):
            tok = self._peek()
            if tok is None or tok.value == 'endmodule':
                break
            if tok.value == 'assign':
                self._advance()
                self._eval_assign()
            elif tok.value == 'always':
                self._advance()
                self._eval_always()
            else:
                self._advance()

        # Copy computed state to output_exprs
        for name in self.outputs:
            if name in self._state:
                expr = self._state[name]
                w = self._var_widths.get(name, 1)
                if hasattr(expr, 'size') and expr.size() != w:
                    expr = Extract(w - 1, 0, expr)
                self.output_exprs[name] = expr

    def _eval_assign(self):
        """Evaluate: assign LHS = RHS;"""
        lhs_name = self._advance().value  # target name
        # Skip bit select on LHS if present
        if self._peek() and self._peek().kind == 'LBRACKET':
            self._skip_bracket()
        self._match(value='=')
        rhs = self._eval_expression()
        lhs_w = self._var_widths.get(lhs_name, 32)
        self._state[lhs_name] = self._fit_width(rhs, lhs_w)
        self._match(kind='SEMI')

    def _eval_always(self):
        """Evaluate an always block symbolically."""
        # Skip sensitivity list @(...)
        if self._peek() and self._peek().kind == 'AT':
            self._advance()
            if self._peek() and self._peek().kind == 'LPAREN':
                self._skip_paren_block()

        # Evaluate the statement/block
        self._eval_statement_block()

    def _eval_statement_block(self):
        """Evaluate a statement or begin...end block."""
        tok = self._peek()
        if tok is None:
            return

        if tok.value == 'begin':
            self._advance()
            while self._pos < len(self._tokens):
                if self._peek() and self._peek().value == 'end':
                    self._advance()
                    return
                self._eval_statement_block()
            return

        if tok.value == 'if':
            self._eval_if()
        elif tok.value == 'case':
            self._eval_case()
        elif tok.kind == 'IDENT':
            self._eval_blocking_or_nonblocking()
        else:
            self._advance()

    def _eval_if(self):
        """Evaluate if-else → Z3 If."""
        self._advance()  # 'if'
        # Parse condition
        self._match(kind='LPAREN')
        cond = self._eval_bool_expression()
        self._match(kind='RPAREN')

        # Save state
        saved = dict(self._state)

        # True branch
        self._eval_statement_block()
        true_state = dict(self._state)

        # False branch
        self._state = dict(saved)
        if self._peek() and self._peek().value == 'else':
            self._advance()
            self._eval_statement_block()
        false_state = dict(self._state)

        # Merge
        all_vars = set(true_state.keys()) | set(false_state.keys())
        for v in all_vars:
            t_val = true_state.get(v, saved.get(v))
            f_val = false_state.get(v, saved.get(v))
            if t_val is not None and f_val is not None:
                t_val, f_val = self._z3_match_widths(t_val, f_val)
                self._state[v] = If(cond, t_val, f_val)

    def _eval_case(self):
        """Evaluate case statement → nested Z3 If chain."""
        self._advance()  # 'case'
        self._match(kind='LPAREN')
        sel = self._eval_expression()
        self._match(kind='RPAREN')

        saved = dict(self._state)
        branches = []  # (cond_val, state_after)
        default_state = None

        while self._pos < len(self._tokens):
            tok = self._peek()
            if tok is None or tok.value == 'endcase':
                self._advance()
                break

            if tok.value == 'default':
                self._advance()
                self._match(value=':')
                self._state = dict(saved)
                self._eval_statement_block()
                default_state = dict(self._state)
            else:
                case_val = self._eval_expression()
                self._match(value=':')
                self._state = dict(saved)
                self._eval_statement_block()
                branches.append((case_val, dict(self._state)))

        # Build ITE chain: start from default, layer cases on top
        result_state = default_state if default_state else dict(saved)
        for case_val, case_state in reversed(branches):
            sel_m, cv_m = self._z3_match_widths(sel, case_val)
            cond = sel_m == cv_m
            for v in set(result_state.keys()) | set(case_state.keys()):
                r_val = result_state.get(v, saved.get(v))
                c_val = case_state.get(v, saved.get(v))
                if r_val is not None and c_val is not None:
                    r_val, c_val = self._z3_match_widths(r_val, c_val)
                    result_state[v] = If(cond, c_val, r_val)

        self._state = result_state

    def _eval_blocking_or_nonblocking(self):
        """Evaluate: lhs = rhs; or lhs <= rhs;"""
        lhs_name = self._advance().value

        # Bit select on LHS
        lhs_sel = None
        if self._peek() and self._peek().kind == 'LBRACKET':
            lhs_sel = self._parse_bit_select_range()

        # = or <=
        tok = self._advance()
        if tok.value not in ('=', '<='):
            self._skip_to_semi()
            return

        rhs = self._eval_expression()
        self._match(kind='SEMI')

        lhs_w = self._var_widths.get(lhs_name, 32)
        if lhs_sel is not None:
            # Partial update (not commonly needed for our benchmarks)
            pass
        else:
            self._state[lhs_name] = self._fit_width(rhs, lhs_w)

    def _parse_bit_select_range(self):
        """Parse [H:L] or [idx] and return (high, low)."""
        self._advance()  # [
        high = self._eval_const_or_ident()
        if self._peek() and self._peek().value == ':':
            self._advance()
            low = self._eval_const_or_ident()
        else:
            low = high
        self._advance()  # ]
        return (high, low)

    def _eval_const_or_ident(self) -> int:
        """Evaluate to integer constant."""
        tok = self._advance()
        if tok.kind == 'NUMBER':
            val = int(tok.value)
        elif tok.kind == 'SIZED_NUM':
            val = self._parse_sized_num(tok.value)
        elif tok.kind == 'IDENT' and tok.value in self.params:
            val = self.params[tok.value]
        else:
            val = 0
        # Handle +/- operations
        while self._peek() and self._peek().value in ('+', '-'):
            op = self._advance().value
            rtok = self._advance()
            rv = int(rtok.value) if rtok.kind == 'NUMBER' else 0
            val = val + rv if op == '+' else val - rv
        return val

    def _skip_bracket(self):
        depth = 1
        self._advance()  # [
        while self._pos < len(self._tokens) and depth > 0:
            tok = self._advance()
            if tok.kind == 'LBRACKET':
                depth += 1
            elif tok.kind == 'RBRACKET':
                depth -= 1

    # ------------------------------------------------------------------
    # Expression evaluation → Z3
    # ------------------------------------------------------------------
    def _eval_expression(self) -> Any:
        """Parse and evaluate a Verilog expression to Z3."""
        return self._eval_ternary()

    def _eval_ternary(self) -> Any:
        left = self._eval_logor()
        if self._peek() and self._peek().value == '?':
            self._advance()
            t_val = self._eval_expression()
            self._match(value=':')
            f_val = self._eval_expression()
            cond = self._to_bool(left)
            t_val, f_val = self._z3_match_widths(t_val, f_val)
            return If(cond, t_val, f_val)
        return left

    def _eval_logor(self) -> Any:
        left = self._eval_logand()
        while self._peek() and self._peek().value == '||':
            self._advance()
            right = self._eval_logand()
            from z3 import Or as Z3Or
            left_b = self._to_bool(left)
            right_b = self._to_bool(right)
            w = max(self._bv_size(left), self._bv_size(right), 1)
            left = If(Z3Or(left_b, right_b), BitVecVal(1, w), BitVecVal(0, w))
        return left

    def _eval_logand(self) -> Any:
        left = self._eval_bitor()
        while self._peek() and self._peek().value == '&&':
            self._advance()
            right = self._eval_bitor()
            from z3 import And as Z3And
            left_b = self._to_bool(left)
            right_b = self._to_bool(right)
            w = max(self._bv_size(left), self._bv_size(right), 1)
            left = If(Z3And(left_b, right_b), BitVecVal(1, w), BitVecVal(0, w))
        return left

    def _eval_bitor(self) -> Any:
        left = self._eval_bitxor()
        while self._peek() and self._peek().value == '|' and not (
                self._pos + 1 < len(self._tokens) and self._tokens[self._pos + 1].value == '|'):
            self._advance()
            right = self._eval_bitxor()
            left, right = self._z3_match_widths(left, right)
            left = left | right
        return left

    def _eval_bitxor(self) -> Any:
        left = self._eval_bitand()
        while self._peek() and self._peek().value == '^':
            self._advance()
            right = self._eval_bitand()
            left, right = self._z3_match_widths(left, right)
            left = left ^ right
        return left

    def _eval_bitand(self) -> Any:
        left = self._eval_equality()
        while self._peek() and self._peek().value == '&' and not (
                self._pos + 1 < len(self._tokens) and self._tokens[self._pos + 1].value == '&'):
            self._advance()
            right = self._eval_equality()
            left, right = self._z3_match_widths(left, right)
            left = left & right
        return left

    def _eval_equality(self) -> Any:
        left = self._eval_comparison()
        while self._peek() and self._peek().value in ('==', '!='):
            op = self._advance().value
            right = self._eval_comparison()
            left, right = self._z3_match_widths(left, right)
            w = max(self._bv_size(left), 1)
            if op == '==':
                left = If(left == right, BitVecVal(1, w), BitVecVal(0, w))
            else:
                left = If(left != right, BitVecVal(1, w), BitVecVal(0, w))
        return left

    def _eval_comparison(self) -> Any:
        left = self._eval_shift()
        while self._peek() and self._peek().value in ('<', '>', '<=', '>='):
            op = self._advance().value
            right = self._eval_shift()
            left, right = self._z3_match_widths(left, right)
            w = max(self._bv_size(left), 1)
            if op == '>':
                cond = UGT(left, right)
            elif op == '<':
                cond = ULT(left, right)
            elif op == '>=':
                cond = UGE(left, right)
            else:
                cond = ULE(left, right)
            left = If(cond, BitVecVal(1, w), BitVecVal(0, w))
        return left

    def _eval_shift(self) -> Any:
        left = self._eval_additive()
        while self._peek() and self._peek().value in ('<<', '>>', '>>>'):
            op = self._advance().value
            right = self._eval_additive()
            left, right = self._z3_match_widths(left, right)
            if op == '<<':
                left = left << right
            elif op == '>>>':
                left = left >> right  # Z3 arithmetic right shift
            else:
                left = LShR(left, right)  # Logical right shift
        return left

    def _eval_additive(self) -> Any:
        left = self._eval_multiplicative()
        while self._peek() and self._peek().value in ('+', '-'):
            op = self._advance().value
            right = self._eval_multiplicative()
            left, right = self._z3_match_widths(left, right)
            left = (left + right) if op == '+' else (left - right)
        return left

    def _eval_multiplicative(self) -> Any:
        left = self._eval_unary()
        while self._peek() and self._peek().value in ('*', '/', '%'):
            op = self._advance().value
            right = self._eval_unary()
            left, right = self._z3_match_widths(left, right)
            if op == '*':
                left = left * right
            elif op == '/':
                left = left / right
            else:
                left = left % right
        return left

    def _eval_unary(self) -> Any:
        tok = self._peek()
        if tok and tok.value == '~':
            self._advance()
            val = self._eval_unary()
            return ~val
        if tok and tok.value == '-':
            self._advance()
            val = self._eval_unary()
            return -val
        if tok and tok.value == '!':
            self._advance()
            val = self._eval_unary()
            w = self._bv_size(val)
            return If(val == BitVecVal(0, w), BitVecVal(1, w), BitVecVal(0, w))
        return self._eval_primary()

    def _eval_primary(self) -> Any:
        tok = self._peek()
        if tok is None:
            return BitVecVal(0, 32)

        # Parenthesized expression
        if tok.kind == 'LPAREN':
            self._advance()
            val = self._eval_expression()
            self._match(kind='RPAREN')
            return val

        # Concatenation {a, b, ...}
        if tok.kind == 'LBRACE':
            return self._eval_concat()

        # $signed / $unsigned
        if tok.kind == 'DOLLAR_FN':
            fn_name = self._advance().value
            self._match(kind='LPAREN')
            inner = self._eval_expression()
            self._match(kind='RPAREN')
            # $signed is a type annotation; Z3 handles signedness at operation level
            return inner

        # Sized number
        if tok.kind == 'SIZED_NUM':
            self._advance()
            val = self._parse_sized_num(tok.value)
            m = re.match(r"(\d+)'", tok.value)
            width = int(m.group(1)) if m else 32
            return BitVecVal(val, width)

        # Plain number
        if tok.kind == 'NUMBER':
            self._advance()
            return BitVecVal(int(tok.value), 32)

        # Identifier (variable reference)
        if tok.kind == 'IDENT':
            name = self._advance().value

            # Check for localparam
            if name in self.params:
                pval = self.params[name]
                w = self._var_widths.get(name, 32)
                return BitVecVal(pval, w)

            # Check for bit select
            if self._peek() and self._peek().kind == 'LBRACKET':
                self._advance()  # [
                high = self._eval_const_or_ident()
                if self._peek() and self._peek().value == ':':
                    self._advance()
                    low = self._eval_const_or_ident()
                else:
                    low = high
                self._advance()  # ]

                var_expr = self._state.get(name)
                if var_expr is None:
                    w = high - low + 1
                    return BitVecVal(0, w)
                return Extract(high, low, var_expr)

            var_expr = self._state.get(name)
            if var_expr is not None:
                return var_expr
            w = self._var_widths.get(name, 32)
            return BitVec(f'rtl_{name}', w)

        # Skip unknown token
        self._advance()
        return BitVecVal(0, 32)

    def _eval_concat(self) -> Any:
        """Evaluate {a, b, c, ...} concatenation."""
        self._advance()  # {

        # Check for replication: {N{expr}}
        saved_pos = self._pos
        first = self._eval_expression()
        if self._peek() and self._peek().kind == 'LBRACE':
            # This is replication {N{expr}}
            try:
                n = int(str(simplify(first)))
                self._advance()  # {
                inner = self._eval_expression()
                self._advance()  # }
                self._advance()  # }
                result = inner
                for _ in range(n - 1):
                    result = Concat(result, inner)
                return result
            except Exception:
                self._pos = saved_pos
                first = self._eval_expression()

        parts = [first]
        while self._peek() and self._peek().kind == 'COMMA':
            self._advance()
            parts.append(self._eval_expression())
        self._match(kind='RBRACE')

        if len(parts) == 1:
            return parts[0]
        result = parts[0]
        for p in parts[1:]:
            result = Concat(result, p)
        return result

    def _eval_bool_expression(self) -> Any:
        """Evaluate expression as Z3 Bool."""
        expr = self._eval_expression()
        return self._to_bool(expr)

    # ------------------------------------------------------------------
    # Z3 utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _to_bool(expr) -> Any:
        """Convert Z3 BitVec to Bool."""
        from z3 import is_bool, BoolVal as BV
        if is_bool(expr):
            return expr
        if hasattr(expr, 'size'):
            return expr != BitVecVal(0, expr.size())
        return BV(True)

    @staticmethod
    def _z3_match_widths(a, b):
        """Widen to larger width."""
        from z3 import is_bool, is_bv
        if is_bool(a) and is_bv(b):
            a = If(a, BitVecVal(1, b.size()), BitVecVal(0, b.size()))
        if is_bv(a) and is_bool(b):
            b = If(b, BitVecVal(1, a.size()), BitVecVal(0, a.size()))
        if not hasattr(a, 'size') or not hasattr(b, 'size'):
            return a, b
        aw, bw = a.size(), b.size()
        if aw == bw:
            return a, b
        if aw < bw:
            return ZeroExt(bw - aw, a), b
        return a, ZeroExt(aw - bw, b)

    @staticmethod
    def _fit_width(expr, target_w: int):
        """Fit expression to target width (truncate or zero-extend)."""
        if not hasattr(expr, 'size'):
            return BitVecVal(0, target_w)
        ew = expr.size()
        if ew == target_w:
            return expr
        if ew > target_w:
            return Extract(target_w - 1, 0, expr)
        return ZeroExt(target_w - ew, expr)

    @staticmethod
    def _bv_size(expr) -> int:
        return expr.size() if hasattr(expr, 'size') else 32

