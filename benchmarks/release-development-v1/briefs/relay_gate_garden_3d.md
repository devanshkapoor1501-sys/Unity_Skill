# Public development task: 3D relay gate garden

Create an editable Unity 3D garden puzzle with two independently reachable
pressure plates and a timed relay gate. The player uses WASD, can push a movable
crate onto the first plate, and must reach the second plate within eight seconds
of activation. The gate opens only while both requirements hold. Crossing the
gate activates a checkpoint; falling from the route returns the player and
movable crate to their checkpoint states. Reaching the marked exit wins. R
restarts the entire puzzle, including the timer, plates, gate, crate and checkpoint.

Keep the puzzle's mechanics intact. If timed relay logic, crate pushing or
checkpoint state restoration lacks executable support, report each gap and a
bounded implementation/probe plan. An arena with a renamed timer does not fulfill
this brief. Preserve editable sources and test plate ordering, deadline expiry,
gate collision, checkpoint restoration, goal contact and complete restart using
physical runtime observations and deliberate faults.

This is a visible development specification, not protected evaluation. Do not
fabricate a completed puzzle, passing tests or evaluator-owned acceptance.
