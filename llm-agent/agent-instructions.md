# Game instructions

Maximize reward over time. Learn the rules from observations and rewards.
The game has no terminal state or resets.
No tools are available.

## Turns and memory

Each request provides `step`, `previous_action`, your previous `memory`, and the
current `observation`. `step` is the action number you are choosing now, starting
at 1 and continuing across resumed runs.

`previous_action` has already been executed once at `step - 1`. The observation,
including its `reward`, is the result of that action. Initially, `previous_action`
and `reward` are null.

Memory was written before `previous_action` was executed. Interpret the current
observation using `previous_action`, even if memory calls that action pending.

Memory is empty initially. It is your only persistent working context beyond
`step` and `previous_action`; retain what you need for future turns, in any format.
Preserve completed experiments with the action, relevant observed features,
before/after measurements, and conclusions. Distinguish observations from
hypotheses, and retain supporting evidence when updating conclusions.

Your reasoning is not carried into the next request. Write hypotheses you want
to revisit into memory, explicitly label them as hypotheses, and preserve
supporting or contradicting evidence. Hypotheses omitted from memory will be lost.
For each hypothesis, record what observations motivated it, why it remains
unconfirmed, and how confident you are in it, with reasons for that confidence.

After a valid reply, your newly chosen action is executed once, advancing the
game one tick. Update memory with the results observed now and record the new
action as pending: its outcome is unknown until the next request.

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
