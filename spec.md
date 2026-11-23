# Project Specification

# Beam Designer

## Purpose
A simplified beam design tool for engineers and students. The user sets up a beam,
places loads on it, and picks the lightest steel or lumber (as selected) section that meets the criteria. The app shows the shear, moment, and deflection diagrams and checks whether the beam is strong and stiff enough, updating instantly as anything changes.

## Users
A civil engineering student checking a homework beam, or an engineer
sizing a floor beam or deck joist.

## Inputs
- Support type: Simply supported (default) or Cantilever (fixed at the left end).
- Span: 4 to 40 ft, set with a slider and a number box that stay in sync. 20ft default
- Loads, listed in a panel where each can be edited or removed:
  - Point loads: magnitude (kips, downward positive/upward negative) and position (ft). Position increases toward the right. Default to 1 kip
    A new point load starts at midspan (at the free end of a cantilever).
  - Uniform loads: magnitude (kips/ft, downward positive/upward negative) and start and end positions (ft). Position increases toward the right. Default to 1 kip/ft from 2ft to 4ft
  - "Add point load" and "Add uniform load" buttons.
  - Point loads can also be dragged along the beam in the drawing,
    snapping to 0.25 ft.
  - Loads that extend past the end of the beam are cut off at the end.
  - Loads that are entirely beyond the span are rejected and the user must input a valid load. If it is a distributed load, it must have a start and end not at the same location, with the start to the left of the end
- Material and section, from these tables:

  Steel W-shapes (E = 29,000 ksi, allowable bending stress Fb = 30 ksi):

  | Section | Ix (in^4) | Sx (in^3) | Weight (lb/ft) |
  |---------|-----------|-----------|----------------|
  | W8x10   | 30.8      | 7.81      | 10 |
  | W10x12  | 53.8      | 10.9      | 12 |
  | W12x26  | 204       | 33.4      | 26 |
  | W14x22  | 199       | 29.0      | 22 |
  | W16x26  | 301       | 38.4      | 26 |
  | W18x35  | 510       | 57.6      | 35 |
  | W21x44  | 843       | 81.6      | 44 |
  | W24x55  | 1350      | 114       | 55 |

  Douglas Fir-Larch No. 2 lumber (E = 1,600 ksi, Fb = 0.900 ksi; estimated self-weight based on 35 lb/ft³):

  | Section | Ix (in^4) | Sx (in^3) | Self-weight (lb/ft) |
  |---------|-----------|-----------|---------------------|
  | 2x8     | 47.63     | 13.14     | 2.638 |
  | 2x10    | 98.93     | 21.39     | 3.366 |
  | 2x12    | 177.98    | 31.64     | 4.102 |

  For this simplified model, calculate the lumber weights using standard actual dressed dimensions (1.5 in by 7.25 in, 9.25 in, and 11.25 in, respectively) and an assumed lumber unit weight of 35 lb/ft³. These are modeling estimates, not product-specific weights.

- Deflection limit: L/240 or L/360 (default L/360). Button/switch to choose.
- Beam self-weight is automatically included as a full-span, downward uniform load for the selected section; it is not editable and has no off switch. Display the selected section's weight in lb/ft and its equivalent load in kip/ft.

## Calculations
- **Sign convention and variables**
  - `x` is distance from the left end (the left support or cantilever fixed end), increasing to the right; `L` is the span. Both are in ft for load, shear, and moment equations. `x_in = 12*x` and `L_in = 12*L` are in inches for deflection.
  - Point load `P_i` (kips) and distributed load `w(x)` (kips/ft) are positive downward; negative values act upward. `a_i` (ft) is the position of point load `P_i`. Distributed loads are integrated only over their clipped portion within the beam span.
  - For a section of weight `W_s` (lb/ft), its self-weight load is `w_sw = W_s/1000` (kips/ft), positive downward, uniform over `0 <= x <= L`. Use `w_total(x) = w_user(x) + w_sw` in equilibrium, shear, moment, and deflection. Apply self-weight exactly once; user-entered uniform loads remain separate and follow their existing clipping rules.
  - Vertical reactions `R_A` and `R_B` (kips) are positive upward. `C_A` (kip-ft) is the cantilever fixed-end reaction moment, positive counterclockwise.
  - `V(x)` is internal shear (kips), positive upward on the left face of a right-hand cut segment. `M(x)` is internal bending moment (kip-ft), positive for sagging. `y(x)` is deflection (inches), positive downward. `θ(x)` is beam rotation in radians, defined by `dy/dx_in` using the small-angle approximation; it is positive when downward deflection increases as `x` increases. These definitions set the signs used in the diagrams.
  - `E` is Young's modulus (ksi), `Ix` is the section's second moment of area (in^4), `Sx` is its elastic section modulus (in^3), and `Fb` is its allowable bending stress (ksi). `fb` is the calculated bending stress (ksi).
- **Reactions**
  - Solve vertical force and moment equilibrium, using the sign convention above:
    - `R_A + R_B - sum(P_i) - integral_0^L w_total(x) dx = 0`
    - `C_A + R_B*L - sum(P_i*a_i) - integral_0^L x*w_total(x) dx = 0`
  - For a simply supported beam, `C_A = 0`; for a cantilever, `R_B = 0`.
- **Shear and moment**
  - Between point loads, `dV/dx = -w_total(x)` and `dM/dx = V(x)`.
  - At point load `P_i`, `V(a_i+) - V(a_i-) = -P_i`; `M(x)` is continuous across a point load.
  - For a simply supported beam, `M(0) = M(L) = 0`. For a cantilever, `M(0) = -C_A` and `M(L) = 0`.
  - For plotting, sample `V(x)`, `M(x)`, `θ(x)`, and `y(x)` at intervals no greater than 1 ft, including every point load, uniform-load start/end, and calculated extremum. Evaluate shear on both sides of each point load.
  - For numerical readouts, evaluate `V(x)`, `M(x)`, and `y(x)` directly from the piecewise beam equations at the requested `x`, and evaluate `θ(x)` from the derivative of the piecewise deflection function; do not interpolate or differentiate between plot samples. Retain full calculation precision through extrema and checks, and round only values shown in the interface.
- **Deflection**
  - Convert moment and position to inch-based units: `M_in(x) = 12*M(x)` (kip-in) and `x_in = 12*x` (in). With `E` in kip/in^2 and `Ix` in in^4, integrate `E*Ix*d^2y/dx_in^2 = -M_in(x)` twice.
  - Calculate the beam rotation as `θ(x) = dy/dx_in` (rad), using the direct first derivative of the deflection function.
  - For a simply supported beam, `y(0) = y(L) = 0`. For a cantilever, `y(0) = 0` and `dy/dx_in` at `x_in = 0` is 0.
- **Maximum values and checks**
  - `V_max = max_x |V(x)|`, `M_max = max_x |M(x)|`, `θ_max = max_x |θ(x)|`, and `y_max = max_x |y(x)|` over `0 <= x <= L`. Include beam endpoints and both sides of shear jumps. Interior moment extrema occur where `V(x) = 0`; interior rotation extrema occur where `M(x) = 0`; interior deflection extrema occur where `dy/dx_in = 0`.
  - Bending stress is `fb = 12*M_max/Sx` (ksi), where the factor 12 converts kip-ft to kip-in. The bending check passes if `fb <= Fb`.
  - Let `n` be the selected deflection-limit denominator (240 or 360). The allowable deflection is `delta_allow = L_in/n` (in), and the deflection check passes if `y_max <= delta_allow`.
  - Check-card ratios are `r_b = fb/Fb` and `r_d = y_max/delta_allow`. A check passes when its ratio is `<= 1`.
- Lightest passing section: of the sections in the chosen material, the
  lightest steel section that passes both checks (if two weigh the same,
  the one with the larger Ix), or the first lumber size in the table
  that passes. Evaluate every candidate using that candidate's own
  self-weight and recalculate reactions, diagrams, extrema, stress, and
  deflection before checking it; do not reuse the currently selected
  section's analysis for other candidates.
- Units: kips, ft, and kip-ft on screen; radians for rotation and inches for deflection.

## Outputs
- A beam drawing labels the span (ft), support types, point-load magnitudes and positions, and user uniform-load magnitudes and loaded intervals. Show reaction arrows with their directions and values (kips), and the cantilever fixed-end reaction moment (kip-ft). Do not draw self-weight as a separate load; identify that it is included in calculations and show its value in the section properties.
- A concise numerical summary shows the support reactions, maximum absolute shear and moment with their positions, maximum absolute rotation and its position, maximum absolute deflection with its position, and maximum bending stress with its position. Show units with every value.
- Four diagrams are stacked below the beam and aligned on the same horizontal x-axis, labeled from 0 to L in ft:
  - Shear, in kips.
  - Moment, in kip-ft.
  - Beam rotation angle `θ(x)`, in radians.
  - Deflected shape, in inches, positive downward.
  - Each diagram has a labeled vertical axis, units, a zero reference line, and readable value ticks. Plot signed values using the calculation sign convention. Label the signed value and position of the point with the maximum absolute value. If the live crosshair is at a labeled maximum, use its inline value instead of a duplicate extrema label.
  - If the deflected shape is vertically exaggerated for visibility, label that the displayed vertical scale is exaggerated.
- Hovering over a diagram or tapping/dragging on it shows a vertical guide across all four diagrams. Show each diagram's current signed value with units beside its crosshair point, and keep a shared readout of x (ft), V (kips), M (kip-ft), `θ` (rad), and y (in) synchronized. When a diagram is keyboard-focused, the arrow keys move the guide along the span and update both the inline and shared readouts. Keep inline values legible on narrow screens.
- Two check cards, Bending and Deflection, show the actual and allowable values with units, the check ratio as a percentage, and PASS or FAIL. The bending card shows `fb` and `Fb` in ksi; the deflection card shows `y_max` and `delta_allow` in inches and identifies the selected L/240 or L/360 limit. The ratio bar is green below 70%, amber from 70% through 100%, and red above 100%; status text must remain explicit and not rely on color alone.
- Identify the currently evaluated material and section, including its self-weight. For the chosen material, suggest the lightest passing section for steel or first in the table for lumber, evaluating every section with its own self-weight, and provide a button to use it. If no listed section passes, say so and do not show a use-this-section button.
- Everything updates immediately whenever any input changes.

## Look and feel
- Opens with an example already loaded (20 ft simply supported W12x26
  with a 1 kip/ft uniform load over the full span), so it is useful the
  moment it opens.
- Clean and professional, like a commercial engineering web app: light
  background, white cards with soft shadows, one accent color, a modern
  system font, and generous spacing. Keep the interface uncluttered, with
  readable text and strong contrast for labels, values, and status messages.
- On desktop, place inputs in a panel on the left and the beam drawing,
  diagrams, and checks on the right. On narrow screens, stack inputs before
  results; keep diagrams within the available width and axis labels and
  numerical values legible. If the desktop input panel is taller than the
  viewport, let it scroll independently so its lower controls remain
  accessible without scrolling through the results.
- Give every input a short, visible label with units. Show plain-language
  validation messages beside the relevant input; do not rely on color alone
  to communicate errors.
- Make controls usable by mouse, touch, and keyboard, with visible keyboard
  focus and touch-friendly targets.
- Explain check-card formulas on hover, keyboard focus, or tap; formula help
  must not depend on hover alone.

## Validation
1. Simply supported, 20 ft, W12x26 (26 lb/ft), user uniform load
   1 kip/ft over the full span: include 0.026 kip/ft self-weight, for
   1.026 kip/ft total uniform load. Reactions are 10.26 k each; maximum
   shear is 10.26 k; maximum moment is 51.30 kip-ft at 10 ft; `fb` is
   18.43 ksi; maximum deflection is 0.624 in at 10 ft; L/360 is 0.667 in,
   so both checks pass. End rotations are `θ(0) = +0.008325 rad` and
   `θ(20 ft) = -0.008325 rad`, maximum absolute angle at both ends.
2. Simply supported, 20 ft, W12x26 (26 lb/ft), point load 10 k at 5 ft:
   include the 0.026 kip/ft full-span self-weight. Reactions are 7.76 k
   (left) and 2.76 k (right); maximum shear is 7.76 k; maximum moment is
   38.47 kip-ft at 5 ft; `fb` is 13.82 ksi; maximum deflection is 0.356 in
   at 8.87 ft. Both checks pass.
3. Cantilever, 10 ft, W12x26 (26 lb/ft), point load 5 k at the free end:
   include the 0.026 kip/ft full-span self-weight. The fixed-end reaction
   is 5.26 k and moment is 51.30 kip-ft; maximum deflection is 0.496 in at
   the free end; tip rotation is `+0.006191 rad`; bending passes and
   L/360 = 0.333 in fails the deflection check.
4. Simply supported 12 ft 2x10 joist (estimated self-weight 3.366 lb/ft),
   user uniform load 0.05 kip/ft: include its self-weight as an additional
   0.003366 kip/ft full-span load. Reactions are 0.3202 k each; maximum
   moment is 0.961 kip-ft at 6 ft; `fb` is 0.539 ksi; maximum deflection
   is 0.157 in at 6 ft. Both checks pass.

## Out of scope
- Moisture- or product-specific changes to the stated lumber self-weight
  estimate, shear stress, lateral-torsional buckling, load combinations,
  and continuous beams.
- Assume linearly elastic materials and small enough deflections for the equations to remain valid.
- Saving designs.

## Build stages
1. **Static page mockup — no calculations**
   - Build the page layout with the example values and chart placeholders.
   - Check desktop and phone layouts, visible labels and units, chart placeholders, and keyboard focus order.
2. **Input controls and state — results remain static**
   - Add support, span, material, section, and limit controls; load add/edit/remove, validation, and point-load dragging.
   - Check defaults, slider/number synchronization, drag snapping, invalid and boundary inputs, and that controls update the intended state.
3. **Reactions, shear, and moment**
   - Implement statics and piecewise `V(x)` and `M(x)` evaluation.
   - Check validation cases 1–3, upward and clipped loads, and queried values between plot samples.
4. **Deflection and design checks**
   - Implement deflection, bending and deflection checks, and section recommendations.
   - Check all four validation cases, both deflection limits, steel/lumber selection, and the no-section-passes case.
5. **Connect results and interactions**
   - Replace placeholders with calculated summaries, diagrams, check cards, and recommendations; add direct crosshair readouts and live updates.
   - Check end-to-end validation, pointer/touch/keyboard interactions, error states, and desktop/phone readability.
6. **Beam rotation angle**
   - Calculate `θ(x)` from the direct derivative of the deflection function; add its maximum absolute value and position, signed diagram between moment and deflection, and synchronized inline/shared crosshair readouts.
   - Check the angle values and signs in validation cases 1 and 3, readouts across all four diagrams, pointer/touch/keyboard synchronization, and desktop/phone readability.
7. **Beam self-weight**
   - Automatically include the selected section's self-weight as a full-span downward uniform load, with no user toggle. Show the section weight and equivalent load; use the existing steel weights and the stated estimated lumber weights.
   - Include self-weight in reactions, shear, moment, rotation, deflection, stress, checks, diagrams, and readouts. Recalculate each section candidate using its own self-weight before determining recommendations.
   - Update validation cases 1–4 with self-weight-inclusive expected results. Check section changes, candidate-specific recommendations, equilibrium, diagrams and direct readouts, and desktop/phone readability.
