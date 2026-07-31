# Insert Python's Lists, Sets and Dictionaries to the fundamental types

In current implementation just numerical types are present as "bare" Python type.
It is important to add at least:
- List type
- Set type
- Dictionary type
These types should be added together with some methods acting on them allowing the user to add some element to them and also some method to extract elements.

We will have some phases:
- Discussion: to decide together the design of the whole stuff.
- Other Requirements: to keep into account. Check that no conflict arises.
- Plan: once everything is cleare we will write a plan. Every decision must be taken together.

## Discussion 

- Which method insert for each type?
- Where to insert these types/classes
- How to concile with annotation? is `Any` suitable for this case?

## Other Requirements

- We must have some test of json file using such nodes

## Plan
- Write a plan in Step and Substep (checkable `- [ ]`). Later we will implement

## Recommendations

- Be *brief* and *concise* when we discuss.
- Be *spot on*: when you have to tell me something, write a *clear* and *unambiguous* and direct sentence to the point. Comments and other dicussion after. But the "thesis" must be cleare immediately.
- Every decision must be made together. I have the responsibility for the design of the software.
- When you ask me to execute command comment with one liner what you are asking me unless obvious.
- *Do not do things I did not ask you to do*. You are welcome to give me caveat or suggestion but I must be the spiritus movens, not you.
- When multiple chioces/decision are to be taken, please one by one: you write the first, i decide (or we discuss), then the second. Do not bomb me with tons of question all together, it is pointless.
- When you ask something about the code do no take for granted I know every details of already-written code, I'm just refactoring it. Do not spend many words about introduction, but keep ready to answer question of mine about it.
