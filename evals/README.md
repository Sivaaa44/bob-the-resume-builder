# Evals

Two ways to check Bob's quality.

**Verifier corpus**: `verifier_corpus.yaml`. Labelled honest and fabricated rewrites. Runs in `pytest`
and CI on every change, no API key needed. Found a fabrication in real use? Add it here first.

**Live eval**: `python -m evals.run`. Runs real tailoring on `cases/*.yaml` with your configured model
and scores it:

| column | meaning | want |
|---|---|---|
| cover | expected requirements matched as covered | all |
| gaps | requirements that must *not* be claimed | all |
| proposals (blocked) | suggestions made / blocked by the verifier | some / few |
| leaks | forbidden terms that made it into a passing proposal | **0** |
| tokens, sec | cost and speed | lower |

Run it before and after changing a prompt or model; results land in `results/` (git-ignored).
