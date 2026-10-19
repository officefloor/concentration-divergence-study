# Sinew — data coupled to the control flow

> **Status (20 October 2026).** This document states the construct as it now stands. It is
> about **identifying** concentrated complexity at a single checkout and **classifying** it as
> good or bad. How concentration comes about over a project's history, and whether coupling
> shows it early, is left to later work. Everything under *Exploratory observations* was seen
> before any hypothesis here was written down; the hypotheses are registered in
> [`PLAN.md`](PLAN.md), not here.

## The claim in one paragraph

A **sinew** is data coupled to the control flow: data that reaches the code that needs it only
by being passed down the call chain, method to method. The more data rides on the control flow,
the stronger the sinew. Strong sinews make code hard to refactor: every method on the path
carries the data in its signature, so changing the data, inserting a step or reordering steps
means editing the whole path. Dependency injection weakens sinews by taking objects off the
control flow and making them available by declaration. OfficeFloor's function injection removes
them from the flow altogether: procedures receive their data as injected values (`@Val`,
`Out<>`) rather than as arguments threaded through callers. The question here is whether sinews
tell good concentrations of complexity from bad ones: whether they are where complexity
concentrates into god classes and methods.

## Why sinews are bad: four harms

1. **Ripple.** Changing the data on a path (adding a field, a parameter, a new piece of
   context) means editing every method that carries it, including the ones that only pass it on.
2. **Rigidity.** A step cannot be inserted, removed or reordered without re-plumbing the
   signatures on either side of it.
3. **Comprehension.** To know where a value came from or where it goes, a reader follows the
   whole path.
4. **Attraction.** Data in scope invites logic. A method that already holds much of the data a
   change needs is where the next change is easiest to put, so complexity collects where the
   data is.

Attraction is the harm that links sinews to god classes and methods, and it is the one this
study rests on.

## Measuring a sinew: coupling divergence

The construct began as **coupling divergence**: per method, the coupling going in against the
coupling going out. Used to find outliers among high change-coupling pairs, it was good at
finding god methods. Coupling can be counted three ways, each a different view of what rides on
the control flow. Per method, at a given commit, with `p` the parameters it declares and `a(c)`
the arguments it passes on each call `c` into the project's own code:

| definition | view | in | out |
|---|---|---|---|
| **flow** | the purest sinew: the call is already coupling (the control flow, +1), and data is coupled to it (+1 per parameter) | `1 + p` | `Σ (1 + a(c))` |
| **data** | coupling is the data alone; a call with no arguments adds nothing | `p` | `Σ a(c)` |
| **message** | Alan Kay's objects: a method receives one message, so the first item is the flow itself and coupling starts at the second, with every call at least the message | `max(p − 1, 1)` | `Σ max(a(c) − 1, 1)` |

and in each, `d = out − in`. The flow definition shows a method that makes many calls with no
arguments as sending a lot out, which the data definition misses.

Only parameters and calls are counted. Return values and exceptions are part of the interface and
add to the sinew, but they need the whole call graph to follow; parameters are what visibly
travels.

**Roles, by analogy with a pipe system:**

| d | role | reading |
|---|---|---|
| > 0 | **junction** | creates and directs flow: hands on more data than it receives |
| = 0 | **pipe** | passes data through, transforming it |
| < 0 | **catchment** | a leaf: receives data and processes it |

**Complexity as area.** The companion petclinic degradation study found that complexity is
conserved: changes move it rather than create or destroy it. The system's complexity is then the
sum over its methods, and each method takes up area in proportion to its complexity. The
hypothesis is that in a healthy system most of the area sits in catchments, with leaf processing
doing the work, while junctions stay thin. A system out of balance puts its area in junctions:
methods that hand on much more data than they receive and also hold the logic.

## Classifying concentration: good and bad

The [complexity-concentration study](https://github.com/officefloor/complexity-concentration-study)
identifies god classes and methods at a single checkout as **scale-free complexity outliers**:
units whose complexity is an outlier for their own codebase (modified z ≥ 3.5, Iglewicz and
Hoaglin), with no raw-scale constant. If complexity is conserved, its concentration is where the
god units are.

But not every concentration is a god unit. Its results so far are positive, relative complexity
outliers do recover god classes and methods, but they also flag many units that are complex for
their codebase without being god units. A complex algorithm concentrates complexity in a leaf,
which is where it belongs.

Coupling divergence classifies a concentration:

| where the complexity sits | reading |
|---|---|
| a **catchment** (d < 0) | **good** concentration: leaf processing doing the work |
| a **pipe** or **junction** (d ≥ 0) | **bad** concentration: a unit that directs data and also holds the logic, a god unit |

Attraction is why the second is bad: a unit that holds the data a change needs draws the
logic, so complexity collects where data rides the flow. The study tests this classification
at a single checkout ([`PLAN.md`](PLAN.md)).

## Dependency injection and OfficeFloor

Code built with OfficeFloor has two layers, and the claim differs between them:

- **The flow layer.** The configured flow between procedures. Data is injected, so no data rides
  on the control flow between procedures: sinews cannot form here, by construction.
- **The Java layer.** Ordinary Java inside a procedure: helper methods, plain calls. Sinews can
  form here exactly as in any Java code, but they are bounded by the procedure.

So the claim is not that OfficeFloor code cannot become complex, or cannot grow god units. It
is that complexity cannot concentrate *by riding the flow*, and that a sinew's reach is bounded
by the procedure. OfficeFloor code should therefore behave differently under these measures, and
the difference has to be **predicted before it is observed**. Explaining any OfficeFloor
result afterwards as "OfficeFloor works differently" would make the theory unfalsifiable.

Dependency injection sits in between: injected collaborators are off the control flow, but the
request's data is still passed method to method.

**Two measurement problems** follow from this and are open:

- Injected parameters of an OfficeFloor procedure (`@Val`, `Out<>`, injected services,
  `@RequestBody`) look like parameters to a parameter count, while Spring's field injection is
  invisible to it. The arms are only comparable once the count knows which parameters are
  injected and which are threaded.
- Data bundled into one object (a DTO, a request context) is stamp coupling: one parameter that
  carries many items. A parameter count misses it. In the petclinic run, Spring's largest god
  method, `OwnerRestControllerV1.addOwner(OwnerDto)`, has one parameter. Counting the data items
  read from a received object is the likely fix.

## Where this sits in the literature

- **Tramp data and stamp coupling** (Yourdon and Constantine, *Structured Design*, 1979): data
  passed through modules that do not use it, and records passed where one field is needed. A
  sinew is tramp data seen as a path. Their transaction analysis and "mosque" shape (high fan-in
  at the bottom, thin top) is the healthy-system picture above.
- **Information flow** (Henry and Kafura 1981): complexity × (fan-in × fan-out)². The closest
  ancestor of complexity × divergence, but it **multiplies** in and out, so a unit high on both
  scores highest; divergence **subtracts** them and sets aside the units that take in more than
  they send. The replication by Kitchenham et al. (1990) found size predicted as well; any
  result here has to beat size and complexity, not just correlate.
- **God Class and Brain Class** (Lanza and Marinescu, *Object-Oriented Metrics in Practice*,
  2006): a God Class is very complex (WMC), not cohesive (TCC) and accesses foreign data (ATFD),
  so complexity and coupling are already combined, through fixed thresholds. A Brain Class is a
  complex class that is not a God Class; how a catchment differs from it is to be stated from
  the book's own definition (section 5.5) before any claim is made.
- **Instability** (Martin 1994): `Ce / (Ca + Ce)`, outgoing dependencies against all
  dependencies, per package. A balance of out against in, like divergence, but of who depends
  on whom, at package level, for architecture; divergence counts what is passed on each call,
  per method and class.
- **Message passing coupling** (Li and Henry 1993): the number of send statements in a class,
  close to the call count in the flow definition. **Module coupling** (Dhama 1994): coupling
  from input and output parameters, separating data from control, as the data and flow
  definitions do.
- **Thresholds that are not constants**: relative thresholds (Oliveira, Valente and Lima 2014:
  "p% of classes must have M ≤ k") and benchmark-derived thresholds (Alves et al. 2010) derive a
  constant from a corpus of systems, as did Lanza and Marinescu's. None fits each codebase on its
  own scale.
- **Facades and proxies**: classes with high fan-out but one responsibility are known false
  positives of coupling-based god class detection; an exemption is needed from that side too.
- **System complexity** (Card and Glass 1990): structural (fan-out²) plus data complexity; a
  replication found fan-out² significant.
- **Data clumps** (Fowler, *Refactoring*): the same group of parameters travelling together.
- **Logical / evolutionary coupling** (Gall et al. 1998; Zimmermann et al. 2004): co-change,
  the visible form of ripple.
- **Functional core, imperative shell**: logic in the leaves, wiring at the top; the same
  balance as catchments holding the area.
- **Dependency injection** has little empirical evidence about coupling; there are small
  studies and catalogues of DI anti-patterns, but no history-based test of whether DI reduces
  data threaded down call chains.

Lehman's laws state that complexity grows unless work is done to reduce it; they do not state
that it is conserved. Conservation is the companion study's finding, and this study depends on it.

### What is new

The ingredients above are old. What no work found so far does:

1. **A scale-free god definition per codebase.** A robust outlier rule (modified z ≥ 3.5) fitted
   on each repository's own units, with no raw-scale constant, tested against human labels.
   Relative and benchmark thresholds derive constants from a corpus.
2. **Divergence as a signed balance that classifies concentration.** out − in places each unit
   as catchment, pipe or junction, and complexity in a catchment is set aside as good
   concentration. Information flow multiplies in and out; instability balances dependencies,
   per package.
3. **Three views of coupling compared head to head:** the call as control flow (flow), the data
   alone (data), and the first item as the message (message).
4. **The sinew:** data riding the control flow, with attraction as the harm that concentrates
   complexity. Tramp data is its ancestor.
5. **The test itself:** pre-registered, a human oracle as the primary, tool and replication
   oracles beside it, and a consistency analysis across oracles and ways of calculating
   complexity. Most code smell studies choose and test on the same data.

"No work found so far" is the result of a literature search, not proof of absence.

## Exploratory observations (petclinic, not evidence)

Source: the petclinic degradation study's control run (`blind-202608100006`, strategy
`just-solve`): 10 chains per arm, 61 checkpoints each, the same feature requests applied by AI
agents to a Spring and an OfficeFloor implementation. Outgoing arguments exclude calls to the
method's own class unless stated. Petclinic code is small and was evolved by agents, so none of
this generalises; it was also the sixth way of measuring the same run, so it shapes hypotheses
and tests none.

**Role shares.** OfficeFloor started more catchment-heavy than Spring (64% of complexity vs
42%) with fewer junctions. Several of OfficeFloor's top junctions were artefacts:
`throw new …Exception(x)` and setters on injected entities counted as outgoing data.

**Attraction, by parameters.** Parameters beyond the first did not predict later complexity gain
in either arm (partial Spearman ≈ 0, controlling complexity, size and earlier changes).
Complexity concentrated about equally in both arms (Gini of method complexity 0.23 → 0.34 in
Spring, 0.22 → 0.35 in OfficeFloor).

## Not tested here

Ripple, rigidity and comprehension are harms, but this study tests only attraction, through the
classification above. Rigidity cannot be read from history (history shows the edits, not how
hard they were); it needs a controlled experiment: the same refactoring tasks given to agents on
plain, Spring DI and OfficeFloor versions of one application, measuring edits, failures and
time.
