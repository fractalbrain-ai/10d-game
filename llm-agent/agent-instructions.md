# Game instructions

Maximize reward over time. Learn the rules from observations and rewards.
You cannot die. The game continues regardless of your satiety or hydration
levels, with no terminal state or resets. Learn the reward mechanics from
observations.
No tools are available.

## Turns and memory

Each request provides `step`, `previous_action`, `memory`, `observation`, and
`reply_error`.
`step` numbers the action you are choosing, starting at 1 and continuing across
resumed runs.
`previous_action` ran once at `step - 1`; `observation`, including its `reward`,
shows its result. Initially, `previous_action` and `reward` are null, and memory
is empty.

Memory was written before `previous_action` ran. Update it with the results.
Choose one action that continues your current plan, or deliberately start or
revise a plan. In memory, record the plan, why you continued or changed it, how
the chosen action fits, and what comes next. Mark the action as pending: after
a valid reply it runs once, advancing one tick; you see its outcome next turn.

`reply_error` is null on the first attempt at each step. Otherwise it describes
why your previous reply was rejected. Correct the error and return a new reply
for the same step. The rejected action was not executed and its proposed memory
was discarded; `step`, `previous_action`, `observation`, and last accepted memory
remain unchanged.

Memory, in any format, is your only persistent working context beyond `step`
and `previous_action`. It contains your own notes and may include mistakes.
Reconcile its claims with `previous_action` and new observations, accounting
for changes across steps. Preserve well-supported findings and record evidence
for corrections. Reasoning is not carried forward; omitted findings are lost.
Save what you learn to build on it without unnecessarily repeating reasoning
or experiments. Include:

- Your understanding of game mechanics and observations: what features may mean,
  what actions do, and what determines reward.
- Clearly labeled hypotheses, separate from observed facts. Record their
  motivation, evidence for and against them, why they remain unconfirmed, and
  your confidence with reasons.
- Experimental progress: the hypothesis, relevant features,
  baseline measurements, actions taken, results so far, and what to do or
  observe next. Carry these notes forward until you interpret the results;
  retain the before/after measurements and conclusions.

## Actions

- `NOP`: wait one tick.
- `MOVE_NORTH`: move one cell by `(dx, dy) = (0, +1)`.
- `MOVE_EAST`: move one cell by `(dx, dy) = (+1, 0)`.
- `MOVE_SOUTH`: move one cell by `(dx, dy) = (0, -1)`.
- `MOVE_WEST`: move one cell by `(dx, dy) = (-1, 0)`.
- `EAT_BEAN`: eat the bean beneath you, if present.
- `PICKUP_BEAN`: pick up the bean beneath you if your inventory is empty.
- `DROP_BEAN`: place your carried bean beneath you if that cell is empty.

An inapplicable action behaves like `NOP`.

## Observations

Observations contain `reward`, `satiety_level`, `hydration_level`,
`inventory_count`, and `fov`. You occupy relative coordinate `(0, 0)`;
east is `+x` and north is `+y`.

`fov.beans` lists visible beans as `[dx, dy, channel_1, channel_2]`.
These channels are observed features, not labels for effects.

`fov.channel_3` is a row-major matrix of numeric values.
Rows run from south to north; columns run from west to east.
For a matrix with `H` rows and `W` columns, relative coordinate `(dx, dy)` maps to
`fov.channel_3[H // 2 + dy][W // 2 + dx]`.

## Response

Return one JSON object with exactly two fields:

- `action`: one of the action names above.
- `memory`: a nonempty string containing your complete memory for the next request.

Example:

```json
{"action": "NOP", "memory": "Chosen action: NOP. Outcome pending."}
```

Do not include Markdown fences or other text around the JSON object.
