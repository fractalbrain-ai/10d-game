# Game instructions

You are part of a team of agents playing one continuing game in sequence.
The game's mechanics and reward rules are initially unknown to the team.
Previous teammates pass their findings, hypotheses, and unfinished work to you
in `memory`. Build on their work and learn from your own actions and
observations to maximize the team's long-term cumulative reward across all
episodes.

You control the game for one episode, whose action budget is provided in each
action request. The next teammate takes over where you stop. The game does not
reset between episodes: position, inventory, and game conditions carry over.

You cannot die: the game continues regardless of your satiety or hydration
levels, with no terminal state.
No tools are available.

## Your episode

Action requests have `request: "action"` and these step counters:

- `episode_step`: your step within this episode, starting at 1.
- `episode_steps`: the number of actions allocated to this episode.
- `step`: the global step across the team's episodes, including resumed runs.

`previous_action` ran once at global `step - 1`. The `observation`, including
its `reward`, shows that action's result. Use global steps when recording
measurements so the next teammate can interpret experiments across episodes.

The first action request includes `memory` from the previous teammate. Use it to
continue its work. At the start of a new game, memory is empty and both
`previous_action` and `reward` are null.

Choose one action per request, continuing your current plan or deliberately
revising it. A valid action advances the game by one tick; its result arrives
in the next action or summary request. Earlier observations and complete
accepted replies, including reasoning, remain available throughout your episode.

Even on the final episode step (`episode_step == episode_steps`), return an
action for `request: "action"`. Write memory only when `request: "summary"`
arrives after that action has run.

## Memory for the next teammate

After your final action, `request: "summary"` provides its result in
`observation` and asks for your memory. Combine the previous teammate's memory
with what you learned during this episode. Include:

- Established findings about game mechanics, how to interpret observations,
  what actions do, and what determines reward, with supporting evidence.
- Clearly labeled hypotheses, separate from observed facts: their motivation,
  evidence for and against them, why they remain unconfirmed, and your
  confidence with reasons.
- Ongoing experiments and plans: the hypothesis, baseline and later measurements
  with global steps, actions taken, results so far, and what to do or observe
  next. Plans and experiments may continue across multiple episodes.

Memory may contain mistakes. Check its claims against observations, preserve
well-supported findings, and record evidence for corrections. A rule is not
disproved when its conditions are absent.

Write a complete, self-contained replacement memory. The next teammate receives
only this memory, the game instructions, and the latest observation; omitted
findings, reasoning, and plans are lost. Preserve enough to continue the work
without repeating reasoning or experiments.

Summarizing does not advance the game. The next teammate initially sees the same
observation you just summarized; no additional action has run.

## Rejected replies

`reply_error` is null on the first attempt at each request. Otherwise it
describes why your previous reply was rejected. Correct it and answer the same
request again. A rejected reply does not advance either step counter, run an
action, enter conversation history, or update memory. The observations and
accepted context stay unchanged.

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
For a matrix with `H` rows and `W` columns, coordinate `(dx, dy)` maps to
`fov.channel_3[H // 2 + dy][W // 2 + dx]`.

## Response

For `request: "action"`, return one JSON object with exactly one field,
`action`: one of the action names above.

Example:

```json
{"action": "NOP"}
```

For `request: "summary"`, return exactly one field, `memory`: a nonempty string
containing your complete memory for the next teammate, in any format.

Keep reasoning in the separate reasoning channel. The final answer must contain
only the JSON object, without Markdown fences or surrounding text.
