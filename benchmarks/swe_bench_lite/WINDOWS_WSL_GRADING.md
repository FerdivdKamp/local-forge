# Grade SWE-bench Lite on this Windows PC (no dual boot)

## Recommendation

Keep LM Studio and the LocalForge model run on Windows. Run only the official
SWE-bench **grading harness** inside the existing Ubuntu WSL 2 distribution,
using Docker Desktop's WSL 2 engine to run the task containers. WSL 2 is a Linux
environment inside Windows; this needs no second boot installation, disk
partition, or switch away from Windows. On this machine, `wsl --status` showed
Ubuntu as the default distribution and WSL version 2. `docker` and `swebench`
were not available when this guide was written, so the gold check has not yet
run. [Docker explains the WSL 2 backend](https://docs.docker.com/desktop/features/wsl/).

The grader can itself live in an outer Docker container, but it creates more
containers for the task tests. That outer container must therefore reach a
Docker daemon, usually via the daemon socket, and mount predictions/output.
This adds setup and security risk without helping the first five cases. Start
with the grader directly in Ubuntu; the task tests are already isolated in
containers by SWE-bench's [official harness](https://github.com/SWE-bench/SWE-bench/blob/main/docs/guides/docker_setup.md).

## 1. Install Docker Desktop on Windows

Use the [official Windows installer](https://docs.docker.com/desktop/setup/install/windows-install/).
Choose the WSL 2 backend and Linux containers. Start Docker Desktop, then in
Settings check **General → Use WSL 2 based engine** (if visible) and
**Resources → WSL Integration → Ubuntu → Apply**. Do **not** separately install
Docker Engine inside Ubuntu when using Docker Desktop integration; Docker
[warns this can conflict](https://docs.docker.com/desktop/features/wsl/).

SWE-bench images need substantial space: its
[Docker guide](https://github.com/SWE-bench/SWE-bench/blob/main/docs/guides/docker_setup.md)
recommends at least 120 GB free and 16 GB RAM. Docker Desktop's WSL data lives
on C: by default; check its data location and free space before building or
pulling images. The first gold run can take time while images are acquired.

In **PowerShell**, open Ubuntu:

```powershell
wsl -d Ubuntu
```

In the resulting **Ubuntu shell**, verify the Docker engine is reachable:

```bash
docker version
docker run --rm hello-world
docker system df
```

If `docker` is missing in Ubuntu, first confirm Docker Desktop is running and
Ubuntu integration is enabled. If Docker is present but cannot reach the daemon,
restart Docker Desktop/Ubuntu integration and retry before installing anything
inside Ubuntu. If `wsl -d Ubuntu` fails, use `wsl -l -v` in PowerShell to check
the actual distribution name.

## 2. Install the official grader in Ubuntu

Use a dedicated Ubuntu virtual environment; do not install the harness into
LocalForge's Windows Poetry environment. These commands follow the
[official SWE-bench quick start](https://github.com/SWE-bench/SWE-bench/blob/main/docs/guides/quickstart.md).

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
mkdir -p ~/src ~/venvs
git clone https://github.com/SWE-bench/SWE-bench.git ~/src/SWE-bench
python3 -m venv ~/venvs/swebench
source ~/venvs/swebench/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ~/src/SWE-bench
swebench eval lite --help
```

Record the SWE-bench Git commit you installed with
`git -C ~/src/SWE-bench rev-parse HEAD`. The install and gold run need internet access
for Python packages, dataset metadata, and container images. Do not run a full
300-case evaluation to test the setup.

## 3. Validate with one gold patch before model grading

Still in Ubuntu with the virtual environment active, grade the reference patch
for one of our [five pinned cases](five.json):

```bash
mkdir -p ~/swe-bench-runs/gold
cd ~/swe-bench-runs/gold
swebench eval lite --gold -i pytest-dev__pytest-9359 --run-id pilot-gold-001 -j 1
python -m json.tool logs/evaluation/pilot-gold-001/results.json
```

Confirm that this one case is **resolved**. If it is unresolved or has an
infrastructure error, inspect its per-instance `run_instance.log` and fix the
grader before testing the model. Use a new `--run-id` for a changed prediction;
the harness can cache a verdict by run ID and instance. The
[CLI reference](https://github.com/SWE-bench/SWE-bench/blob/main/docs/reference/cli.md)
describes `-i`, `-j`, and the results directory.

## 4. Generate predictions on Windows, grade them in Ubuntu

Run the model step on Windows as described in the [pilot README](README.md).
It writes `predictions.jsonl` under the configured `WORKSPACE_ROOT`. With the
default `../workspaces` from this repository, run `pilot-001` produces:

```text
G:\coding_projects\workspaces\run-logs\swe-bench-lite\pilot-001\predictions.jsonl
```

The default WSL mount for G: is `/mnt/g`, so the same file is typically:

```text
/mnt/g/coding_projects/workspaces/run-logs/swe-bench-lite/pilot-001/predictions.jsonl
```

If `WORKSPACE_ROOT` differs, translate its path with `wslpath -u` in Ubuntu.
Check that the source exists before copying. Keep the grader's working directory
and generated logs in Ubuntu's Linux filesystem for simpler paths and better
I/O; the copy below does **not** remove the Windows original:

```bash
source ~/venvs/swebench/bin/activate
mkdir -p ~/swe-bench-runs/pilot-001
cp /mnt/g/coding_projects/workspaces/run-logs/swe-bench-lite/pilot-001/predictions.jsonl ~/swe-bench-runs/pilot-001/predictions.jsonl
cd ~/swe-bench-runs/pilot-001
swebench eval lite -p predictions.jsonl --run-id pilot-001-linux-001 -j 1 \
  -i pytest-dev__pytest-9359 \
  -i matplotlib__matplotlib-25433 \
  -i sympy__sympy-21627 \
  -i django__django-15202 \
  -i pylint-dev__pylint-7114
python -m json.tool logs/evaluation/pilot-001-linux-001/results.json
```

Check the per-instance reports and count resolved cases out of **five**.
LocalForge's `results.json` records whether the agent produced a patch; only
the official harness gives a resolved verdict. Keep the model ID/settings,
manifest SHA, dataset SHA, SWE-bench Git commit, and the harness output together
when comparing models. Do not call a five-case pilot a full Lite benchmark score.

The current `localforge.swe_bench grade` command starts `swebench` in the same
OS where LocalForge runs. Calling it from Windows does **not** move grading into
WSL or a Linux container. Use the Ubuntu commands above until a WSL/container
handoff is implemented in the runner. A
[reported native-Windows line-ending issue](https://github.com/SWE-bench/SWE-bench/issues/652)
is another reason to validate and grade from Linux.

## If you later containerize the grader itself

Use a Linux image with the pinned SWE-bench version, pass in the predictions as
a read-only mount, persist the grader's output, and explicitly provide access
to the Docker daemon so it can create its own task containers. Treat mounting
the Docker socket as granting strong control over the host daemon
([Docker security guidance](https://docs.docker.com/engine/security/)); do not use
an untrusted grader image or expose the Docker API on an unauthenticated TCP
port. For these five cases, direct Ubuntu/WSL grading is the simpler option.
