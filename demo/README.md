# Demo gallery

Every animation ProofMotion has rendered, with the question that produced it.
Nothing here was hand-edited — each is the pipeline's own output, kept whether
it came out well or badly, because the failures are the more useful record.

`composed` means the scene was built from verified components rather than
hand-written Manim. `defects` counts what the layout checker measured on the
finished scene: text over text, text over geometry, and anything off-frame.

47 animations, 16.7 MB, 3 assembled.

Rebuild with `uv run python scripts/build_demo.py`.

| # | Question | Model | Length | Assembled | Composed | Components | Defects |
|---|---|---|---|---|---|---|---|
| 1 | [Explain gradient descent visually for a beginner](explain-gradient-descent-visually-for-a-beginner__unknown.mp4) | ?/unknown | 13.6s | no | no | — | — |
| 2 | [Explain gradient descent visually for a beginner](explain-gradient-descent-visually-for-a-beginner__unknown-2.mp4) | ?/unknown | 13.6s | no | no | — | — |
| 3 | [Explain gradient descent visually for a expert](explain-gradient-descent-visually-for-a-expert__unknown.mp4) | ?/unknown | 13.6s | no | no | — | — |
| 4 | [Explain gradient descent visually for a expert](explain-gradient-descent-visually-for-a-expert__unknown-2.mp4) | ?/unknown | 2.0s | no | no | — | — |
| 5 | [Explain the derivative as the limit of secant slopes](explain-the-derivative-as-the-limit-of-secant-slopes__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 21.4s | no | no | — | — |
| 6 | [Explain the derivative as the limit of secant slopes](explain-the-derivative-as-the-limit-of-secant-slopes__deepseek-v4-flash.mp4) | deepseek/deepseek-v4-flash | 1.0s | no | no | — | — |
| 7 | [Show why the sum of the first n odd numbers equals n squared](show-why-the-sum-of-the-first-n-odd-numbers-equals-n__deepseek-v4-flash.mp4) | deepseek/deepseek-v4-flash | 38.4s | no | no | — | — |
| 8 | [Explain why the derivative of sin(x) is cos(x)](explain-why-the-derivative-of-sin-x-is-cos-x__deepseek-v4-flash.mp4) | deepseek/deepseek-v4-flash | 32.3s | no | no | — | — |
| 9 | [Two vertical poles, each 50 metres tall, stand on level ground. An 80-met...](two-vertical-poles-each-50-metres-tall-stand-on-leve__deepseek-v4-flash.mp4) | deepseek/deepseek-v4-flash | 48.7s | no | no | — | — |
| 10 | [mathematical letters running on the curve](mathematical-letters-running-on-the-curve__deepseek-v4-flash.mp4) | deepseek/deepseek-v4-flash | 20.2s | no | no | — | 0 |
| 11 | [Explain why the derivative of sin(x) is cos(x)](explain-why-the-derivative-of-sin-x-is-cos-x__deepseek-v4-flash-2.mp4) | deepseek/deepseek-v4-flash | 72.5s | no | no | — | 0 |
| 12 | [the heading of the topic becomes it's curve for explanation](the-heading-of-the-topic-becomes-it-s-curve-for-expl__deepseek-v4-flash.mp4) | deepseek/deepseek-v4-flash | 25.6s | no | no | — | 0 |
| 13 | [Explain why the derivative of sin(x) is cos(x)](explain-why-the-derivative-of-sin-x-is-cos-x__deepseek-v4-flash-3.mp4) | deepseek/deepseek-v4-flash | 27.0s | no | no | — | 0 |
| 14 | [Two vertical poles, each 50 metres tall, stand on level ground. An 80-met...](two-vertical-poles-each-50-metres-tall-stand-on-leve__deepseek-v4-flash-2.mp4) | deepseek/deepseek-v4-flash | 35.8s | no | no | — | 0 |
| 15 | [Two vertical poles, each 50 metres tall, stand on level ground. An 80-met...](two-vertical-poles-each-50-metres-tall-stand-on-leve__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 30.5s | no | no | — | 0 |
| 16 | [Explain why the sum of interior angles of a triangle is 180 degrees](explain-why-the-sum-of-interior-angles-of-a-triangle__gpt-5-2.mp4) | openai/gpt-5.2 | 23.0s | no | no | — | 0 |
| 17 | [Explain why the derivative of sin(x) is cos(x)](explain-why-the-derivative-of-sin-x-is-cos-x__gpt-5-2.mp4) | openai/gpt-5.2 | 36.6s | no | no | — | 0 |
| 18 | [Explain why the derivative of sin(x) is cos(x)](explain-why-the-derivative-of-sin-x-is-cos-x__gpt-5-6-terra.mp4) | openai/gpt-5.6-terra | 30.0s | no | no | — | 0 |
| 19 | [Show how gradient descent converges to the minimum of a convex function](show-how-gradient-descent-converges-to-the-minimum-o__gpt-5-6-terra.mp4) | openai/gpt-5.6-terra | 30.1s | no | no | `function_plot`, `tangent_secant` | 0 |
| 20 | [Show how gradient descent converges to the minimum of a convex function](show-how-gradient-descent-converges-to-the-minimum-o__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 28.7s | no | yes | `function_plot`, `tangent_secant` | 1 |
| 21 | [Show how gradient descent converges to the minimum of a convex function](show-how-gradient-descent-converges-to-the-minimum-o__gpt-5-2.mp4) | openai/gpt-5.2 | 18.3s | no | yes | `function_plot`, `iteration_trace`, `tangent_secant` | 0 |
| 22 | [Show how gradient descent converges to the minimum of a convex function](show-how-gradient-descent-converges-to-the-minimum-o__deepseek-v4-pro-2.mp4) | deepseek/deepseek-v4-pro | 22.6s | no | yes | `function_plot`, `iteration_trace`, `tangent_secant` | 0 |
| 23 | [teach me how can i sum all positive numbers and the result is still negative](teach-me-how-can-i-sum-all-positive-numbers-and-the__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 43.9s | no | no | — | 0 |
| 24 | [convuluational layes visualization](convuluational-layes-visualization__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 25.8s | no | no | — | 0 |
| 25 | [Explain and prove the inequality ∫₀¹ (f'(x))² dx ≥ π² ∫₀¹ f(x)² dx for tw...](explain-and-prove-the-inequality-f-x-dx-f-x-dx-for-t__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 69.4s | no | no | `function_plot` | 0 |
| 26 | [Solve and visually explain a frictionless block moving through a vertical...](solve-and-visually-explain-a-frictionless-block-movi__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 48.5s | no | yes | `function_plot` | 0 |
| 27 | [Show why a bead on a vertical loop needs a minimum speed at the top](show-why-a-bead-on-a-vertical-loop-needs-a-minimum-s__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 25.3s | no | yes | `circular_motion` | 0 |
| 28 | [Explain the normal distribution and what one standard deviation covers](explain-the-normal-distribution-and-what-one-standar__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 29.9s | no | yes | `distribution_plot` | 4 |
| 29 | [Show step by step why the difference of two squares factors as (a-b)(a+b)](show-step-by-step-why-the-difference-of-two-squares__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 29.9s | no | no | `equation_chain` | 0 |
| 30 | [Show how binary search narrows down to a target in a sorted array](show-how-binary-search-narrows-down-to-a-target-in-a__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 29.3s | no | yes | `array_cells` | 3 |
| 31 | [Show why a bead on a vertical loop needs a minimum speed at the top](show-why-a-bead-on-a-vertical-loop-needs-a-minimum-s__deepseek-v4-pro-2.mp4) | deepseek/deepseek-v4-pro | 29.1s | no | no | — | 0 |
| 32 | [Show what the matrix [[2,1],[1,2]] does to the plane and its eigenvectors](show-what-the-matrix-2-1-1-2-does-to-the-plane-and-i__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 28.9s | no | no | — | 1 |
| 33 | [Solve and visually explain a frictionless block moving through a vertical...](solve-and-visually-explain-a-frictionless-block-movi__deepseek-v4-pro-2.mp4) | deepseek/deepseek-v4-pro | 69.1s | no | yes | `circular_motion`, `energy_bars` | 0 |
| 34 | [Explain the normal distribution and what one standard deviation covers](explain-the-normal-distribution-and-what-one-standar__deepseek-v4-pro-2.mp4) | deepseek/deepseek-v4-pro | 23.3s | no | yes | `distribution_plot` | 0 |
| 35 | [P and M latter bheavig like human](p-and-m-latter-bheavig-like-human__deepseek-v4-pro.mp4) | deepseek/deepseek-v4-pro | 26.5s | no | no | — | 0 |
| 36 | [Show step by step why the difference of two squares factors as (a-b)(a+b)](show-step-by-step-why-the-difference-of-two-squares__deepseek-v4-pro-2.mp4) | deepseek/deepseek-v4-pro | 12.5s | no | no | — | 0 |
| 37 | [P and M latter bheavig like human](p-and-m-latter-bheavig-like-human__deepseek-v4-flash.mp4) | deepseek/deepseek-v4-flash | 8.0s | no | no | — | 0 |
| 38 | [Show how binary search narrows down to a target in a sorted array](show-how-binary-search-narrows-down-to-a-target-in-a__deepseek-v4-pro-2.mp4) | deepseek/deepseek-v4-pro | 24.7s | no | no | — | 0 |
| 39 | [llm attenstion visulization](llm-attenstion-visulization__deepseek-v4-flash.mp4) | deepseek/deepseek-v4-flash | 21.5s | no | no | — | 0 |
| 40 | [attenstion in trsnformer example](attenstion-in-trsnformer-example__gpt-5-6-terra.mp4) | openai/gpt-5.6-terra | 29.0s | no | no | — | 0 |
| 41 | [attenstion in trsnformer example](attenstion-in-trsnformer-example__gpt-5-6-terra-2.mp4) | openai/gpt-5.6-terra | 29.0s | no | no | — | 1 |
| 42 | [make some guessing face that suggest user to think](make-some-guessing-face-that-suggest-user-to-think__gpt-5-6-terra.mp4) | openai/gpt-5.6-terra | 5.1s | no | no | — | 0 |
| 43 | [Ek bus seedhi sadak par 72 kilometer prati ghante ki raftaar se chal rahi...](ek-bus-seedhi-sadak-par-72-kilometer-prati-ghante-ki__gpt-5-6-terra.mp4) | openai/gpt-5.6-terra | 32.5s | no | no | — | 0 |
| 44 | [Show the tangent line to f(x)=x^2-4x+5 at x=3 and what its slope means](show-the-tangent-line-to-f-x-x-2-4x-5-at-x-3-and-wha__deepseek-v4-flash.mp4) | deepseek/deepseek-v4-flash | 16.5s | no | no | `function_plot`, `tangent_secant` | 2 |
| 45 | [Show the tangent line to f(x)=x^2-4x+5 at x=3 and what its slope means](show-the-tangent-line-to-f-x-x-2-4x-5-at-x-3-and-wha__deepseek-v4-flash-2.mp4) | deepseek/deepseek-v4-flash | 22.8s | yes | yes | `equation_chain`, `function_plot`, `tangent_secant` | 1 |
| 46 | [Show the tangent line to f(x)=x^2-4x+5 at x=3 and what its slope means](show-the-tangent-line-to-f-x-x-2-4x-5-at-x-3-and-wha__deepseek-v4-flash-3.mp4) | deepseek/deepseek-v4-flash | 19.3s | yes | yes | `tangent_secant` | 0 |
| 47 | [Show the tangent line to f(x)=x^2-4x+5 at x=3 and what its slope means](show-the-tangent-line-to-f-x-x-2-4x-5-at-x-3-and-wha__deepseek-v4-flash-4.mp4) | deepseek/deepseek-v4-flash | 21.3s | yes | yes | `function_plot`, `tangent_secant` | 0 |

## Notes

- Early entries predate the layout engine and show the overlapping text that motivated it.
- Runs against several models on the same question are kept side by side deliberately;
  they are the clearest evidence of what is the system's doing and what is the model's.
- `assembled` marks scenes emitted by the deterministic assembler rather than written
  by the coding agent. Those runs skip the coder loop entirely.
