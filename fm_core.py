"""
fm_core.py
==========
Public API for Person 1 deliverables.
Import this file in other modules (Person 2 SAT, Person 3 UI).

Usage
-----
    from fm_core import load_feature_model, FeatureModelParser, LogicTranslator

    parser, translator = load_feature_model("feature_model.xml")

    # All features dict
    parser.features          # dict[str, Feature]
    parser.root_name         # str
    parser.constraints       # list[Constraint]

    # All propositional logic formulas
    translator.formulas      # list[{"rule", "formula", "note"}]
    translator.get_all_formulas()     # human-readable string
    translator.get_combined_formula() # single AND-joined formula string
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from xml_parser import FeatureModelParser, LogicTranslator, Feature, Constraint


def load_feature_model(xml_path: str) -> tuple:
    """
    Parse an XML feature model file and translate it to propositional logic.

    Parameters
    ----------
    xml_path : str
        Path to the XML feature model file.

    Returns
    -------
    tuple[FeatureModelParser, LogicTranslator]
        parser    – use to access features, hierarchy, constraints
        translator – use to access propositional logic formulas
    """
    parser = FeatureModelParser(xml_path, is_file=True)
    parser.parse()

    translator = LogicTranslator(parser)
    translator.translate()

    return parser, translator


def load_feature_model_from_string(xml_string: str) -> tuple:
    """
    Same as load_feature_model but accepts raw XML string.
    Useful for testing or UI where XML is typed in a text box.
    """
    parser = FeatureModelParser(xml_string, is_file=False)
    parser.parse()

    translator = LogicTranslator(parser)
    translator.translate()

    return parser, translator


# ---------------------------------------------------------------------------
# Helper utilities for Person 2 (SAT Solver integration)
# ---------------------------------------------------------------------------

def get_feature_names(parser: FeatureModelParser) -> list[str]:
    """Return all feature names as a list (useful for variable mapping in SAT)."""
    return list(parser.features.keys())


def get_mandatory_features(parser: FeatureModelParser) -> list[str]:
    """Return features that MUST be in every valid configuration."""
    mandatory = []
    for name, feat in parser.features.items():
        # Root is mandatory; direct mandatory children of any parent are mandatory
        if feat.parent is None or (feat.mandatory and feat.parent is not None
                                   and name in parser.features[feat.parent].children):
            mandatory.append(name)
    return mandatory


def get_xor_groups(parser: FeatureModelParser) -> list[tuple[str, list[str]]]:
    """Return list of (parent_name, [members]) for every XOR group."""
    return [(name, feat.group_children)
            for name, feat in parser.features.items()
            if feat.group_type == "xor" and feat.group_children]


def get_or_groups(parser: FeatureModelParser) -> list[tuple[str, list[str]]]:
    """Return list of (parent_name, [members]) for every OR group."""
    return [(name, feat.group_children)
            for name, feat in parser.features.items()
            if feat.group_type == "or" and feat.group_children]


def get_cross_tree_propositional(parser: FeatureModelParser,
                                  translator: LogicTranslator) -> list[str]:
    """Return only cross-tree constraint formulas (R5/R6 rules)."""
    return [e["formula"] for e in translator.formulas if e["rule"] == "R5/R6"]


# ---------------------------------------------------------------------------
# Re-export data classes so other modules only need to import fm_core
# ---------------------------------------------------------------------------

__all__ = [
    "load_feature_model",
    "load_feature_model_from_string",
    "get_feature_names",
    "get_mandatory_features",
    "get_xor_groups",
    "get_or_groups",
    "get_cross_tree_propositional",
    "FeatureModelParser",
    "LogicTranslator",
    "Feature",
    "Constraint",
]
