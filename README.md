# pyvv

欢迎来到 pyvv，这是一个支持 Python 多版本项目。

当前版本采用 **托管 runtime + 多命名 venv** 的混合方案：

1. `pyvv <version>` 先使用系统已有的 `uv` 下载并定位对应 Python；如果找不到，pyvv 会自动在私有目录准备 uv
2. 把完整 Python 运行时复制到 `~/.pyvv/runtimes/<version>/python-home/`
3. 再基于这个私有 runtime 创建一个或多个虚拟环境：
   `~/.pyvv/runtimes/<version>/envs/<name>/`
4. 日常执行、`pip install`、脚本运行都走指定名字的私有 venv
5. 通过 `-n <name>` 或 `--name <name>` 可以在同一个 Python 版本下创建多个环境
6. 如果某个环境损坏，pyvv 会自动重建该环境；如果 runtime 损坏，pyvv 会重建 runtime

## 安装

`pyvv` 要求 Python 3.11 或更高版本。发布到 PyPI 后，使用当前 Python 安装：

```bash
python -m pip install pyvv
pyvv help
```

安装 `pyvv` 本身不会强制安装 uv。第一次执行需要 Python runtime 的命令时，pyvv 会优先复用系统中已有的 uv；如果找不到，再自动将 uv 安装到自己的私有目录。首次自动准备 uv 或下载 Python runtime 需要网络连接。

## 关于 uv

当前版本下载和定位 Python 依赖 `uv` 作为后端。pyvv 会优先复用系统 `PATH` 中已有的 `uv`；如果找不到，则使用当前 Python 在 `~/.pyvv/tools/uv/` 下创建专用虚拟环境并安装 uv，不会直接修改系统 Python。

`pyvv` 在日常使用时并不是简单把环境直接挂在 `uv` 上，而是：

- 先把 Python runtime 复制到自己的目录
- 再基于这个私有 runtime 创建命名虚拟环境

即使后续 uv 的原始 runtime 被清理，`pyvv` 自己托管的环境仍然可以继续使用。

如果系统 Python 没有 `venv` 或 pip 被系统策略限制，pyvv 会继续尝试用户级 pip 安装；如果仍然失败，会显示 pip 的具体错误和手动安装命令。

## 目录结构示例

`pyvv` 会把 uv 工具、Python runtime 和命名虚拟环境分开保存：

```text
~/.pyvv/
├── tools/
│   └── uv/                         # 系统没有 uv 时，pyvv 自动创建的专用环境
│       ├── Scripts/                # Windows：uv.exe、python.exe
│       └── bin/                    # Linux/macOS：uv、python
│
└── runtimes/
    └── 3.14/                      # 一个 Python 版本对应一个独立 runtime
        ├── python-home/           # 从 uv 获取后复制并由 pyvv 托管的完整 Python
        │   ├── python.exe         # Windows
        │   ├── bin/python          # Linux/macOS
        │   ├── Lib/                # Windows 标准库
        │   └── lib/               # Linux/macOS 标准库
        │
        └── envs/                  # 基于 python-home 创建的命名虚拟环境
            ├── default/           # 不指定 --name 时使用
            │   ├── Scripts/       # Windows：python.exe、pip.exe
            │   └── bin/           # Linux/macOS：python、pip
            │
            ├── data/              # pyvv 3.14 -n data
            │   ├── Scripts/       # Windows
            │   └── bin/           # Linux/macOS
            │
            └── web/               # pyvv 3.14 -n web
                ├── Scripts/       # Windows
                └── bin/           # Linux/macOS
```

说明：

- 如果系统 `PATH` 中已经有 uv，pyvv 会直接复用，不会创建 `tools/uv/`。
- `python-home/` 是 pyvv 自己托管的 runtime，删除 uv 的缓存不会影响已经创建的环境。
- `envs/<name>/` 是实际执行 `python`、`pip`、脚本和环境命令的位置。
- `default`、`data`、`web` 只是环境名称，可以按项目需要创建多个。

## 常用示例

```text
pyvv 3.14
pyvv 3.14 -n data
pyvv 3.14 --name data pip list
pyvv 3.14 -n web pip install fastapi
pyvv 3.14 -n web hello.py
pyvv 3.14 -n web -m http.server
pyvv remove 3.14 -n data
```

如果你要运行像 `ipython` 这样的环境命令，先安装对应包：

```text
pyvv 3.14 -n web pip install ipython
pyvv 3.14 -n web ipython
```

## 说明

- 不写 `-n/--name` 时，默认环境名是 `default`
- 只有删除某个版本下最后一个环境时，pyvv 才会顺带清理该版本的 runtime
- pyvv 会自动判断你要执行的是 pip、Python 参数、Python 脚本还是环境命令

## 命令列表

```text
【pyvv help】                          查看帮助
【pyvv list】                          查看已安装/可安装的 Python 版本
【pyvv mirror】                        给全局 pip 设置清华镜像源
【pyvv 3.14】                          进入 Python3.14 默认环境
【pyvv 3.14 -n data】                  进入 Python3.14 的 data 环境
【pyvv 3.14 --name data pip list】     在指定环境运行 pip 命令
【pyvv 3.14 hello.py】                 通过当前环境运行脚本 hello.py
【pyvv 3.14 -m http.server】           直接传递给 Python 自身参数
【pyvv remove 3.14】                   删除 Python3.14 的默认环境
【pyvv remove 3.14 -n data】           删除 Python3.14 的 data 环境
```
