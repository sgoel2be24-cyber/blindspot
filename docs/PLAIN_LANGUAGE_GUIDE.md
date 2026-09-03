# BlindSpot, in simple language

## The one-line explanation

BlindSpot helps a risk team check whether its fraud rules are blocking good payments—and tells the team when it needs more evidence.

## The problem

A blocked payment is not automatically a fraudulent payment. But when a payment does not go through, finding out whether blocking it was right can be difficult. Counting blocked payments alone does not tell a business whether its fraud rules are doing a good job.

## How BlindSpot helps

1. Start with the blocked payments.
2. Pick a sample to review, before looking at the answers.
3. Use the review results to estimate what may be happening in the whole group.
4. Show the uncertainty. Keep missing answers visible.
5. Give the risk team a summary it can inspect before deciding what to investigate.

## The impact we aim for

Help a business notice unnecessary blocks, plan its review effort and question a weak conclusion. This is the intended benefit, not proof of recovered revenue or measured customer impact.

## Three screens, three questions

| Screen | Question |
|---|---|
| 1. Blocked payments | Were good payments blocked? |
| 2. Check a sample | What did we find in the payments we reviewed? |
| 3. Can we trust the result? | How much do we know, and what is still missing? |

## Words to use when presenting

| Technical term | Say this first |
|---|---|
| False decline | A good payment that was blocked |
| Block precision | The share of blocked payments that were fraud |
| Sampling propensity | A payment's chance of being picked for review |
| Confidence interval | An estimated range, not a guaranteed exact answer |
| Sealed oracle | A separate answer key used only to check the experiment |
| Abstention | We do not know enough to conclude yet |

Never call every percentage “accuracy.” A percentage about the review sample is not automatically a percentage about all blocked payments. Never describe a 95% method as a promise that this particular answer is correct.

## What is real and what is simulated?

The application and local review-file workflow work. The main experiment uses real historical IEEE-CIS transactions with simulated blocking and hidden answers. The delayed, missing and wrong review answers are simulated tests. There is no live Razorpay connection, no automatic approval and no measured money saved.

## Presentation rule

Explain the problem, show one useful result, then explain what it means for a person. Keep technical details available on request. Simplify the words—not the evidence, uncertainty or limitations.
