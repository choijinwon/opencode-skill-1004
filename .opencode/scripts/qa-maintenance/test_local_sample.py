import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = ROOT / "samples"
SAMPLE_PATHS = {
    "sklearn": "sklearn_sample",
    "pytorch": "pytorch_sample",
    "tensorflow": "tensorflow_sample",
}
DEFAULT_SAMPLES = list(SAMPLE_PATHS)


def python_in_venv(venv_dir: Path) -> Path:
    # Windows and POSIX virtual environments place the Python executable in
    # different folders. Keep the path logic here so the rest of the script is
    # platform-neutral.
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run(cmd, cwd: Path):
    print(f"[run] cwd=. cmd={' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def interpreter_version(python_bin: Path) -> str:
    result = subprocess.run(
        [str(python_bin), "-c", "import platform; print(platform.python_version())"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def ensure_venv(sample_dir: Path, rebuild: bool, base_python: Path) -> Path:
    venv_dir = sample_dir / ".venv"
    # Rebuild is useful when validating a clean Windows 10/11 setup or after
    # changing sample requirements.
    if rebuild and venv_dir.exists():
        shutil.rmtree(venv_dir)
    if not venv_dir.exists():
        print(f"[info] create venv: {venv_dir}")
        run([str(base_python), "-m", "venv", str(venv_dir)], cwd=sample_dir)
    return python_in_venv(venv_dir)


def install_requirements(python_bin: Path, sample_dir: Path):
    run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], cwd=sample_dir)
    run([str(python_bin), "-m", "pip", "install", "-r", "requirements.txt"], cwd=sample_dir)


def test_sample(sample_name: str, rebuild: bool, do_install: bool, do_register: bool, base_python: Path):
    sample_dir = SAMPLES_DIR / SAMPLE_PATHS[sample_name]
    if not sample_dir.exists():
        raise FileNotFoundError(f"unknown sample: {sample_name}")

    python_bin = ensure_venv(sample_dir, rebuild=rebuild, base_python=base_python)
    if do_install:
        install_requirements(python_bin, sample_dir)

    # runtest.py is preferred when present. Bundled samples otherwise expose
    # run_model.py as the local prepare/export entrypoint.
    if (sample_dir / "train.py").exists():
        run([str(python_bin), "train.py"], cwd=sample_dir)
    if (sample_dir / "register_model.py").exists():
        run([str(python_bin), "register_model.py", "--prepare-only"], cwd=sample_dir)
    if (sample_dir / "runtest.py").exists():
        run([str(python_bin), "runtest.py"], cwd=sample_dir)
    elif (sample_dir / "run_model.py").exists():
        run([str(python_bin), "run_model.py", "--prepare-only"], cwd=sample_dir)
    else:
        raise FileNotFoundError(f"missing runtest.py or run_model.py: {sample_dir}")

    # Full registration is optional because each user may have different local
    # or remote MLflow tracking settings.
    if do_register:
        if (sample_dir / "register_model.py").exists():
            run([str(python_bin), "register_model.py"], cwd=sample_dir)
        elif (sample_dir / "runtest.py").exists():
            run([str(python_bin), "runtest.py"], cwd=sample_dir)
        else:
            run([str(python_bin), "run_model.py"], cwd=sample_dir)


def main():
    parser = argparse.ArgumentParser(description="Run local sample checks")
    parser.add_argument(
        "--sample",
        choices=DEFAULT_SAMPLES + ["all"],
        default="all",
        help="sample project to test",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="skip pip install and reuse the existing venv",
    )
    parser.add_argument(
        "--rebuild-venv",
        action="store_true",
        help="recreate .venv before testing",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="run the MLflow registration example after prepare-only",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="base Python interpreter used to create the sample virtual environment",
    )
    args = parser.parse_args()

    base_python = Path(args.python).resolve()
    if not base_python.exists():
        raise FileNotFoundError(f"python interpreter not found: {base_python}")

    version = interpreter_version(base_python)
    if version != "3.11.9":
        raise RuntimeError(
            f"python {version} is not supported for this sample set. "
            "Use Python 3.11.9 with --python."
        )

    targets = DEFAULT_SAMPLES if args.sample == "all" else [args.sample]
    for sample_name in targets:
        print(f"[info] test sample: {sample_name}")
        test_sample(
            sample_name=sample_name,
            rebuild=args.rebuild_venv,
            do_install=not args.skip_install,
            do_register=args.register,
            base_python=base_python,
        )
    print("[done] local sample checks completed")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"[error] command failed with exit code {exc.returncode}", file=sys.stderr)
        sys.exit(exc.returncode)
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
