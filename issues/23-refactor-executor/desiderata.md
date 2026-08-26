# Desiderata

Here we would like to refactor the executor (`coral-app/src/coral_app/executor.py`) and related files.

## Goal

- To think if replacement current implementation of Kahn's algoritm with `graphlib.TopologicalSorter`.
- To veryfy (looking around the python files) if the slot validation is done somewhere and not repeated. 
- To think if a calss to express the graph itself could fint our aim enforcing separation of concern.

## Previous Analysis

Look at `issues/23-*/executor-ordering-analysis`

## Roadmap

- We will discuss together about any design ascpet.
- After every detail is clear you will write a `plan.md` divided into checkable (`- [ ]`) step and and substep. In another session this plan will be implemented.

## Important

- Be *coincise* both in document and in answers. Sentence must be clear, not ambiguous and when one reads them one must immediately understand the point. Details after.
- Do not even ask to commit. I will do.
- If there are several things to decide, one by one, not all together.
