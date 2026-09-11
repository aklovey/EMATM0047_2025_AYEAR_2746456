# Executed Fresh246 generation and filtering procedure

`generate_fresh246_executed.py` is the complete driver actually used to generate and filter 246 questions. It was copied byte-for-byte from this directory's existing `remote_generate246.py` (9,106 bytes), rather than reconstructed from the 8-question probe. The program was already stored locally and was sent through SSH stdin to the host Python interpreter for execution. Archiving this copy involved only byte-equality and syntax checks. Generation was not rerun, and freeze246 data were unchanged.

## Original execution command

The following command was executed in PowerShell from the local working directory `C:\Users\aklovey\Documents\Codex\2026-09-10\9-4-cause-1-8-8`.

```powershell
Get-Content -LiteralPath 'work\fresh_cladder_feasibility\remote_generate246.py' -Raw |
  ssh -o BatchMode=yes main-laptop D:/env/envs/TensorFlow1/python.exe -
```

The archived entry point with identical content is shown below.

```powershell
Get-Content -LiteralPath 'work\fresh_cladder_feasibility\generate_fresh246_executed.py' -Raw |
  ssh -o BatchMode=yes main-laptop D:/env/envs/TensorFlow1/python.exe -
```

The second command records an equivalent invocation and was not executed during archiving. The driver immediately reports `Frozen manifest exists; do not overwrite` if `freeze246/manifest.json` already exists. Reproduction should use an independent copy or clean working directory while retaining the original data. Changes to the driver's `R` path should be made and recorded in a separate execution copy; the archived executed version remains unchanged.

## Host interpreter, directories and inputs

- Interpreter `D:\env\envs\TensorFlow1\python.exe`, running Python 3.9.16. This was an existing interpreter; no older Python installation was added.
- Fixed driver path `R` is `C:\Users\Wyatt\Documents\Codex\transfers\fresh_cladder_feasibility_20260910`.
- Official source is under `R\source\`, from this directory's `official_cladder_source.zip`, commit `3d2d1169b4b939a09048a6a75956c8972a93cc38`. The author's `generate_questions`, `RandomBuilder` and query implementations were called without modification.
- Added dependencies are under `R\pydeps\` and loaded through `sys.path`, without writing to the existing Python site-packages.
- The independent calculator `R\independent_calc.py` corresponds to the local file with that name. It implements separate calculations from given probabilities and CPTs, without calling the author's reasoning.step5.
- Probe exclusions use `R\probe8.json`, which contains the earlier 8 feasibility SCMs and excludes their complete and target-relevant CPTs.
- Historical exclusions use `E:\CAUSE\data\cladder-v1-meta-models.json`. It contains **7,064 metadata records** but only **4,256 distinct numerical SCM signatures** under the graph-plus-normalised-complete-CPT rule. It must not be described as 7,064 independent SCMs.
- Formal outputs are under `R\freeze246\`. The local frozen copy is in this directory's `freeze246\`.

## Recorded dependency versions

| Package | Runtime version | Source |
|---|---|---|
| pomegranate | 0.14.8 | Separate pydeps, CPython 3.9 Windows wheel |
| omnibelt | 0.7.6 | Separate pydeps |
| omnifig | 1.0.1 | Separate pydeps |
| omniply | 0.1.1 | Separate pydeps |
| tabulate | 0.9.0 | Separate pydeps |
| indexed | 1.3.0 | Separate pydeps |
| dill | 0.3.8 | Separate pydeps |
| numpy | 1.22.4 | Existing interpreter environment |
| pandas | 2.1.4 | Existing interpreter environment |
| scipy | 1.10.1 | Existing interpreter environment |
| networkx | 3.1 | Existing interpreter environment |

Dependencies were installed in three batches using the existing Python interpreter with `-m pip install --no-deps --target R\pydeps`.

```text
pomegranate==0.14.8 omnibelt==0.7.6 omnifig==1.0.1 omniply==0.1.1 tabulate
indexed==1.3.0
dill==0.3.8
```

The initial installation did not pin the tabulate minor version; the installed version was 0.9.0, as recorded above. Reproduction should use the recorded version. Other base dependencies, including PyYAML, joblib, wrapt, cryptography and toml, came from the existing interpreter. No complete Python environment lockfile was generated, so this record is not a complete dependency closure. Added pydeps files totalled 41,141,294 bytes; no large extensions were compiled.

## Frozen data rules and results

The complete driver records every rule, including 94 ATE, 82 ETT, 20 NDE and 50 NIE questions, a new seed schedule and one new SCM per question. It excludes complete or relevant CPT duplicates against historical metadata, probe8 and previously retained fresh instances. It requires agreement between author labels, independent full-precision calculations and public percentage-precision calculations. Complete proposal and exclusion logs are retained, with public problem statements separated from scoring sidecars.

The 257 proposals produced 246 retained instances and 11 exclusions in 20.671 seconds. Each complete-CPT cell was proposed independently from Uniform(0,1). The final data therefore follow that proposal distribution conditional on the prespecified validity checks. The author's ATE/ETT convention of assigning no to near-zero effects is explicitly recorded, and the original labels were retained.

Generation outputs include `generation_protocol.json`, `manifest.json`, `sampling_attempts.jsonl`, `all_attempt_models.jsonl`, `selected_source_and_validation246.jsonl`, `targets_public.jsonl` and `targets_scoring_only.jsonl`. Subsequently, local `verify246_local.py` performed a second independent recalculation and produced `local_independent_verification.json`. It does not replace the generation driver.

The reproduction package should retain at least the executed driver, `independent_calc.py`, the official source archive and commit, `probe8.json`, and the historical metadata input or its precisely retrievable version. It should also retain the pre-generation protocol, complete sampling logs, selected original models and local recalculation results.
