"""Contract version. Bump on any change to enums.py or models.py.

Semantics:
  MAJOR -- a breaking change (field removed, renamed, or type narrowed)
  MINOR -- an additive change (new optional field, new enum member)
  PATCH -- documentation or validation-only change

Every API response carries this so a mismatched web build fails loudly instead
of silently rendering the wrong thing.
"""

CONTRACT_VERSION = "1.0.0"
