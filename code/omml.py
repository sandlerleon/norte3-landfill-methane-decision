# -*- coding: utf-8 -*-
"""(Copied from the late-time-vacuum-decay repository, with accents added.) A small LaTeX -> Office Math (OMML) converter for the subset of LaTeX used in the paper.

Supported: letters and digits, Greek letters and common symbols (\\alpha ... \\sim \\lesssim ...), ^ and _ (also together), \\frac, \\sqrt,
\\left( ... \\right) delimiters, \\int with limits, \\rm / \\mathrm / \\text (upright text), operator names (\\ln, \\exp, ...), spacing commands.
The result is a native, editable Word equation (m:oMath) that can be inserted inline or as a display equation.
"""
import re

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

GREEK = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "kappa": "κ",
         "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "phi": "ϕ", "varphi": "φ", "chi": "χ", "psi": "ψ",
         "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Lambda": "Λ", "Sigma": "Σ", "Omega": "Ω", "Phi": "Φ", "ell": "ℓ", "hbar": "ℏ", "partial": "∂",
         "sim": "∼", "sum": "∑", "Upsilon": "Υ", "oint": "∮", "mu": "μ", "simeq": "≃", "approx": "≈", "lesssim": "≲", "gtrsim": "≳", "ll": "≪", "gg": "≫", "times": "×", "cdot": "·", "to": "→", "pm": "±",
         "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "infty": "∞", "propto": "∝", "equiv": "≡", "dots": "…", "ldots": "…", "nabla": "∇",
         "Rightarrow": "⇒", "Longrightarrow": "⇒", "prime": "′", "mid": "|", "langle": "⟨", "rangle": "⟩"}
FUNCS = {"ln", "log", "exp", "sin", "cos", "arcsin", "max", "min"}
SPACES = {",": " ", ";": " ", ":": " ", "quad": " ", "qquad": "  ", " ": " ", "!": ""}
M = lambda tag: OxmlElement("m:" + tag)


def _tokenize(s):
    toks, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[i:])
            toks.append(("cmd", m.group(1)))
            i += len(m.group(0))
        elif c in "{}^_":
            toks.append((c, c)); i += 1
        elif c == "$":
            i += 1
        elif c.isspace():
            toks.append(("sp", " ")); i += 1
        else:
            toks.append(("ch", c)); i += 1
    return toks


class _P:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek(); self.i += 1; return tok

    # sequence until a closing brace / \right / end
    def seq(self, stop_right=False):
        out, plain = [], False
        while True:
            k, v = self.peek()
            if k is None or k == "}" or (stop_right and k == "cmd" and v == "right"):
                break
            if k == "cmd" and v in ("rm", "mathrm", "bf", "mathbf") and False:
                pass
            node, plain = self.atom_with_scripts(plain)
            if node is not None:
                out.extend(node if isinstance(node, list) else [node])
        return out

    def group(self):
        k, _ = self.peek()
        if k == "{":
            self.take()
            body = self.seq()
            if self.peek()[0] == "}":
                self.take()
            return body
        node, _ = self.atom_with_scripts(False, no_scripts=True)
        return node if isinstance(node, list) else ([node] if node is not None else [])

    def atom_with_scripts(self, plain, no_scripts=False):
        k, v = self.peek()
        if k == "cmd" and v in ("rm", "mathrm"):
            self.take()
            # \rm applies to the rest of the current group; \mathrm takes a group
            if v == "mathrm":
                atom = ("plain", self.group())
            else:
                return None, True
        else:
            atom = self.atom(plain)
        if no_scripts:
            return atom, plain
        sub = sup = None
        while self.peek()[0] in ("^", "_"):
            op = self.take()[0]
            arg = self.group()
            if op == "^":
                sup = arg
            else:
                sub = arg
        if sub is not None or sup is not None:
            atom = ("script", atom, sub, sup)
        return atom, plain

    def atom(self, plain):
        k, v = self.take()
        if k == "{":
            body = self.seq()
            if self.peek()[0] == "}":
                self.take()
            return ("group", body)
        if k == "cmd":
            if v in ("frac", "tfrac", "dfrac"):
                a = self.group(); b = self.group()
                return ("frac", a, b)
            if v == "sqrt":
                return ("sqrt", self.group())
            if v in ("text", "operatorname"):
                if self.peek()[0] == "{":
                    self.take(); depth, buf = 1, ""
                    while self.i < len(self.t) and depth:
                        kk, vv = self.take()
                        if kk == "{":
                            depth += 1
                        elif kk == "}":
                            depth -= 1
                            if depth == 0:
                                break
                        elif kk in ("ch", "sp"):
                            buf += vv
                        elif kk == "cmd":
                            buf += GREEK.get(vv, SPACES.get(vv, vv))
                    return ("txt", buf)
                return ("txt", "")
            if v == "left":
                lk, lv = self.take()
                left = lv if lk == "ch" else ("." if lk == "cmd" and lv == "." else lv)
                body = self.seq(stop_right=True)
                rk, rv = self.take()           # \right
                ek, ev = self.take()
                right = ev
                return ("delim", left, body, right)
            if v in ("dot", "ddot", "tilde", "hat", "bar"):
                return ("acc", self.group(), {"dot": "̇", "ddot": "̈", "tilde": "̃", "hat": "̂", "bar": "̅"}[v])
            if v in ("int",):
                return ("int",)
            if v in SPACES:
                return ("space", SPACES[v])
            if v in GREEK:
                return ("ch", GREEK[v], plain)
            if v in FUNCS:
                return ("func", v)
            if v in ("{", "}", "%", "&", "_", "#"):
                return ("ch", v, plain)
            if v == "\\":
                return ("space", " ")
            return ("ch", v, plain)
        if k == "sp":
            return ("nop",)
        if k in ("^", "_"):
            return ("ch", k, plain)
        return ("ch", v, plain)


def _run(text, plain=False, nor=False):
    text = text.replace("---", "—").replace("--", "–")
    r = M("r")
    if plain or nor:
        # upright text: m:nor (honoured by Word and LibreOffice), kept in the math font
        pr = M("rPr"); pr.append(M("nor")); r.append(pr)
        wpr = OxmlElement("w:rPr")
        f = OxmlElement("w:rFonts"); f.set(qn("w:ascii"), "Cambria Math"); f.set(qn("w:hAnsi"), "Cambria Math"); wpr.append(f)
        it = OxmlElement("w:i"); it.set(qn("w:val"), "0"); wpr.append(it)
        r.append(wpr)
    t = M("t"); t.text = text; t.set(qn("xml:space"), "preserve")
    r.append(t)
    return r


def _emit(nodes, parent, plain=False):
    i = 0
    nodes = list(nodes)
    # merge consecutive plain characters into one run
    buf, bufplain = "", None

    def flush():
        nonlocal buf, bufplain
        if buf:
            parent.append(_run(buf, plain=bool(bufplain)))
            buf, bufplain = "", None

    for n in nodes:
        kind = n[0]
        if kind == "ch":
            pl = plain or n[2]
            if bufplain is not None and bufplain != pl:
                flush()
            buf += n[1].replace("-", "−"); bufplain = pl
            continue
        flush()
        if kind == "space":
            parent.append(_run(n[1], plain=True))
        elif kind == "func":
            parent.append(_run(n[1], plain=True))
        elif kind == "plain":
            _emit(n[1], parent, plain=True)
        elif kind == "txt":
            parent.append(_run(n[1], nor=True))
        elif kind == "nop":
            pass
        elif kind == "group":
            _emit(n[1], parent, plain)
        elif kind == "int":
            parent.append(_run("∫", plain=True))
        elif kind == "acc":
            ac = M("acc"); pr = M("accPr"); cc = M("chr"); cc.set(qn("m:val"), n[2]); pr.append(cc); ac.append(pr)
            e = M("e"); _emit(n[1], e, plain); ac.append(e); parent.append(ac)
        elif kind == "frac":
            f = M("f"); num = M("num"); den = M("den")
            _emit(n[1], num, plain); _emit(n[2], den, plain)
            f.append(num); f.append(den); parent.append(f)
        elif kind == "sqrt":
            rad = M("rad"); pr = M("radPr"); dh = M("degHide"); dh.set(qn("m:val"), "1"); pr.append(dh); rad.append(pr)
            rad.append(M("deg")); e = M("e"); _emit(n[1], e, plain); rad.append(e); parent.append(rad)
        elif kind == "delim":
            d = M("d"); pr = M("dPr")
            bc = M("begChr"); bc.set(qn("m:val"), "" if n[1] == "." else n[1]); pr.append(bc)
            ec = M("endChr"); ec.set(qn("m:val"), "" if n[3] == "." else n[3]); pr.append(ec)
            d.append(pr); e = M("e"); _emit(n[2], e, plain); d.append(e); parent.append(d)
        elif kind == "script":
            base, sub, sup = n[1], n[2], n[3]
            tag = "sSubSup" if (sub is not None and sup is not None) else ("sSub" if sub is not None else "sSup")
            s = M(tag); e = M("e")
            _emit([base], e, plain); s.append(e)
            if sub is not None:
                sb = M("sub"); _emit(sub, sb, plain); s.append(sb)
            if sup is not None:
                sp = M("sup"); _emit(sup, sp, plain); s.append(sp)
            parent.append(s)
    flush()


def tex_to_omml(tex):
    p = _P(_tokenize(tex))
    nodes = p.seq()
    while p.i < len(p.t):            # stray closing braces
        p.i += 1
        nodes += p.seq()
    om = M("oMath")
    _emit(nodes, om)
    return om


def set_size(om, half_points):
    """Give every math run an explicit font size (w:sz in half-points)."""
    from docx.oxml import OxmlElement as OE
    for r in om.iter(qn("m:r")):
        rpr = OE("w:rPr")
        sz = OE("w:sz"); sz.set(qn("w:val"), str(half_points)); rpr.append(sz)
        szc = OE("w:szCs"); szc.set(qn("w:val"), str(half_points)); rpr.append(szc)
        t = r.find(qn("m:t"))
        r.insert(list(r).index(t), rpr)
    return om
