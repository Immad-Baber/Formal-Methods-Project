"""
sat_solver.py
=============
Person 2 – SAT Solver Integration, Feature Verification, MWP & Constraint Checking
Formal Methods Project | NUCES Islamabad

Responsibilities:
  - T1: Encode all propositional logic formulas (from Person 1) into CNF and run PySAT
  - T2: Verify user-selected feature configurations (valid / invalid + reason)
  - T3: Compute the Minimum Working Product (MWP) – smallest valid configuration
  - T4: Check cross-tree constraints (requires / excludes) on any given selection

Dependencies:
  - fm_core.py  (Person 1's public API)
  - pysat       (install via: pip install python-sat)

Usage
-----
    from fm_core import load_feature_model
    from sat_solver import SATValidator

    parser, translator = load_feature_model("feature_model.xml")
    validator = SATValidator(parser, translator)

    # T2 – Verify a selection
    result = validator.verify(["Application", "Catalog", "Filtered", "ByLocation",
                                "Payment", "CreditCard"])
    print(result)

    # T3 – Get the Minimum Working Product
    mwp = validator.get_mwp()
    print(mwp)

    # T4 – Check constraints only (fast, no SAT call)
    violations = validator.check_constraints(["Application", "Catalog", "Filtered",
                                               "ByLocation", "Payment", "CreditCard"])
    print(violations)
"""

import re
import sys
import os

# ── Make sure fm_core is importable when sat_solver.py sits in the same folder ──
sys.path.insert(0, os.path.dirname(__file__))

from fm_core import (
    FeatureModelParser,
    LogicTranslator,
    get_mandatory_features,
    get_xor_groups,
    get_or_groups,
)

try:
    from pysat.solvers import Glucose3
    from pysat.formula import CNF
    _PYSAT_AVAILABLE = True
except ImportError:                          # graceful fallback for environments without pysat
    _PYSAT_AVAILABLE = False


# ===========================================================================
# T1 – CNF Encoder
# ===========================================================================

class CNFEncoder:
    """
    Encodes the propositional logic formulas produced by Person 1's
    LogicTranslator into DIMACS-style CNF clauses understood by PySAT.

    Variable mapping: each feature name → a unique positive integer.
    Negation is represented by the negative of that integer.

    Supported formula shapes (matching what LogicTranslator produces):
        R0  :  A                           (unit clause [A])
        R1/R2: A → B                       ([-A, B])
        R3/R4: A → (B ∨ C ∨ …)            ([-A, B, C, …])
        R3b  : ¬A ∨ ¬B                     ([-A, -B])
        R5   : A → B                       ([-A, B])
        R6   : ¬A ∨ ¬B                     ([-A, -B])
    """

    def __init__(self, parser: FeatureModelParser, translator: LogicTranslator):
        self.parser = parser
        self.translator = translator

        # Build feature → integer mapping (1-indexed, PySAT requirement)
        self._features = list(parser.features.keys())
        self._var: dict[str, int] = {
            name: idx + 1 for idx, name in enumerate(self._features)
        }
        self._var_inv: dict[int, str] = {v: k for k, v in self._var.items()}

        self.clauses: list[list[int]] = []   # CNF clauses
        self._encode_all()

    # -----------------------------------------------------------------------
    # Public helpers
    # -----------------------------------------------------------------------

    def var(self, name: str) -> int:
        """Return the positive integer variable for a feature name."""
        return self._var[name]

    def feature_of(self, var_id: int) -> str:
        """Return the feature name for a variable id (handles negatives)."""
        return self._var_inv[abs(var_id)]

    def num_vars(self) -> int:
        return len(self._features)

    def assumption_true(self, name: str) -> int:
        """Assumption literal: feature IS selected."""
        return self._var[name]

    def assumption_false(self, name: str) -> int:
        """Assumption literal: feature is NOT selected."""
        return -self._var[name]

    # -----------------------------------------------------------------------
    # Encoding
    # -----------------------------------------------------------------------

    def _encode_all(self):
        """Encode every formula from translator.formulas into CNF clauses."""
        for entry in self.translator.formulas:
            formula = entry["formula"]
            clause = self._formula_to_clause(formula)
            if clause is not None:
                self.clauses.append(clause)

    def _formula_to_clause(self, formula: str) -> list[int] | None:
        """
        Convert a single propositional formula string to a CNF clause.

        Shapes handled:
          1.  "A"             →  [var(A)]
          2.  "A → B"         →  [-var(A), var(B)]
          3.  "A → (B ∨ C)"   →  [-var(A), var(B), var(C)]
          4.  "¬A ∨ ¬B"       →  [-var(A), -var(B)]
        """
        formula = formula.strip()

        # ── Shape 4: ¬A ∨ ¬B  (pairwise XOR / excludes) ──────────────────
        if "∨" in formula and "→" not in formula:
            parts = [p.strip() for p in formula.split("∨")]
            clause = []
            for p in parts:
                lit = self._literal(p)
                if lit is None:
                    return None
                clause.append(lit)
            return clause

        # ── Shape 2 / 3: A → … ─────────────────────────────────────────────
        if "→" in formula:
            lhs, rhs = formula.split("→", 1)
            lhs = lhs.strip()
            rhs = rhs.strip().strip("()")

            ant = self._literal(lhs)
            if ant is None:
                return None
            neg_ant = -ant if ant > 0 else abs(ant)   # negate antecedent

            # RHS may be a single literal or a disjunction
            consequents = [r.strip() for r in rhs.split("∨")]
            clause = [neg_ant]
            for c in consequents:
                lit = self._literal(c)
                if lit is None:
                    return None
                clause.append(lit)
            return clause

        # ── Shape 1: bare feature name (unit clause) ──────────────────────
        lit = self._literal(formula)
        if lit is not None:
            return [lit]

        return None   # unrecognised shape – skip

    def _literal(self, token: str) -> int | None:
        """
        Parse a token like 'ByLocation' or '¬ByLocation' into a signed integer.
        Returns None if the feature name is not found.
        """
        token = token.strip()
        negated = token.startswith("¬")
        name = token.lstrip("¬").strip()
        if name not in self._var:
            return None
        v = self._var[name]
        return -v if negated else v


# ===========================================================================
# T1 / T2 / T3 / T4 – SATValidator (main public class)
# ===========================================================================

class SATValidator:
    """
    Public class for Person 3 (UI) to import and use.

    Exposes four methods corresponding to the four Person 2 tasks:
      T1: CNF encoding (done internally in __init__)
      T2: verify(selected_features)
      T3: get_mwp()
      T4: check_constraints(selected_features)

    Parameters
    ----------
    parser     : FeatureModelParser  (from Person 1)
    translator : LogicTranslator     (from Person 1)
    """

    def __init__(self, parser: FeatureModelParser, translator: LogicTranslator):
        self.parser = parser
        self.translator = translator

        # T1 – Build the CNF encoder (encodes all formulas into SAT clauses)
        self.encoder = CNFEncoder(parser, translator)

        if not _PYSAT_AVAILABLE:
            print(
                "[WARNING] python-sat is not installed.\n"
                "          Run:  pip install python-sat\n"
                "          SAT-based methods will raise RuntimeError until installed."
            )

    # -----------------------------------------------------------------------
    # T2 – Feature Selection Verification
    # -----------------------------------------------------------------------

    def verify(self, selected: list[str]) -> dict:
        """
        T2 – Verify whether a set of selected features forms a valid configuration.

        Steps:
          1. Fast constraint check (T4) – detect obvious violations immediately
          2. SAT check – encode selection as unit assumptions and query solver

        Parameters
        ----------
        selected : list[str]
            Feature names the user has chosen.

        Returns
        -------
        dict with keys:
            "valid"      : bool
            "reason"     : str  (human-readable explanation)
            "violations" : list[str]  (list of violated constraint descriptions)
        """
        # ── Step 1: fast cross-tree constraint pre-check (T4) ──────────────
        violations = self.check_constraints(selected)
        if violations:
            return {
                "valid": False,
                "reason": "Cross-tree constraint violation(s) detected.",
                "violations": violations,
            }

        # ── Step 2: SAT-based full model check ─────────────────────────────
        if not _PYSAT_AVAILABLE:
            raise RuntimeError("python-sat is not installed. Run: pip install python-sat")

        selected_set = set(selected)
        unknown = selected_set - set(self.parser.features.keys())
        if unknown:
            return {
                "valid": False,
                "reason": f"Unknown feature(s): {sorted(unknown)}",
                "violations": [f"Feature '{f}' does not exist in the model." for f in unknown],
            }

        # Build assumption literals:
        #   selected features → forced TRUE
        #   all other features → forced FALSE (we check this exact selection)
        assumptions = []
        for name in self.parser.features:
            if name in selected_set:
                assumptions.append(self.encoder.assumption_true(name))
            else:
                assumptions.append(self.encoder.assumption_false(name))

        satisfiable = self._solve(assumptions)

        if satisfiable:
            return {
                "valid": True,
                "reason": "The selected configuration satisfies all feature model constraints.",
                "violations": [],
            }
        else:
            # Try to give a more helpful message by checking model-level rules
            reason = self._diagnose(selected_set)
            return {
                "valid": False,
                "reason": reason,
                "violations": [reason],
            }

    # -----------------------------------------------------------------------
    # T3 – Minimum Working Product (MWP)
    # -----------------------------------------------------------------------

    def get_mwp(self) -> dict:
        """
        T3 – Compute the Minimum Working Product.

        Strategy:
          1. Force all mandatory features to TRUE.
          2. For XOR groups: pick the first member only (minimum choice).
          3. For OR groups: pick the first member only (minimum choice).
          4. Force all optional features that are NOT in the above to FALSE.
          5. Verify via SAT; if satisfiable, return that configuration.

        Returns
        -------
        dict with keys:
            "features" : list[str]  – features in the MWP
            "valid"    : bool
            "note"     : str
        """
        if not _PYSAT_AVAILABLE:
            raise RuntimeError("python-sat is not installed. Run: pip install python-sat")

        mwp_selected: set[str] = set()

        # ── Step 1: include all mandatory features ─────────────────────────
        for name in get_mandatory_features(self.parser):
            mwp_selected.add(name)

        # ── Step 2: for each XOR group where parent is selected, pick first member ──
        for parent, members in get_xor_groups(self.parser):
            if parent in mwp_selected:
                mwp_selected.add(members[0])   # pick first → minimum

        # ── Step 3: for each OR group where parent is selected, pick first member ───
        for parent, members in get_or_groups(self.parser):
            if parent in mwp_selected:
                mwp_selected.add(members[0])   # pick first → minimum

        # ── Step 4: verify via SAT ─────────────────────────────────────────
        assumptions = []
        for name in self.parser.features:
            if name in mwp_selected:
                assumptions.append(self.encoder.assumption_true(name))
            else:
                assumptions.append(self.encoder.assumption_false(name))

        satisfiable = self._solve(assumptions)

        if satisfiable:
            return {
                "features": sorted(mwp_selected),
                "valid": True,
                "note": (
                    "Minimum Working Product: all mandatory features selected; "
                    "one member chosen per XOR/OR group; all optional features excluded."
                ),
            }
        else:
            # Fallback: let SAT solver find any satisfying assignment on its own
            solver = Glucose3()
            for clause in self.encoder.clauses:
                solver.add_clause(clause)
            sat = solver.solve()
            if sat:
                model = solver.get_model()
                solver.delete()
                selected = [self.encoder.feature_of(v) for v in model if v > 0]
                return {
                    "features": sorted(selected),
                    "valid": True,
                    "note": "MWP computed by SAT solver (heuristic selection).",
                }
            solver.delete()
            return {
                "features": [],
                "valid": False,
                "note": "ERROR: The feature model itself is unsatisfiable. Check the XML.",
            }

    # -----------------------------------------------------------------------
    # T4 – Cross-Tree Constraint Checking
    # -----------------------------------------------------------------------

    def check_constraints(self, selected: list[str]) -> list[str]:
        """
        T4 – Check cross-tree constraints (requires / excludes) against a selection.

        Does NOT call the SAT solver — purely logical checks based on the
        propositional formulas in translator.formulas (R5/R6 rules).

        Parameters
        ----------
        selected : list[str]
            Feature names the user has chosen.

        Returns
        -------
        list[str]
            Descriptions of every violated constraint (empty list = all OK).
        """
        selected_set = set(selected)
        violations: list[str] = []

        for entry in self.translator.formulas:
            if entry["rule"] != "R5/R6":
                continue

            formula = entry["formula"].strip()

            # ── Pattern: A → B  (requires) ────────────────────────────────
            if "→" in formula and "¬" not in formula.split("→")[0]:
                parts = formula.split("→")
                lhs = parts[0].strip().lstrip("¬").strip()
                rhs = parts[1].strip().lstrip("¬").strip()
                negated_rhs = "¬" in parts[1]

                if lhs in selected_set:
                    if not negated_rhs and rhs not in selected_set:
                        violations.append(
                            f"Constraint violated: '{lhs}' is selected but '{rhs}' is not "
                            f"(requires: {formula})"
                        )
                    elif negated_rhs and rhs in selected_set:
                        violations.append(
                            f"Constraint violated: '{lhs}' is selected but '{rhs}' must be excluded "
                            f"(excludes: {formula})"
                        )

            # ── Pattern: ¬A ∨ ¬B  (excludes) ─────────────────────────────
            elif "∨" in formula and "→" not in formula:
                parts = [p.strip() for p in formula.split("∨")]
                feat_names = [p.lstrip("¬").strip() for p in parts]
                negated = [p.startswith("¬") for p in parts]

                # ¬A ∨ ¬B means A and B cannot both be selected
                if all(n for n in negated):
                    if all(f in selected_set for f in feat_names):
                        violations.append(
                            f"Constraint violated: '{feat_names[0]}' and '{feat_names[1]}' "
                            f"cannot both be selected (excludes: {formula})"
                        )

        return violations

    # -----------------------------------------------------------------------
    # Extra helper for Person 3 (UI)
    # -----------------------------------------------------------------------

    def get_required_additions(self, selected: list[str]) -> list[str]:
        """
        Given the currently selected features, return which extra features
        must be added to avoid cross-tree 'requires' violations.

        Useful for Person 3's UI to auto-suggest missing features.

        Returns
        -------
        list[str] – feature names that should be auto-added.
        """
        selected_set = set(selected)
        additions: list[str] = []

        for entry in self.translator.formulas:
            if entry["rule"] != "R5/R6":
                continue
            formula = entry["formula"].strip()
            if "→" in formula and "¬" not in formula.split("→")[0]:
                lhs, rhs = formula.split("→", 1)
                lhs = lhs.strip()
                rhs = rhs.strip()
                if not rhs.startswith("¬") and lhs in selected_set and rhs not in selected_set:
                    additions.append(rhs)

        return list(set(additions))

    def all_features(self) -> list[str]:
        """Return all feature names in the model (useful for UI checkbox population)."""
        return list(self.parser.features.keys())

    def mandatory_features(self) -> list[str]:
        """Return features that must always be selected."""
        return get_mandatory_features(self.parser)

    # -----------------------------------------------------------------------
    # Internal SAT helper
    # -----------------------------------------------------------------------

    def _solve(self, assumptions: list[int]) -> bool:
        """Run Glucose3 SAT solver with the base clauses + given assumptions."""
        solver = Glucose3()
        for clause in self.encoder.clauses:
            solver.add_clause(clause)
        result = solver.solve(assumptions=assumptions)
        solver.delete()
        return result

    def _diagnose(self, selected_set: set[str]) -> str:
        """
        Produce a human-readable diagnosis when a selection is SAT-unsatisfiable
        (cross-tree checks already passed, so it's a structural model violation).
        """
        # Check mandatory features missing
        missing_mandatory = [
            f for f in get_mandatory_features(self.parser)
            if f not in selected_set
        ]
        if missing_mandatory:
            return (
                f"Missing mandatory feature(s): {missing_mandatory}. "
                "These must always be included."
            )

        # Check XOR groups
        for parent, members in get_xor_groups(self.parser):
            if parent in selected_set:
                chosen = [m for m in members if m in selected_set]
                if len(chosen) == 0:
                    return (
                        f"XOR group under '{parent}': at least one of "
                        f"{members} must be selected."
                    )
                if len(chosen) > 1:
                    return (
                        f"XOR group under '{parent}': exactly one of "
                        f"{members} must be selected, but you chose {chosen}."
                    )

        # Check OR groups
        for parent, members in get_or_groups(self.parser):
            if parent in selected_set:
                chosen = [m for m in members if m in selected_set]
                if len(chosen) == 0:
                    return (
                        f"OR group under '{parent}': at least one of "
                        f"{members} must be selected."
                    )

        return "The selection violates one or more feature model constraints (SAT unsatisfiable)."


# ===========================================================================
# Quick self-test / demo  (run:  python sat_solver.py)
# ===========================================================================

if __name__ == "__main__":
    from fm_core import load_feature_model

    xml_path = os.path.join(os.path.dirname(__file__), "feature_model.xml")
    print(f"\nLoading model: {xml_path}\n{'='*60}")
    parser, translator = load_feature_model(xml_path)

    validator = SATValidator(parser, translator)

    print("\n[T1] CNF Encoding")
    print("-" * 40)
    print(f"  Features    : {validator.all_features()}")
    print(f"  Total vars  : {validator.encoder.num_vars()}")
    print(f"  CNF clauses : {len(validator.encoder.clauses)}")
    for i, clause in enumerate(validator.encoder.clauses, 1):
        readable = [
            ("¬" + validator.encoder.feature_of(lit) if lit < 0 else validator.encoder.feature_of(lit))
            for lit in clause
        ]
        print(f"  Clause {i:>2}: {readable}")

    print("\n[T3] Minimum Working Product")
    print("-" * 40)
    mwp = validator.get_mwp()
    print(f"  Valid   : {mwp['valid']}")
    print(f"  Features: {mwp['features']}")
    print(f"  Note    : {mwp['note']}")

    print("\n[T2] Verify valid selection (MWP itself)")
    print("-" * 40)
    result = validator.verify(mwp["features"])
    print(f"  Valid      : {result['valid']}")
    print(f"  Reason     : {result['reason']}")

    print("\n[T2] Verify INVALID selection (ByLocation without Location)")
    print("-" * 40)
    bad = ["Application", "Catalog", "Filtered", "ByLocation", "Payment", "CreditCard"]
    result2 = validator.verify(bad)
    print(f"  Valid      : {result2['valid']}")
    print(f"  Reason     : {result2['reason']}")
    print(f"  Violations : {result2['violations']}")

    print("\n[T4] Constraint-only check on bad selection")
    print("-" * 40)
    violations = validator.check_constraints(bad)
    for v in violations:
        print(f"  ⚠ {v}")
    if not violations:
        print("  No cross-tree violations (structural SAT check would still run).")

    print("\n[T4] get_required_additions for bad selection")
    print("-" * 40)
    additions = validator.get_required_additions(bad)
    print(f"  Must also add: {additions}")

    print("\n[Done] sat_solver.py self-test complete.\n")
