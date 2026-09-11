# Feasibility of generating new instances with official CLADDER code

The authors' generator passed a smoke test for four probabilistic query types. This does not yet establish or complete a new evaluation.

- The official source is `https://github.com/causalNLP/cladder`, pinned to commit `3d2d1169b4b939a09048a6a75956c8972a93cc38`. The `causalbenchmark` package reports `__version__=0.1`.
- The authors' source was not modified. The test used `causalbenchmark.generator.generate_questions`, their `RandomBuilder` and `create_query`. The original CLI example is `fig generate demo`, with configuration at `config/demo.yml`.
- The existing source-host interpreter is `D:\env\envs\TensorFlow1\python.exe`, running Python 3.9.16. Its main environment was unchanged. Packages were added only under `C:\Users\Wyatt\Documents\Codex\transfers\fresh_cladder_feasibility_20260910\pydeps` and accessed through sys.path.
- The added packages were pomegranate 0.14.8, omnibelt 0.7.6, omnifig 1.0.1, omniply 0.1.1, tabulate 0.9.0, indexed 1.3.0 and dill 0.3.8. pomegranate used the official CPython 3.9 Windows wheel, which was 6.49 MB. No large extension was compiled. Additional downloads totalled approximately 7 MB.
- Existing NumPy 1.22.4, pandas 2.1.4, SciPy 1.10.1 and NetworkX 3.1 installations were reused. pandas reported only a warning about an old bottleneck version, which did not affect generation. The original environment was not upgraded for this warning.

## Observed smoke-test results

Two instances were generated for each of ATE/frontdoor, ETT/frontdoor, NDE/mediation and NIE/mediation, giving eight distinct CPTs. Generation took 0.219 seconds, excluding Python imports. The authors' question text, given probabilities, SCM parameters and model-computed gold labels were saved in `probe8.json`.

An independent calculator used three inputs separately, namely the given probabilities, public probabilities rounded to two decimal places, and complete SCM CPTs. All eight label directions agreed, and all eight full-precision effects matched the authors' groundtruth. Neither the eight complete-parameter signatures nor their relevant-mechanism CPT signatures appeared among the 7,064 historical metadata records. A later check showed that these records correspond to 4,256 canonical complete-CPT signatures, rather than 7,064 independent SCMs. Matching compared structures and exact numerical values, rather than only qids, model names or story text.

Validation is recorded in `probe8_independent_check.json`. The generation script is `remote_probe.py`, and the checking script is `check_probe.py`.

## Minimal plan for 246 new instances

Use the predefined quotas of 94 ATE, 82 ETT, 20 NDE and 50 NIE questions, with a fixed seed sequence distinct from the smoke test. Retain one question from one new SCM for each target. The authors' RandomBuilder resamples node conditional-probability tables from Uniform(0,1). Preserve every seed, spec, story template, complete CPT, model graph and original query metadata record.

Fixed exclusions comprise generation failure, an original answer outside yes/no, duplicate complete parameters or query-relevant CPTs against historical or already selected models, disagreement between independent full-precision recalculation and the authors' values or labels, and a changed answer direction or zero effect when using public probabilities rounded to two decimal places. Exclusion logs retain candidate seeds and reasons. Selection uses data validity only and does not read Qwen results. Gold labels are not derived from old reasoning.step5 text.

Generation alone for 246 models is estimated to take a few seconds to tens of seconds. Data checks, export and manifest freezing should take 5–10 minutes, with a 20-minute allowance. Before running the 246-instance generation, these remain time estimates based on the smoke test.

## Limitations to report

1. This is a new random-SCM extension using a fixed version of the authors' code. Its RandomBuilder distribution differs from the difficulty-builder selection distribution underlying the old balanced data. It is not a random holdout from the original balanced benchmark.
2. The confirmed novelty concerns probabilistic instances separated from old parameter and mechanism instances. Story templates and graph families are reused, so this is not cross-story or cross-graph generalisation.
3. Deterministic counterfactuals are not added solely to fill a category. The authors' deterministic mechanism set is finite. Changing irrelevant root probabilities or renaming variables does not produce a new target-relevant mechanism. Such examples require additional mechanism-overlap checks before being described as new independent instances.
4. The authors' reasoning.step5 is retained as source material, but known displayed-expression errors prevent treating it directly as a semantic oracle.
5. This task performed no model inference or external judging, did not inspect intermediate main300 results, and changed no old source file.
