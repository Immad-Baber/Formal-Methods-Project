# Propositional Logic Translation Rules
## Feature Model Analysis Tool — Person 1 Documentation

---

## Overview

A **Feature Model** is a hierarchical tree of features with relationships and constraints.
This document describes exactly how each relationship type is translated into
**Propositional Logic** formulas by the tool.

---

## Feature Relationship Types

| Relationship | XML Representation | Description |
|---|---|---|
| Mandatory child | `mandatory="true"` | Child must be selected whenever parent is |
| Optional child | `mandatory="false"` or absent | Child may or may not be selected |
| XOR group | `<group type="xor">` | Exactly one child in the group must be selected |
| OR group | `<group type="or">` | One or more children must be selected |
| Cross-tree (requires) | `<englishStatement>` or `<booleanExpression>` | Feature A implies Feature B |
| Cross-tree (excludes) | `<englishStatement>` or `<booleanExpression>` | Feature A and B cannot coexist |

---

## Translation Rules

### R0 — Root Feature

The root feature is always present in every valid product configuration.

```
root
```

**Example:** `Application`

---

### R1 — Mandatory Child

If feature **B** is a mandatory child of feature **A**:
- Selecting **A** forces **B** (parent implies child)
- Selecting **B** forces **A** (child implies parent)

```
A -> B
B -> A
```

**Example:**
- `Application -> Catalog`  *(Catalog is mandatory under Application)*
- `Catalog -> Application`

---

### R2 — Optional Child

If feature **B** is an optional child of feature **A**:
- **B** can only exist if **A** is selected
- But **A** can exist without **B**

```
B -> A
```

**Example:**
- `Notification -> Application`  *(Notification is optional; if chosen, Application must be present)*

---

### R3 — XOR Group (Exactly One)

For an XOR group `{A, B, C}` under parent **P**:

1. **At least one** must be selected when P is selected:
```
P -> (A ∨ B ∨ C)
```

2. **At most one** can be selected (pairwise exclusion):
```
¬A ∨ ¬B
¬A ∨ ¬C
¬B ∨ ¬C
```

3. Each member implies the parent:
```
A -> P
B -> P
C -> P
```

**Example (Filtered -> {ByDiscount, ByWeather, ByLocation}):**
```
Filtered -> (ByDiscount ∨ ByWeather ∨ ByLocation)
¬ByDiscount ∨ ¬ByWeather
¬ByDiscount ∨ ¬ByLocation
¬ByWeather ∨ ¬ByLocation
ByDiscount -> Filtered
ByWeather -> Filtered
ByLocation -> Filtered
```

---

### R4 — OR Group (At Least One)

For an OR group `{A, B}` under parent **P**:

1. **At least one** must be selected when P is selected:
```
P -> (A ∨ B)
```

2. Each member implies the parent:
```
A -> P
B -> P
```

**Example (Payment -> {CreditCard, Discount}):**
```
Payment -> (CreditCard ∨ Discount)
CreditCard -> Payment
Discount -> Payment
```

---

### R5 — Cross-Tree Requires Constraint

"Feature **A** requires Feature **B**" means A cannot be selected without B.

```
A -> B
```

**Example:**
- English: *"The Location feature is required to filter the catalog by location."*
- Propositional: `ByLocation -> Location`

---

### R6 — Cross-Tree Excludes Constraint

"Feature **A** excludes Feature **B**" means A and B cannot both be selected.

```
¬A ∨ ¬B   (equivalent to: A -> ¬B)
```

---

## Full Formula for Sample Feature Model

The complete conjunction (AND of all clauses) for the provided XML:

```
Application                                      -- R0: root
∧ Application -> Catalog                          -- R1: Catalog is mandatory
∧ Catalog -> Application                          -- R1
∧ Catalog -> Filtered                             -- R1: Filtered is mandatory
∧ Filtered -> Catalog                             -- R1
∧ Notification -> Application                     -- R2: Notification is optional
∧ Location -> Application                         -- R2: Location is optional
∧ Application -> Payment                          -- R1: Payment is mandatory
∧ Payment -> Application                          -- R1
∧ Filtered -> (ByDiscount ∨ ByWeather ∨ ByLocation)  -- R3: XOR at-least-one
∧ ¬ByDiscount ∨ ¬ByWeather                      -- R3: XOR pairwise
∧ ¬ByDiscount ∨ ¬ByLocation                     -- R3: XOR pairwise
∧ ¬ByWeather ∨ ¬ByLocation                      -- R3: XOR pairwise
∧ ByDiscount -> Filtered                          -- R3: member implies parent
∧ ByWeather -> Filtered                           -- R3
∧ ByLocation -> Filtered                          -- R3
∧ Notification -> (SMS ∨ Call)                    -- R3: XOR at-least-one
∧ ¬SMS ∨ ¬Call                                   -- R3: XOR pairwise
∧ SMS -> Notification                             -- R3
∧ Call -> Notification                            -- R3
∧ Location -> (WiFi ∨ GPS)                        -- R4: OR at-least-one
∧ WiFi -> Location                                -- R4: member implies parent
∧ GPS -> Location                                 -- R4
∧ Payment -> (CreditCard ∨ Discount)              -- R4: OR at-least-one
∧ CreditCard -> Payment                           -- R4
∧ Discount -> Payment                             -- R4
∧ ByLocation -> Location                          -- R5: cross-tree requires
```

---

## English to Propositional Logic Translation

The tool supports automatic translation of English cross-tree constraints using pattern matching:

| English Pattern | Propositional Formula |
|---|---|
| `X requires Y` | `X -> Y` |
| `X excludes Y` | `¬X ∨ ¬Y` |
| `X is required to [do Y]` | `Y -> X` |
| `if X then Y` | `X -> Y` |
| Boolean expression `X implies Y` | `X -> Y` |

If no pattern is matched, the tool prompts the user to manually enter the propositional form.

---

## How to Use in Code

```python
from fm_core import load_feature_model

parser, translator = load_feature_model("feature_model.xml")

# Get all propositional formulas
print(translator.get_all_formulas())

# Get helper data for Person 2 (SAT Solver)
from fm_core import get_mandatory_features, get_xor_groups, get_or_groups
mandatory = get_mandatory_features(parser)
xor_groups = get_xor_groups(parser)
or_groups  = get_or_groups(parser)
```
