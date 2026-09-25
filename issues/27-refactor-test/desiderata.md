# Audit and refactor of test suite

This issue will be aimed to understand what we did so far for testing and to understand if certain change are possible.
In this document there will be certain question and certain proposal. The aim is to answer these question and validate the proposal.
After that the output of the session will be a plan for a possible refactor of the test suite.

## Audit on questions
- Clarify in `tests` the difference between subfolder `fixtures` and `golden`. What is the functional distinction
- in `test_acceptance` there is the use of `uv`. This suggests that these tests cannot be run by final user who will use pip. Is this acceptable? Is this limited just to these tests?

## Audit on test refactor proposal (*ultra deep think*)
Now all the tests are in the `tests` folder. I would like to have some central test suite about core app functionalities and that every plugin would be able to carry its own tests.
When a plugin is "registered" also its test should be.
Is it clever to have a suitable decorator with which to decorate tests belonging to plugins?
This would trigger a complete refactor of tests making everything more natural.

## Refactor
On top of previous decisions discuss the opportunity to implement what is described in `issues/25-*/TODO.md`.

## Beware
- Decision must be taken together.
- Do not do what I do not ask. If you want you can suggest me.
- Do no take for granted I know every line of code since we are refactoring a pre-existing code. So if needed make a very very brief comment of what the part of code under investigation is supposed to to.
