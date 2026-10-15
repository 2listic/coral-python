# Audit

In the present session we have to investigate about issue #44. It partially overlap also with issue #34

The main subject is: *type annotations*; the function to be investigated upon is in `src/coral_app/registry.py` function `python_type_to_string`.

## Questions
1. Has this function to do with formation of registry json files?
2. It seems that non-primitive (`PRIMITIVE_MAP` and `COLLECTION_TYPES`) types, that is *all* the types coming from plugins are marked with `Any`. Is it true?
3. What happen to classes registered in plugins? How are they referred to in json registry files?

## Reccommendations
1. Be very brief and coincise.
2. Try to make clear statements not taking all the context for granted.
