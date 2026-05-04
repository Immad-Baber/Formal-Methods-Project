"""
main_p1.py
==========
Driver script for Person 1 deliverables:
  - XML Parsing
  - Feature Hierarchy Extraction
  - Propositional Logic Translation
  - Translation Rules Documentation
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from xml_parser import FeatureModelParser, LogicTranslator


def main(xml_path: str = "feature_model.xml"):
    print("\n" + "=" * 60)
    print("FEATURE MODEL ANALYSIS TOOL  —  Person 1: XML + Logic Core")
    print("=" * 60)

    # ----------------------------------------------------------------
    # Step 1: Parse XML
    # ----------------------------------------------------------------
    print(f"\n[1] Parsing XML: {xml_path}")
    try:
        parser = FeatureModelParser(xml_path, is_file=True)
        parser.parse()
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    print(f"  Root feature  : {parser.root_name}")
    print(f"  Total features: {len(parser.features)}")
    print(f"  Constraints   : {len(parser.constraints)}")

    # ----------------------------------------------------------------
    # Step 2: Print Feature Hierarchy
    # ----------------------------------------------------------------
    print("\n[2] Feature Hierarchy")
    print("-" * 40)
    parser.print_hierarchy()

    # ----------------------------------------------------------------
    # Step 3: Show extracted feature metadata
    # ----------------------------------------------------------------
    print("\n[3] Feature Details")
    print("-" * 40)
    header = f"{'Name':<16} {'Mandatory':<12} {'Parent':<16} {'Group Type':<12} {'Group Children'}"
    print(header)
    print("-" * len(header))
    for name, feat in parser.features.items():
        gc = ", ".join(feat.group_children) if feat.group_children else "-"
        print(f"{name:<16} {str(feat.mandatory):<12} {str(feat.parent):<16} {str(feat.group_type):<12} {gc}")

    # ----------------------------------------------------------------
    # Step 4: Show raw constraints
    # ----------------------------------------------------------------
    print("\n[4] Cross-Tree Constraints (raw)")
    print("-" * 40)
    for i, c in enumerate(parser.constraints, 1):
        print(f"  Constraint {i}:")
        if c.english:
            print(f"    English : {c.english}")
        if c.boolean_expr:
            print(f"    Boolean : {c.boolean_expr}")

    # ----------------------------------------------------------------
    # Step 5: Translate to Propositional Logic
    # ----------------------------------------------------------------
    print("\n[5] Propositional Logic Translation")
    translator = LogicTranslator(parser)
    translator.translate()
    print(translator.get_all_formulas())

    # ----------------------------------------------------------------
    # Step 6: Combined formula
    # ----------------------------------------------------------------
    print("\n[6] Combined Propositional Formula (all clauses AND-joined)")
    print("-" * 40)
    print(translator.get_combined_formula())

    # ----------------------------------------------------------------
    # Step 7: Cross-tree constraint translations
    # ----------------------------------------------------------------
    print("\n[7] Cross-Tree Constraint Translations")
    print("-" * 40)
    for i, c in enumerate(parser.constraints, 1):
        print(f"  Constraint {i}:")
        if c.english:
            print(f"    English      : {c.english}")
        print(f"    Propositional: {c.propositional}")

    print("\n[Done] Person 1 module executed successfully.\n")

    # Return objects for use by other team members
    return parser, translator


if __name__ == "__main__":
    xml_file = sys.argv[1] if len(sys.argv) > 1 else "feature_model.xml"
    main(xml_file)
