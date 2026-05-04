"""
xml_parser.py
=============
Person 1 – XML Parsing & Input Handling
Formal Methods Project | NUCES Islamabad

Responsibilities:
  - Parse feature model XML into a Python data structure
  - Extract feature hierarchy (mandatory, optional, XOR, OR)
  - Translate the hierarchy into Propositional Logic formulas
  - Document every translation rule applied
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class Feature:
    """Represents a single feature node in the feature model."""
    name: str
    mandatory: bool = True          # True  → mandatory child
    parent: Optional[str] = None    # None  → root feature
    children: list = field(default_factory=list)          # direct Feature children
    group_type: Optional[str] = None  # 'xor' | 'or' | None (for grouped children)
    group_children: list = field(default_factory=list)    # children that belong to group


@dataclass
class Constraint:
    """A cross-tree constraint, given in English and/or Boolean form."""
    english: Optional[str] = None
    boolean_expr: Optional[str] = None
    propositional: Optional[str] = None   # filled in after translation


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class FeatureModelParser:
    """
    Parses a Feature Model XML file into:
      - a dict of Feature objects  (name → Feature)
      - a root feature name
      - a list of Constraint objects
    """

    def __init__(self, xml_source: str, is_file: bool = True):
        """
        Parameters
        ----------
        xml_source : str
            Path to an XML file (is_file=True) or raw XML string (is_file=False).
        is_file : bool
            Whether xml_source is a file path or raw XML text.
        """
        if is_file:
            tree = ET.parse(xml_source)
            self.root_elem = tree.getroot()
        else:
            self.root_elem = ET.fromstring(xml_source)

        self.features: dict[str, Feature] = {}
        self.root_name: Optional[str] = None
        self.constraints: list[Constraint] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self):
        """Entry point – parse both features and constraints."""
        # The XML root element is <featureModel>
        feature_elems = self.root_elem.findall("feature")
        if not feature_elems:
            raise ValueError("No <feature> elements found at the top level of the XML.")

        # There should be exactly one top-level feature (the root)
        root_elem = feature_elems[0]
        self.root_name = root_elem.get("name")
        self._parse_feature(root_elem, parent_name=None, mandatory=True)

        # Parse cross-tree constraints
        constraints_elem = self.root_elem.find("constraints")
        if constraints_elem is not None:
            for c_elem in constraints_elem.findall("constraint"):
                c = Constraint()
                eng = c_elem.find("englishStatement")
                if eng is not None:
                    c.english = eng.text.strip() if eng.text else None
                bexp = c_elem.find("booleanExpression")
                if bexp is not None:
                    c.boolean_expr = bexp.text.strip() if bexp.text else None
                self.constraints.append(c)

        return self

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_feature(self, elem, parent_name: Optional[str], mandatory: bool):
        """Recursively parse a <feature> element."""
        name = elem.get("name")
        if name is None:
            raise ValueError(f"Found a <feature> element without a 'name' attribute.")

        # mandatory attribute: if absent on root → True; if absent on child → False (optional)
        if parent_name is None:
            # Root is always mandatory
            is_mandatory = True
        else:
            raw = elem.get("mandatory", None)
            if raw is None:
                # absence of mandatory attribute means optional (per spec)
                is_mandatory = False
            else:
                is_mandatory = raw.lower() == "true"

        feat = Feature(name=name, mandatory=is_mandatory, parent=parent_name)
        self.features[name] = feat

        if parent_name is not None:
            self.features[parent_name].children.append(name)

        # Parse direct (non-grouped) child features
        for child_elem in elem.findall("feature"):
            self._parse_feature(child_elem, parent_name=name, mandatory=True)

        # Parse group children (XOR / OR)
        group_elem = elem.find("group")
        if group_elem is not None:
            gtype = group_elem.get("type", "").lower()
            feat.group_type = gtype
            if gtype not in ["xor", "or"]:
                raise ValueError(f"Invalid group type '{gtype}' in feature '{name}'")
            for gchild in group_elem.findall("feature"):
                gname = gchild.get("name")
                # grouped features: mandatory=False individually; group constraint applied separately
                gfeat = Feature(name=gname, mandatory=False, parent=name)
                self.features[gname] = gfeat
                feat.group_children.append(gname)
                # recurse in case grouped features have sub-features
                self._parse_feature(gchild, parent_name=name, mandatory=False)
                # correct: group children were added to feat.children by recursive call,
                # but we want them only in group_children → remove from children list
                if gname in feat.children:
                    feat.children.remove(gname)

    # ------------------------------------------------------------------
    # Pretty print (for debugging / report)
    # ------------------------------------------------------------------

    def print_hierarchy(self, name: Optional[str] = None, indent: int = 0):
        if name is None:
            name = self.root_name
        feat = self.features[name]
        kind = "mandatory" if feat.mandatory else "optional"
        prefix = "  " * indent
        print(f"{prefix}[{kind}] {name}")
        for child in feat.children:
            self.print_hierarchy(child, indent + 1)
        if feat.group_type:
            print(f"{prefix}  <{feat.group_type.upper()} group>")
            for gc in feat.group_children:
                self.print_hierarchy(gc, indent + 2)


# ---------------------------------------------------------------------------
# Propositional Logic Translator
# ---------------------------------------------------------------------------

class LogicTranslator:
    """
    Converts a parsed FeatureModelParser into propositional logic formulas.

    Translation Rules (documented)
    --------------------------------
    R0  Root:
            root                        (root feature is always selected)

    R1  Mandatory child:
            parent → child              (selecting parent forces child)
            child → parent              (selecting child forces parent)

    R2  Optional child:
            child → parent              (selecting child forces parent;
                                         but parent can exist without child)

    R3  XOR group (exactly one):
            parent → (A ∨ B ∨ … )      (at least one must be chosen)
            ¬A ∨ ¬B   for every pair    (at most one can be chosen)
            Each group member → parent  (any selection forces parent)

    R4  OR group (at least one):
            parent → (A ∨ B ∨ … )      (at least one must be chosen)
            Each group member → parent  (any selection forces parent)

    R5  Cross-tree constraint (requires):
            A → B                       (A requires B)

    R6  Cross-tree constraint (excludes):
            ¬A ∨ ¬B   i.e.  A → ¬B    (A and B cannot coexist)
    """

    def __init__(self, parser: FeatureModelParser):
        self.parser = parser
        self.formulas: list[dict] = []   # [{"rule": "R1", "formula": "...", "note": "..."}]

    def translate(self) -> list[dict]:
        """Run all translation rules and return the list of formula dicts."""
        self.formulas = []
        self._rule_root()
        self._rule_features()
        self._rule_cross_tree()
        return self.formulas

    # ------------------------------------------------------------------

    def _add(self, rule: str, formula: str, note: str):
        self.formulas.append({"rule": rule, "formula": formula, "note": note})

    def _rule_root(self):
        r = self.parser.root_name
        self._add("R0", r, f"Root feature '{r}' is always selected (mandatory by definition).")

    def _rule_features(self):
        for name, feat in self.parser.features.items():
            if feat.parent is None:
                continue  # root handled by R0

            parent = feat.parent

            # Non-grouped direct children
            if name in self.parser.features[parent].children:
                if feat.mandatory:
                    # R1 – mandatory
                    self._add("R1",
                               f"{parent} → {name}",
                               f"Mandatory: selecting '{parent}' forces '{name}'.")
                    self._add("R1",
                               f"{name} → {parent}",
                               f"Mandatory: '{name}' can only exist under '{parent}'.")
                else:
                    # R2 – optional
                    self._add("R2",
                               f"{name} → {parent}",
                               f"Optional: '{name}' can only appear if '{parent}' is selected.")

            # Group children are handled below at the group level (avoid duplication)

        # Group-level rules
        for name, feat in self.parser.features.items():
            if not feat.group_children:
                continue
            group = feat.group_children
            members = " ∨ ".join(group)

            if feat.group_type == "xor":
                # R3a – at least one
                self._add("R3",
                           f"{name} → ({members})",
                           f"XOR group under '{name}': at least one child must be selected.")
                # R3b – at most one (pairwise exclusion)
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        self._add("R3",
                                   f"¬{group[i]} ∨ ¬{group[j]}",
                                   f"XOR group: '{group[i]}' and '{group[j]}' cannot both be selected.")
                # R3c – each member implies parent
                for g in group:
                    self._add("R3",
                               f"{g} → {name}",
                               f"XOR member '{g}' can only be selected if parent '{name}' is selected.")

            elif feat.group_type == "or":
                # R4a – at least one
                self._add("R4",
                           f"{name} → ({members})",
                           f"OR group under '{name}': at least one child must be selected.")
                # R4b – each member implies parent
                for g in group:
                    self._add("R4",
                               f"{g} → {name}",
                               f"OR member '{g}' can only be selected if parent '{name}' is selected.")

    def _rule_cross_tree(self):
        """
        Translate English cross-tree constraints to propositional logic.
        Currently handles:
          - 'X requires Y'  →  X → Y    (R5)
          - 'X excludes Y'  →  ¬X ∨ ¬Y  (R6)
        For the sample model the English statement is parsed heuristically.
        """
        for c in self.parser.constraints:
            if c.boolean_expr:
                # Already in boolean form – clean up and store
                expr = (c.boolean_expr
                        .replace("implies", "→")
                        .replace("requires", "→")
                        .replace("excludes", "→ ¬"))
                self._add("R5/R6", expr,
                           f"Cross-tree (from booleanExpression): {c.boolean_expr}")
                c.propositional = expr

            elif c.english:
                prop = self._english_to_propositional(c.english)
                self._add("R5/R6", prop,
                           f"Cross-tree (from English): \"{c.english}\"")
                c.propositional = prop

    def _english_to_propositional(self, text: str) -> str:
        """
        Lightweight English → propositional logic converter for common patterns.
        Patterns supported:
          'X is required to Y'   →  interprets as Y → X  (Y requires X)
          'X requires Y'         →  X → Y
          'X excludes Y'         →  ¬X ∨ ¬Y
          'if X then Y'          →  X → Y
        Falls back to raw text if no pattern matches.
        """
        t = text.strip().rstrip(".")
        tl = t.lower()

        # Pattern: "The Location feature is required to filter the catalog by location."
        # Meaning: ByLocation → Location
        if "is required to" in tl:
            # "X is required to [action involving Y]"
            # X is the required feature, Y is the dependent feature
            # heuristic: extract feature names from known feature list
            feat_names = list(self.parser.features.keys())
            found = [fn for fn in feat_names if fn.lower() in tl]
            if len(found) >= 2:
                # The first mentioned feature that appears after subject → required
                # Convention: "Location is required to ByLocation" → ByLocation → Location
                required = found[0]
                dependent = found[-1]
                return f"{dependent} → {required}"

        # Pattern: "X requires Y"
        if " requires " in tl:
            parts = tl.split(" requires ")
            left = self._find_feature(parts[0])
            right = self._find_feature(parts[1])
            if left and right:
                return f"{left} → {right}"

        # Pattern: "X excludes Y"
        if " excludes " in tl:
            parts = tl.split(" excludes ")
            left = self._find_feature(parts[0])
            right = self._find_feature(parts[1])
            if left and right:
                return f"¬{left} ∨ ¬{right}"

        # Pattern: "if X then Y"
        if tl.startswith("if ") and " then " in tl:
            _, rest = tl.split("if ", 1)
            cond, cons = rest.split(" then ", 1)
            left = self._find_feature(cond)
            right = self._find_feature(cons)
            if left and right:
                return f"{left} → {right}"

        return f"[Manual translation needed]: {t}"

    def _find_feature(self, text: str) -> Optional[str]:
        """Return the feature name found in text (case-insensitive match)."""
        text_lower = text.lower()
        for fn in self.parser.features:
            if fn.lower() in text_lower:
                return fn
        return None

    # ------------------------------------------------------------------
    # Report helpers
    # ------------------------------------------------------------------

    def get_all_formulas(self) -> str:
        """Return a human-readable string of all formulas with rules and notes."""
        lines = ["=" * 60,
                 "PROPOSITIONAL LOGIC TRANSLATION",
                 "=" * 60]
        current_rule = None
        for entry in self.formulas:
            if entry["rule"] != current_rule:
                current_rule = entry["rule"]
                rule_desc = {
                    "R0": "Rule R0 – Root",
                    "R1": "Rule R1 – Mandatory Child",
                    "R2": "Rule R2 – Optional Child",
                    "R3": "Rule R3 – XOR Group",
                    "R4": "Rule R4 – OR Group",
                    "R5/R6": "Rule R5/R6 – Cross-Tree Constraints",
                }.get(current_rule, f"Rule {current_rule}")
                lines.append(f"\n{rule_desc}")
                lines.append("-" * 40)
            lines.append(f"  {entry['formula']}")
            lines.append(f"    ↳ {entry['note']}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def get_combined_formula(self) -> str:
        """Return all formulas joined with ∧ (AND) as a single big conjunction."""
        return " ∧\n".join(e["formula"] for e in self.formulas)
