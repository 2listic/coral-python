
# Multi level inheritance
as in dealII-X coral-editor project issue #63.


## Current situation
Not supported

## Desiderata
1. If a class A derives from n base classes B_1, ..., B_n it should be possible to register all of them as base classes.
2. When validation and/or run of the network is done Liksov principle must be respected: if A derives from B_1, ..., B_n, then a function requiring a reference to B_i can be fed with A.
3. Also chain of inheritance must be supported: if A derives from B and C, it should be possible to enforce Licksov principle again.
4. Arbitrary combination of multi parent and chain should be handled.
5. _a finer point_: if we register a class A deriving from B and a class B deriving from C, it would be nice that the program itself recognize that A is deriving from C even if not explicitly set by the user, if this is possible.

## What I'm asking
I want the following phases:
1. Discussion (no code has to be written).
2. After alla decisions have been taken, write a plane in a separate file in this folder. It will contain tests.
3. Plan will be implemented
4. We will make a small audit about consistency of what we have just done

## Note for discussion
1. Be crystal clear and very very brief.
2. Text should not be long. Examples of the user experience are important. "Ok, whit this modification you are proposing, the user using coral what is meant to write as code?"
3. Do no be prolix.
4. Please do not do what you are not asked for. If you see a danger suggest me but remember I'm the siritus movens.
