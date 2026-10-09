# More ergonomic function registration

## Context
* Function and classes are presented via `get_function` and `get_classes` method of the base class `Plugin`.
* We create a `output` decorator to name the result of functions and method.

## Proposal (to think about)
It would be more ergonomic to have instead a registration mechanism with some parametrized decorators like `register_class` `register_function` (and maybe `register_method`) taking as parameter for instance the `output` name (and perhaps also the optional registration name overriding the standard one, and also the variable registration name hiding the standard one). (here by "registration name" i mean the name that ends up in the registry.)

## Design changes (to decide)
* In the current situation, every plugin has to subclass `Plugin` abstract base class and override `get_functions` and `get_classes` method.Here probably one should instatiate a plugin and use decorator. Are there alternatives? To discuss and find the most ergonomic in terms of user. User experience should be provided (code samples)
* Can it be that every method is registered by default, but we need to input nonetheless the output name. So probably it is better and more symmetrical to have each method registered.
* If we already have a class with some method or we have some function, can we avoid to create wrapper and simply use decorator befor as normal function registering other functions, classes and method?

## TODO
In order:
1. Think about. Please be pracmatic showing the effect of each decision in the code one has to write.
2. Record decision in a file `decisions.md`. It should contain al the contex necessary for the implementation plan.
3. Based on the decision write the implementaion plan. It must be divided in checkable (`- [ ]`) setp and substep. Approximately each step shoul have tests and they sould pass. There might be exceptions to this rule, tell me about.
4. Implement the plan. Step by step. After each step pause so that I check.
