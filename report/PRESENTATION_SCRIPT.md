# Presentation script: Team bakarwadi (6 minutes + 4 minutes of questions)

About 930 spoken words, which is about 6.5 minutes at a calm pace, so speak briskly or drop the
last bullet of Part 6 if you run long. Speaker labels A, B and C are
placeholders; split the parts however suits you. Times are cumulative.

---

## Part 1: The one idea that sets us apart (A, 0:00–0:50)

> Good evening. We are team bakarwadi. Our bot is comboop1. On the leaderboard it beats F 81 percent
> of the time and O 66 percent of the time.
>
> If you remember one thing from us, remember this: **we never trained against F.** Not one game.
> F was our test set and nothing else. Every improvement you will see came from the bot playing
> against older versions of itself. Our own estimate of the F score matched the leaderboard within the
> error bar. So we believe the number is real, and not tuned to one opponent.
>
> We want to spend most of our time on *how* we got each idea, because each one came from a
> measurement, not from a guess.

## Part 2: We measured before we built anything (A, 0:50–1:40)

> The first thing we did was time the engine. Copying the game and playing one move costs 0.1
> milliseconds. One random game to the end costs 11 milliseconds. We get about 12 milliseconds per
> move.
>
> That one calculation decided the whole design. MCTS needs hundreds of random games per move, and we
> cannot afford even one. So MCTS was out, and deep search also. We confirmed it on catanatron's
> own AlphaBeta bot: even with no clock, it beat F only 57 percent of the time.
>
> So we decided our edge had to come from **judging a position well in one look**, not from looking far
> ahead.

## Part 3: We read the opponent's code to find its blind spots (B, 1:40–2:30)

> Next, we read F's code. F scores public victory points first, and everything else is a tie-breaker.
> It does not count hidden VP cards, and it does not value a knight until it is played.
>
> We ran F against itself to check what this means in practice. The winner held Largest Army in only 3
> percent of games, and F bought just two dev cards a game. Largest Army is 2 free points that F will
> never fight for.
>
> So we built our bot to want those points. Our first tuned bot, v5, held Largest Army in about 89 percent of
> its wins against F. **We did not make the bot cleverer everywhere. We made it greedy exactly where F is
> blind.**

## Part 4: How the bot thinks (B, 2:30–3:30)

> Our bot scores every position with one formula, and **every weight in it is in victory points**. For
> example, "a hand that can build a city right now is worth 0.47 points". We chose this on purpose,
> because then a human can read every number and ask, "does this make sense?"
>
> On each move, the bot tries every legal move on a copy of the game, scores each result, and plays the
> best. Two ideas made a big difference, and both came from watching games:
> - We saw the bot finishing games with knights still in hand. Playing a knight looked like "losing a
>   card", because the gain comes one step later, from the robber move. So we score a knight together
>   with its robber move. That alone gave **5 points**.
> - Buying a dev card in a simulation draws one random card, so the decision was a coin toss. We score
>   the **average** card instead.
>
> Then we tuned all the weights with SPSA, by self-play. Two copies with slightly different weights play
> each other, and we move towards whichever wins. That was the biggest single jump: **+6.5 points**,
> to 79 percent against F.

## Part 5: Our most important failure (C, 3:30–4:30)

> Here is the experiment we learned the most from. We thought: why hand-set weights at all? So we fit
> a logistic regression to predict the winner from game positions. It was 78 percent accurate. As a bot,
> it won **10 percent**.
>
> We looked at the weights to find out why. "Holding the cards for a city" was worth 1.5 points, more
> than building the city. Winners usually hold lots of cards, so the model learned that. But a greedy
> bot then never builds; it just keeps holding. **A model that predicts who wins is not a model that
> picks good moves.** Our VP-unit formula is what let us spot this in one minute: no state should be
> worth more than the point it leads to.
>
> But then we asked: where *would* prediction be the same as choosing? In the **opening**. All four
> starting settlements are compared at one moment, with nothing half-built. So we learned the opening
> from 16,000 self-play games and searched the snake draft with it. That gave another 2.5 to 5 points
> against every bot we tried. Same tool, right place.

## Part 6: How we kept ourselves honest (C, 4:30–5:30)

> Catan is very noisy. At 400 games the error bar is plus or minus 4 points. Several "improvements" we
> saw early simply vanished at 300 games. So:
> - we compared versions on **the same boards and the same dice**, with seats swapped;
> - we did not accept any change below about 2 standard errors.
>
> That is also why we can tell you what did *not* work. Search add-ons, endgame tricks, community
> tips, a second round of tuning: all of them landed within noise.
>
> Win rates hide rare mistakes, so we also **audited about 950 single decisions**. For each one we
> replayed every alternative move with the same dice. One mistake stood out: playing Monopoly before
> rolling cost about 7 points in those situations.
>
> Finally, we attacked our own bot to look for crashes and clock problems before the organisers could
> find them.

## Part 7: Close (A, 5:30–6:00)

> So, what sets us apart:
> - we measured before we designed;
> - we exploited exactly what F cannot see;
> - we never touched F while tuning;
> - we learned only where prediction equals decision.
>
> The result is 81 percent against F and 66 percent against O, with zero games over the clock. Thank
> you. We are happy to take questions.

---

## Questions you are likely to get

| Question | Short answer |
|---|---|
| **Why not MCTS or reinforcement learning?** | One random playout costs 11 ms, almost a whole move's budget. Published from-scratch RL bots for Catan lost even to random players, and we had one day. |
| **How do you know you didn't overfit to F?** | F was never used in tuning or in choosing versions. Our local F numbers (0.791 and 0.820) matched the leaderboard (0.779 and 0.813). We also gained against O, which we never trained against. |
| **Why do you think the learned evaluation failed?** | It learned which states *look like* winning, not which *moves* win. Holding cards correlates with winning, so the greedy bot hoards. The fix is a decision-level signal: compare the chosen move against the alternatives, or TD learning. More outcome data does not fix it. |
| **Then why did learning work for the opening?** | Settlements are compared at one moment with nothing in progress, so predicting the outcome from a placement and choosing the placement are the same question. |
| **What is SPSA, and why use it?** | It nudges all weights at once in a random ± direction, plays the "+" and "−" versions against each other, and steps toward the winner. It costs two bots per step regardless of how many weights there are, and it works with a noisy, non-differentiable win rate. 93 steps took about 12 minutes on 4 cores. |
| **Why are the weights in VP units?** | So every number is a readable claim we can sanity-check. That is how we caught the hoarding bug. |
| **Is comboop1 really better than combo, or is it noise?** | On the same 1000 boards it scored 0.820 vs 0.787 against F. Head-to-head it won 0.523 over 1000 games, about 1.5 standard errors, so it is suggestive on its own. The leaderboard agrees: comboop1 improved on v5 against both F and O. |
| **Why does the bot race instead of block?** | SPSA set the opponent weight to 0.74. Gaining 1 point is worth more than taking 1 from the opponent, because in 2-player you win by reaching 10 first. |
| **Why didn't you submit the Monopoly and clock fix?** | The fixed version scored 0.770 vs F against comboop1's 0.820, because it runs the turn plan less often. comboop1 had 0 games over the clock on the leaderboard, so we kept it. *(Check this matches the team's actual reason.)* |
| **What would you do with more time?** | TD learning on after-move positions; averaging over several guesses of the hidden cards, since we use only about 20 percent of the clock; and re-tuning with the turn plan switched on. |
| **What did you learn that holds beyond Catan?** | (1) Predicting an outcome is not the same as choosing an action. (2) Under a tight compute budget, a better evaluation beats deeper search. (3) Find what your opponent's objective ignores. (4) Keep a held-out opponent, use paired comparisons, and distrust small samples. |

## Numbers to keep in your head

| What | Number |
|---|---|
| Leaderboard, comboop1 | **0.813 vs F, 0.658 vs O**, 0 games over the clock |
| Leaderboard, first submission (v5) | 0.779 vs F, 0.626 vs O |
| Progression vs F | 0.635 (v1) → 0.683 → 0.726 → 0.791 (v5) → 0.820 (comboop1, local) |
| Biggest single gain | SPSA, +6.5 points |
| Learned evaluation | 78 % accurate as a predictor, 10 % as a bot |
| Opening model | 16,000 games, AUC 0.74 |
| Decision audit | about 950 decisions; Monopoly before roll costs 7.3 ± 5.7 points |
| Error bar | ±4.4 points at 400 games, ±2.5 at 1000 |
