# expbox

*A lightweight, local-first experiment box for Python.*

`expbox` gives each experiment its own **box** — a directory like `results/<exp_id>/` — and a small Python API to manage configs, logs, and metadata in a uniform way across scripts, notebooks, and projects.

---

## Features

- **Minimal API**

  ```python
  import expbox as xb

  ctx = xb.init(...)   # start new experiment
  ctx = xb.load(...)   # reload existing experiment
  xb.save(ctx)         # finalize and record metadata
    ````

* **Local-first structure**

  Every experiment lives under:

  ```text
  results/<exp_id>/
    meta.json         # metadata (source of truth)
    artifacts/        # config snapshot, models, tables
    figures/          # plots, visualizations
    logs/             # metrics.jsonl, logs
    notebooks/        # optional experiment-specific notebooks
  ```

* **Flexible experiment IDs**

  * datetime-based (`YYMMDD-HHMM` by default)
  * sequential (`proj-01`, `proj-02`, …)
  * random IDs
  * custom patterns via user-defined generator
  * `kebab` (`-`) or `snake` (`_`) linking of parts

* **Pluggable logging backends**

  * `none`: no logging, but unified interface
  * `file`: local JSONL + PNG
  * `wandb`: optional Weights & Biases integration

* **Tool-agnostic integration**

  * `meta.json` is designed as the single source of truth
  * easy to sync into PKM tools (e.g. Notion, Obsidian)
  * easy to connect to experiment trackers (e.g. W&B, MLflow) via URLs inside `meta.extra`

* **Distributed & HPC-ready**

  * Safe for multi-GPU / multi-node environments (DDP / MPI / SLURM)
  * Standard rank-0 logging pattern — only rank 0 writes logs and metadata
  * No special dependencies; works on NFS / Lustre / GPFS / local SSD
  * Easy to redirect `results_root` to cluster storage (e.g. `$SCRATCH`)

---

## Philosophy

`expbox` is built around three ideas:

1. **1 experiment = 1 directory**

   All files for a run — config snapshot, logs, figures, notebooks — are under `results/<exp_id>/`. You can zip that directory and have everything you need to reproduce.

2. **Context object, not framework**

   User code receives a single `ExpContext`:

   ```python
   ctx.exp_id
   ctx.paths   # root, artifacts, logs, figures, notebooks
   ctx.config  # dict-like config
   ctx.meta    # ExperimentMeta
   ctx.logger  # logger backend
   ```

   This keeps your training / analysis code independent of expbox internals.

3. **Optional integrations, never mandatory**

   * You can stay purely local.
   * You can enable W&B with a flag.
   * You can mirror `meta.json` into Notion for human-friendly tracking.
   * None of these integrations are required for `expbox` to be useful.

---

## Installation

Minimal installation (Python ≥ 3.9):

```bash
pip install expbox
```

Optional extras:

```bash
# YAML config support
pip install "expbox[yaml]"

# W&B logger support
pip install "expbox[wandb]"
```

---

## Quick Start
### 0. Project layout & where to call `init`

The recommended layout is:

```text
workspace/
  project_x/
    src/
    configs/
    results/      # created automatically by expbox (default)
  project_y/
    ...
```

You typically:

* **run your scripts / notebooks from each project’s top directory**, e.g. `workspace/project_x`
* call `xb.init(...)` inside code that is executed in that project
* by default, `results_root="results"` is **relative to the current working directory**, so:

  * if you run from `workspace/project_x`, you get `workspace/project_x/results/...`
  * if you prefer a shared results area, you can set `results_root` explicitly, e.g. `results_root="../shared_results"`.

This makes it easy to keep experiments **project-local** by default, while still allowing custom layouts when needed.

---


### 1. Basic usage

**Note:**  
If you run distributed training (DDP / MPI / SLURM),  
use `expbox` only on **rank 0**.  
See the FAQ section for a full example and recommended patterns.


```python
import expbox as xb

# Start a new experiment
ctx = xb.init(
    project="DrugScreen",
    title="SSL baseline",
    purpose="Check KD effect in liver slides",
    config="configs/ssl.yaml",   # dict / JSON / YAML
    logger="file",               # "none" / "file" / "wandb"
)

# Use in your training loop
for step in range(100):
    loss = 0.1 * step
    ctx.logger.log_metrics({"loss": loss}, step=step)

# Save a figure
import matplotlib.pyplot as plt

fig = plt.figure()
plt.plot([1, 2, 3], [3, 2, 1])
ctx.logger.log_figure(fig, "example_plot")

# Final notes and finalize
ctx.meta.env_note = "colab pro+"
ctx.meta.final_note = "works; next: try lr=1e-4"
xb.save(ctx)
```

This creates a structure like:

```text
results/
  250124-1530/
    meta.json
    artifacts/config.yaml
    logs/metrics.jsonl
    logs/example_plot.png
    figures/
    notebooks/
```

---

### 2. Using W&B as the logger backend

```python
import expbox as xb

ctx = xb.init(
    project="DrugScreen",
    config={"lr": 1e-3},
    logger="wandb",
)

# Training loop
for step in range(50):
    loss = 0.05 * step
    ctx.logger.log_metrics({"loss": loss}, step=step)

# Optionally record the W&B URL into meta.extra
ctx.meta.extra["wandb_url"] = ctx.logger.run.url
xb.save(ctx)
```

You now have:

* Local experiment structure in `results/<exp_id>/`
* A W&B run tracking the same metrics and figures
* The W&B URL recorded in `meta.json`

---

### 3. Recording the experiment in Notion

After the run, you can sync `meta.json` into a Notion database.

```python
import json
from notion_client import Client
import expbox as xb

# Reload context if needed
ctx = xb.load(exp_id="250124-1530")
meta_path = ctx.paths.root / "meta.json"
meta = json.load(open(meta_path, encoding="utf-8"))

summary = {
    "exp_id": meta["exp_id"],
    "project": meta["project"],
    "title": meta.get("title"),
    "purpose": meta.get("purpose"),
    "created_at": meta["created_at"],
    "finished_at": meta.get("finished_at"),
    "results_path": str(ctx.paths.root),
    "config_path": str(ctx.paths.artifacts / "config.yaml"),
    "wandb_url": meta.get("extra", {}).get("wandb_url"),
}

notion = Client(auth=NOTION_API_TOKEN)

notion.pages.create(
    parent={"database_id": NOTION_DB_ID},
    properties={
        "Experiment ID": {"title": [{"text": {"content": summary["exp_id"]}}]},
        "Project": {"rich_text": [{"text": {"content": summary["project"]}}]},
        "Title": {"rich_text": [{"text": {"content": summary["title"] or ''}}]},
        "Purpose": {"rich_text": [{"text": {"content": summary["purpose"] or ''}}]},
        "Created": {"date": {"start": summary["created_at"]}},
        "Finished": {"date": {"start": summary["finished_at"]}} if summary["finished_at"] else None,
        "Results Path": {"url": summary["results_path"]},
        "Config": {"url": summary["config_path"]},
        "WandB": {"url": summary["wandb_url"]} if summary["wandb_url"] else None,
    },
)
```

This lets you browse experiments in Notion while keeping `expbox` as the technical source of truth.

---

## FAQ

### Q: Why not just use MLflow?

MLflow is powerful but relatively heavy.
`expbox` is deliberately small:

* no servers, databases, or UIs
* just directories, JSON/YAML, and a tiny API

You can still add MLflow on top if you want.

---

### Q: Does this replace W&B?

No. `expbox` treats W&B as an **optional backend**:

* if `logger="wandb"` → metrics/figures go to W&B
* if `logger="file"`  → metrics/figures go to local files
* if `logger="none"`  → no logging, but your code does not change

---

### Q: Is this suitable for notebooks?

Yes. That’s one of the main use-cases:

```python
import expbox as xb
ctx = xb.init(project="NotebookDemo")
# … run cells …
xb.save(ctx)
```

You always know where outputs go (`results/<exp_id>/`), and you can paste the `exp_id` into Notion or W&B.

---

### Q: How do I customize `exp_id`?

* datetime-based (default):

  ```python
  ctx = xb.init(project="MyProj")
  # exp_id: "250124-1530"
  ```

* with prefix/suffix:

  ```python
  ctx = xb.init(
      project="MyProj",
      prefix="rbc",
      suffix="v1",
      link_style="snake",
  )
  # exp_id: "rbc_250124-1530_v1"
  ```

* sequential:

  ```python
  ctx = xb.init(project="MyProj", id_style="seq")
  # exp_id: "myproj-01", then "myproj-02", ...
  ```

* fully custom:

  ```python
  def my_id(project, root):
      return "mouseA_kidney_01"

  ctx = xb.init(project="MyProj", id_generator=my_id)
  ```

---


### Q: Can I use expbox in distributed training on HPC clusters (DDP / MPI / SLURM)?

Yes — expbox works well in HPC and distributed environments.  
The recommended pattern is the same as used by most modern ML frameworks:

**Only rank 0 uses expbox (init / log / save).**  
Other ranks do not create or write experiment files.

This avoids file-write contention on HPC filesystems (NFS / Lustre / GPFS).

#### Example (generic DDP / MPI / SLURM)

```python
import os
from pathlib import Path
import expbox as xb

# Detect rank from common env vars (MPI, PyTorch DDP, SLURM)
rank = int(
    os.environ.get("OMPI_COMM_WORLD_RANK",
    os.environ.get("PMI_RANK",
    os.environ.get("RANK", 0)))
)

# Choose a results directory (local or HPC storage)
RESULTS_ROOT = Path(os.environ.get("SCRATCH_RESULTS", "./results"))

# Initialize expbox only on rank 0
if rank == 0:
    ctx = xb.init(
        project="MyProj",
        config="configs/train.yaml",
        logger="file",        # or "wandb"
        results_root=RESULTS_ROOT,
    )
else:
    ctx = None

# Training loop
for step in range(num_steps):
    loss = compute_loss(...)
    if rank == 0 and ctx is not None:
        ctx.logger.log_metrics({"loss": float(loss)}, step=step)

# Finalize
if rank == 0 and ctx is not None:
    ctx.meta.env_note = f"HPC job {os.environ.get('SLURM_JOB_ID', '')}"
    xb.save(ctx)

```

---

## License

`expbox` is released under the **MIT License**. See `LICENSE` for details.


## Authors
- [Tadahaya Mizuno](https://github.com/tadahayamiz)  
    - correspondence  

## Contact
If you have any questions or comments, please feel free to create an issue on github here, or email us:  
- tadahaya[at]gmail.com  
    - lead contact  