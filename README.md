# Cortado-Core

![lint workflow](https://github.com/cortado-tool/cortado-core/actions/workflows/lint.yml/badge.svg)
![test workflow](https://github.com/cortado-tool/cortado-core/actions/workflows/test.yml/badge.svg)
![code coverage](https://img.shields.io/codecov/c/gh/cortado-tool/cortado-core?label=Unit%20test%20coverage)

**Cortado-core is a Python library that implements various algorithms and methods for interactive/incremental process discovery.**
Cortado-core is part of the software tool Cortado.

This is a fork of the main repository implementing UNFOLDING-BASED ALIGNMENTS - a work within a Master's thesis on - 'Partial Order-based Alignments via Petri net Unfolding'

It replaces the sequentialization-based conformance checking in Cortado with unfolding-based alignments along with additional features.

Find all the relevant code in `cortado_core/alignments/unfolding/`

## Setup
see https://github.com/cortado-tool/cortado-core?tab=readme-ov-file#setup

## Usage for standalone conformance checking (without having to use the webapp)

To align a model and log, cd to `cortado_core/alignments/unfolding/`, make sure there is a `results/` folder in <directory-path>, and run:

```
python test.py unfolding-based-alignments -p <directory-path> -l <log-name> -m <model-name> -v <variant>
```

- _directory-path_: path to the directory where log file, model file and the `results/` folder reside
- _log-name_: name of the log (.xes)
- _model-name_: name of the model (.pnml)
- _variant_: possible values - 0 or 1 or 2 to run ERV[|>c] (baseline), ERV[|>c] (optimized) or ERV[|>h], respectively.
  
saves results of each alignment to a .csv file in `<directory-path>/results/<model-name>.csv`

Header: ['variant', 'trace_idx', 'trace_length', 'time_taken', 'time_taken_potext', 'queued_events', 'visited_events', 'alignment_costs']

Timeout (in seconds) is adjustable for each single alignment. Change the value at: https://github.com/ariba-work/cortado-core/blob/4c6a9e35d7d0bec71bdff0e579782b2b0cda1840/cortado_core/alignments/unfolding/constants.py#L1

## Script to add noise to an event log

The [following script](https://github.com/ariba-work/cortado-core/blob/main/cortado_core/alignments/unfolding/add_noise.py) adds noise to a given event log from levels of 0-70% in steps of 10%

Specify the correct location of the event log at 
https://github.com/ariba-work/cortado-core/blob/d1ef631132a809687b632cd647f11bbd3045b030/cortado_core/alignments/unfolding/add_noise.py#L127

and run `python add_noise.py` to create 7 log files for each noise level
