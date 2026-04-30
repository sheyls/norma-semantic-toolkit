This folder contains a lightweight way to test the generated SWRL rules without Protégé.

Use:

```bash
python3 test/run_swrl_cases.py
```

What it does:

- loads `regulations/eu-ai-act/eu-ai-act.swrl.owl`
- reads scenario facts from `test/eu_ai_act_cases.json`
- evaluates the exported SWRL fragment used by this repo
- reports which trigger events and norms activate for each case

Important limitation:

- this is not a full SWRL reasoner
- it supports the rule pattern currently emitted by `norma_engine.exporters.swrl`
- if the exported SWRL shape changes, the runner should be updated too

Why this is still useful:

- it gives a fast, local equivalent of the practical Protégé workflow
- it makes the expected legal outcomes explicit as repeatable test cases
- it warns if the SWRL file contains duplicate rule IRIs, which your current EU AI Act rules file does
