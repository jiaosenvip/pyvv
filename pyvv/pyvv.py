import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from rich import print
from rich.tree import Tree


def load_version_list() -> list[str]:
    result = subprocess.run(
        ["uv", "python", "list", "--only-downloads", "--output-format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "uv python list failed")
    return [
        f"{item['version_parts']['major']}.{item['version_parts']['minor']}{'t' if item['variant'] == 'freethreaded' else ''}"
        for item in json.loads(result.stdout)
        if item.get("implementation") == "cpython"
    ]


VERSION_LIST = load_version_list()
PYVV_HOME = Path.home() / ".pyvv"
RUNTIME_DIR = PYVV_HOME / "runtimes"
DEFAULT_ENV_NAME = "default"
PIP_INDEX_URL = "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
PYTHON_FLAG_PREFIXES = ("-",)
if os.name == "nt":
    TEMP_DIR = Path.home() / "AppData/Local/Temp"
else:
    TEMP_DIR = Path("/tmp")

for directory in (PYVV_HOME, RUNTIME_DIR):
    directory.mkdir(parents=True, exist_ok=True)

HELP_STR = """
[red]欢迎来到 pyvv[/]

说明：

  - 当前版本下载和定位 Python 仍依赖 uv 作为后端
  - 不写 -n/--name 时，默认环境名是 default
  - pyvv 会自动判断你要执行的是 pip、Python 参数、Python 脚本还是环境命令
  - pyvv mirror 会给全局 pip 设置清华镜像源，需要用户主动执行才会生效

命令列表示例:

  [green]【pyvv help】[/green]                             查看帮助
  [green]【pyvv list】[/green]                             查看已安装/可安装
  [green]【pyvv mirror】[/green]                           给全局 pip 设置清华镜像源
  [green]【pyvv 3.14】[/green]                             进入 Python3.14 默认环境
  [green]【pyvv 3.14 -n data】[/green]                     进入 Python3.14 的 data 环境
  [green]【pyvv 3.14 --name data pip list】[/green]        在指定环境运行 pip 命令
  [green]【pyvv 3.14 hello.py】[/green]                    通过当前环境运行脚本 hello.py
  [green]【pyvv 3.14 -m http.server】[/green]              直接传递给 Python 自身参数
  [green]【pyvv 3.14 -n web pip install ipython】[/green]  安装 ipython
  [green]【pyvv 3.14 -n web ipython】[/green]              运行环境里的 ipython 命令
  [green]【pyvv remove 3.14】[/green]                      删除 Python3.14 的默认环境
  [green]【pyvv remove 3.14 -n data】[/green]              删除 Python3.14 的 data 环境
"""


def normalize_env_name(name: str | None) -> str:
    if not name:
        return DEFAULT_ENV_NAME
    env_name = name.strip()
    if not env_name:
        return DEFAULT_ENV_NAME
    if env_name in {".", ".."}:
        raise ValueError("环境名称不能是 . 或 ..")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", env_name):
        raise ValueError("环境名称只能包含字母、数字、点、下划线和中划线")
    return env_name


def split_name_args(args: list[str]) -> tuple[str, list[str]]:
    env_name = DEFAULT_ENV_NAME
    remaining: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"-n", "--name"}:
            if i + 1 >= len(args):
                raise ValueError(f"{arg} 后面必须跟环境名称")
            env_name = normalize_env_name(args[i + 1])
            i += 2
            continue
        remaining.append(arg)
        i += 1
    return env_name, remaining


def env_label(env_name: str) -> str:
    return "默认环境" if env_name == DEFAULT_ENV_NAME else f"{env_name} 环境"


def get_runtime_dir(version: str) -> Path:
    return RUNTIME_DIR / version


def get_python_home(version: str) -> Path:
    return get_runtime_dir(version) / "python-home"


def get_envs_dir(version: str) -> Path:
    return get_runtime_dir(version) / "envs"


def get_env_dir(version: str, env_name: str = DEFAULT_ENV_NAME) -> Path:
    return get_envs_dir(version) / normalize_env_name(env_name)


def get_script_dir(version: str, env_name: str = DEFAULT_ENV_NAME) -> Path:
    env_dir = get_env_dir(version, env_name)
    return env_dir / ("Scripts" if os.name == "nt" else "bin")


def get_python_path(version: str, env_name: str = DEFAULT_ENV_NAME) -> Path:
    script_dir = get_script_dir(version, env_name)
    return script_dir / ("python.exe" if os.name == "nt" else "python")


def get_runtime_python_path(version: str) -> Path:
    python_home = get_python_home(version)
    return python_home / ("python.exe" if os.name == "nt" else "bin/python")


def resolve_env_command(version: str, env_name: str, command_name: str) -> Path | None:
    script_dir = get_script_dir(version, env_name)
    candidates = [command_name]
    if os.name == "nt":
        lowered = command_name.lower()
        if not lowered.endswith((".exe", ".bat", ".cmd", ".ps1")):
            candidates.extend(
                [
                    f"{command_name}.exe",
                    f"{command_name}.bat",
                    f"{command_name}.cmd",
                    f"{command_name}.ps1",
                ]
            )
    for candidate in candidates:
        candidate_path = script_dir / candidate
        if candidate_path.exists():
            return candidate_path
    return None


def run_command(command: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, text=True)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except FileNotFoundError as exc:
        missing = command[0] if command else "<unknown>"
        print(f"[red]命令不存在或未安装: {missing}[/]")
        print(
            "[yellow]如果这是 Python 包提供的命令，请先在当前环境中安装对应包，例如：[/]"
        )
        print("[yellow]pyvv <version> -n <name> pip install <package>[/]")
        print(f"[dim]{exc}[/dim]")
        raise SystemExit(1)


def is_python_healthy(python_path: Path) -> bool:
    if not python_path.exists():
        return False
    try:
        result = subprocess.run(
            [str(python_path), "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_python_version(python_path: Path) -> str | None:
    if not python_path.exists():
        return None
    try:
        result = subprocess.run(
            [
                str(python_path),
                "-c",
                "import platform; print(platform.python_version())",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        version = result.stdout.strip()
        return version or None
    except Exception:
        return None


def ensure_uv_python(version: str) -> str:
    install = subprocess.run(
        ["uv", "python", "install", version, "--managed-python"],
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        raise RuntimeError(
            install.stderr or install.stdout or f"uv python install {version} failed"
        )

    found = subprocess.run(
        ["uv", "python", "find", version, "--managed-python"],
        capture_output=True,
        text=True,
    )
    if found.returncode != 0:
        raise RuntimeError(
            found.stderr or found.stdout or f"uv python find {version} failed"
        )

    python_path = found.stdout.strip()
    if not python_path:
        raise RuntimeError(f"uv python find {version} returned empty path")
    return python_path


def copy_runtime_home(version: str, destination: Path) -> None:
    uv_python_path = Path(ensure_uv_python(version))
    source_home = uv_python_path.parent
    if os.name != "nt" and source_home.name == "bin":
        source_home = source_home.parent
    if not source_home.exists():
        raise RuntimeError(f"找不到 uv 管理的 Python 目录: {source_home}")
    shutil.copytree(source_home, destination, dirs_exist_ok=True)


def create_env_from_runtime(version: str, python_home: Path, env_dir: Path) -> None:
    runtime_python = python_home / ("python.exe" if os.name == "nt" else "bin/python")
    if not runtime_python.exists():
        raise RuntimeError(f"找不到托管运行时解释器: {runtime_python}")
    result = subprocess.run(
        [str(runtime_python), "-m", "venv", str(env_dir), "--copies"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr or result.stdout or f"创建虚拟环境失败: {env_dir}"
        )

    env_python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pip_check = subprocess.run(
        [str(env_python), "-m", "pip", "--version"],
        capture_output=True,
        text=True,
    )
    if pip_check.returncode != 0:
        detail = pip_check.stderr or pip_check.stdout or "pip 不可用"
        raise RuntimeError(
            f"python{version} 新环境创建成功，但 pip 不可用。当前 runtime 可能缺少 ensurepip。\n{detail}"
        )


def create_managed_runtime(version: str, runtime_dir: Path) -> bool:
    temp_dir = runtime_dir.with_name(f".{runtime_dir.name}.tmp-{time.time_ns()}")
    try:
        print(f"python{version} runtime installing...")
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        python_home = temp_dir / "python-home"
        copy_runtime_home(version, python_home)

        if runtime_dir.exists():
            shutil.rmtree(runtime_dir, ignore_errors=True)
        temp_dir.replace(runtime_dir)

        runtime_python = get_runtime_python_path(version)
        if not is_python_healthy(runtime_python):
            raise RuntimeError(f"python{version} runtime 健康检查失败")

        print(f"python{version} runtime installed")
        return True
    except Exception as exc:
        if runtime_dir.exists() and not is_python_healthy(
            get_runtime_python_path(version)
        ):
            shutil.rmtree(runtime_dir, ignore_errors=True)
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"[red]{exc}[/]")
        print(f"python{version} runtime installing failed.")
        return False


def ensure_runtime_home(version: str) -> bool:
    runtime_dir = get_runtime_dir(version)
    runtime_python = get_runtime_python_path(version)
    if is_python_healthy(runtime_python):
        return True

    if runtime_dir.exists():
        print(f"python{version} runtime is broken, recreating...")
        shutil.rmtree(runtime_dir, ignore_errors=True)
    return create_managed_runtime(version, runtime_dir)


def ensure_named_env(version: str, env_name: str) -> bool:
    env_name = normalize_env_name(env_name)
    if not ensure_runtime_home(version):
        return False

    env_dir = get_env_dir(version, env_name)
    env_python = get_python_path(version, env_name)
    if is_python_healthy(env_python):
        return True

    if env_dir.exists():
        print(f"python{version} {env_label(env_name)}已损坏，正在重建...")
        shutil.rmtree(env_dir, ignore_errors=True)

    print(f"python{version} {env_label(env_name)} installing...")
    try:
        env_dir.parent.mkdir(parents=True, exist_ok=True)
        create_env_from_runtime(version, get_python_home(version), env_dir)
        if not is_python_healthy(env_python):
            raise RuntimeError(f"python{version} {env_label(env_name)}健康检查失败")
        print(f"python{version} {env_label(env_name)} installed")
        return True
    except Exception as exc:
        if env_dir.exists():
            shutil.rmtree(env_dir, ignore_errors=True)
        print(f"[red]{exc}[/]")
        print(f"python{version} {env_label(env_name)} installing failed.")
        return False


def list_versions() -> None:
    tree = Tree("[bold cyan]Python 环境[/bold cyan]")
    for version in VERSION_LIST:
        runtime_dir = get_runtime_dir(version)
        runtime_python = get_runtime_python_path(version)
        envs_dir = get_envs_dir(version)
        runtime_ok = is_python_healthy(runtime_python)
        runtime_version = get_python_version(runtime_python)

        env_names: list[str] = []
        if envs_dir.exists():
            env_names = sorted(
                path.name for path in envs_dir.iterdir() if path.is_dir()
            )

        if not runtime_dir.exists() and not env_names:
            tree.add(f"[dim]{version}[/dim] [red](未安装)[/red]")
            continue

        if runtime_ok:
            display_version = runtime_version or "unknown"
            version_node = tree.add(
                f"[green]{version}[/green] [green]({display_version} 正常)[/green]"
            )
        else:
            display_version = runtime_version or "runtime"
            version_node = tree.add(
                f"[yellow]{version}[/yellow] [yellow]({display_version} 损坏或缺失)[/yellow]"
            )

        if not env_names:
            version_node.add("[dim]无环境[/dim]")
            continue

        for env_name in env_names:
            env_python = get_python_path(version, env_name)
            env_ok = is_python_healthy(env_python)
            env_display = "default (默认)" if env_name == DEFAULT_ENV_NAME else env_name
            if env_ok:
                version_node.add(f"[green]{env_display}[/green]")
            else:
                version_node.add(
                    f"[yellow]{env_display}[/yellow] [yellow]（损坏）[/yellow]"
                )
    print(tree)


def remove_version(version: str, env_name: str = DEFAULT_ENV_NAME) -> None:
    env_name = normalize_env_name(env_name)
    runtime_dir = get_runtime_dir(version)
    env_dir = get_env_dir(version, env_name)
    if not env_dir.exists():
        print(f"Python{version} 的 {env_label(env_name)}不存在")
        return

    target = TEMP_DIR / f"{version}-{env_name}-{time.time():.0f}"
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    shutil.move(str(env_dir), str(target))

    envs_dir = get_envs_dir(version)
    remaining_envs = (
        [path for path in envs_dir.iterdir() if path.is_dir()]
        if envs_dir.exists()
        else []
    )
    if not remaining_envs:
        runtime_target = TEMP_DIR / f"{version}-runtime-{time.time():.0f}"
        if runtime_target.exists():
            shutil.rmtree(runtime_target, ignore_errors=True)
        shutil.move(str(runtime_dir), str(runtime_target))
        print(f"[green]{version} 的 {env_label(env_name)}已删除，同时清理了 runtime[/]")
        return

    print(f"[green]{version} 的 {env_label(env_name)}已删除[/]")


def set_global_pip_mirror() -> int:
    print("将给全局 pip 设置清华镜像源。")
    print("这会修改当前用户的 pip 默认配置。")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "config",
            "set",
            "global.index-url",
            PIP_INDEX_URL,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"[red]{result.stderr}[/]")
        print("[red]设置全局 pip 清华镜像源失败[/]")
        return 1

    verify = subprocess.run(
        [sys.executable, "-m", "pip", "config", "get", "global.index-url"],
        capture_output=True,
        text=True,
    )
    if verify.returncode != 0:
        if verify.stdout:
            print(verify.stdout)
        if verify.stderr:
            print(f"[red]{verify.stderr}[/]")
        print("[red]已写入配置，但读取验证失败[/]")
        return 1

    print(f"[green]已给全局 pip 设置清华镜像源：{verify.stdout.strip()}[/]")
    return 0


def is_python_style_argument(arg: str) -> bool:
    return arg.startswith(PYTHON_FLAG_PREFIXES)


def is_python_script_argument(arg: str) -> bool:
    lowered = arg.lower()
    return lowered.endswith(".py") or lowered.endswith(".pyw")


def print_unknown_command(version: str, env_name: str, command_name: str) -> int:
    print(f"[red]无法识别命令: {command_name}[/]")
    print(f"[yellow]当前环境: Python {version} / {env_label(env_name)}[/]")
    print("[yellow]已尝试按以下方式解析：Python 参数、Python 脚本、环境内可执行命令[/]")
    print("[yellow]如果这是环境命令，请先安装对应包，例如：[/]")
    print(f"[yellow]pyvv {version} -n {env_name} pip install <package>[/]")
    return 1


def print_activate_help(version: str, env_name: str) -> int:
    env_name = normalize_env_name(env_name)
    env_dir = get_env_dir(version, env_name)

    print("[yellow]activate 暂时无法直接运行，请手动运行下面命令激活环境。[/]\n")

    if os.name == "nt":
        activate_bat = env_dir / "Scripts" / "activate.bat"
        activate_ps1 = env_dir / "Scripts" / "Activate.ps1"
        activate_sh = env_dir / "Scripts" / "activate"
        print(f'PowerShell: [green]\n    & "{activate_ps1}"[/]')
        print(f"cmd: [green]\n    {activate_bat}[/]")
        print(f"bash: [green]\n    source {activate_sh}[/]")
        return 0

    activate_path = env_dir / "bin" / "activate"
    print(f"[green]source {activate_path}[/]")
    return 0


def run_python(version: str, args: list[str], env_name: str = DEFAULT_ENV_NAME) -> int:
    env_name = normalize_env_name(env_name)
    if not ensure_named_env(version, env_name):
        return 1

    python_path = get_python_path(version, env_name)
    if not args:
        try:
            return run_command([str(python_path)]).returncode
        except KeyboardInterrupt:
            return 0

    first_arg = args[0]
    if first_arg == "activate":
        return print_activate_help(version, env_name)
    if first_arg in {"pip", "pip.exe", "pip3", "pip3.exe"}:
        return run_command([str(python_path), "-m", "pip", *args[1:]]).returncode

    if is_python_style_argument(first_arg):
        return run_command([str(python_path), *args]).returncode

    if is_python_script_argument(first_arg):
        return run_command([str(python_path), *args]).returncode

    command_path = resolve_env_command(version, env_name, first_arg)
    if command_path is not None:
        return run_command([str(command_path), *args[1:]]).returncode

    candidate_path = Path(first_arg)
    if candidate_path.exists() and candidate_path.is_file():
        return run_command([str(python_path), *args]).returncode

    return print_unknown_command(version, env_name, first_arg)


def main() -> None:
    args = sys.argv
    if len(args) == 1:
        print(HELP_STR)
        return

    command = args[1]
    if command in VERSION_LIST:
        try:
            env_name, remaining_args = split_name_args(args[2:])
        except ValueError as exc:
            print(f"[red]{exc}[/]")
            return
        raise SystemExit(run_python(command, remaining_args, env_name))
    if command == "list":
        list_versions()
        return
    if command == "mirror":
        raise SystemExit(set_global_pip_mirror())
    if command in {"help", "--help", "-h"}:
        print(HELP_STR)
        return
    if command == "remove":
        if len(args) <= 2:
            print(HELP_STR)
            return
        version = args[2]
        if version not in VERSION_LIST:
            print(f"[red]只能删除支持的版本号 {VERSION_LIST}[/]")
            return
        try:
            env_name, remaining_args = split_name_args(args[3:])
        except ValueError as exc:
            print(f"[red]{exc}[/]")
            return
        if remaining_args:
            print(f"[red]remove 不支持额外参数: {remaining_args}[/]")
            return
        remove_version(version, env_name)
        return

    print(f"支持的Python版本有 {VERSION_LIST}")
