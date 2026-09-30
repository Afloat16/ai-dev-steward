# StewardCheck

**保持编码节奏，看清每次改动。**

[English](README.md) | **简体中文**

StewardCheck 是面向 LLM 编程与 vibecoding 的轻量本地命令行工具：记录任务开始时的真实工作区，整理有容量限制的上下文，并生成“改了什么、检查了什么、结果是否仍然有效”的验收记录。

它补充现有编辑器或编程助手，不另造一个完整代理。无需模型账号、API Key、服务器或第三方 Python 运行时依赖，也不会自动修改源码。

**0.2.0 · Alpha · Python 3.11+ · Git · MIT**

## 解决什么问题

测试命令成功，并不代表任务边界没有被突破。是否改了无关文件？是否删掉断言让测试变绿？测试完成后代码是否又变了？任务开始前是否已有你自己的未提交改动？

| 需求 | 实际行为 |
| --- | --- |
| 控制改动范围 | 声明允许修改的路径、受保护路径及修改文件数量上限。 |
| 保留已有工作 | 以任务开始时的工作区为基线，包含已有未提交内容与未忽略的未跟踪文件，而非仅比较 HEAD；不自动回滚。 |
| 传递必要上下文 | 输出有严格字节预算的完整文件 Markdown，排除敏感文件名并进行启发式脱敏。 |
| 留下可复查依据 | 只有明确使用 `check --run` 才运行任务开始时声明的命令，结果绑定工作区、暂存区与 HEAD 指纹。 |
| 避免过期结论 | 检测检查期间和检查之后的状态变化；没有运行检查或存在复核警告时不会显示通过。 |
| 发现常见风险 | 新出现的疑似凭据、测试删除、断言标记减少、跳过测试标记增加、部分暂存等。 |

这是**工作区任务验收**，不是仅检查暂存区的提交钩子、语义正确性证明、安全沙箱、备份工具或安全认证。

## 复用任务配置（0.2.0）

需要重复使用范围和检查命令时，可以在被检查项目根目录维护一份经过审阅的 `.stewardcheck.toml`，不必为每个任务创建新配置：

```toml
schema = 1
scope = ["src/**", "tests/**"]
checks = [["python", "-m", "unittest", "discover", "-s", "tests"]]
max_files = 12
timeout = 120
```

```sh
stewardcheck start "修复空输入处理" --config .stewardcheck.toml
stewardcheck packet
# 审阅改动和已声明命令后，才显式执行。
stewardcheck check --run
```

**不会自动发现或加载配置。** 相对路径始终相对于 Git 仓库根目录，即使 `--root` 指向子目录；也支持显式绝对路径。不接受父目录跳转、符号链接、非普通文件、无效 UTF-8/TOML、未知键或超过 64 KiB 的文件。支持字段为 `schema`、`scope`、`protect`、`acceptance`、`checks`（参数数组）、`max_files`、`timeout`、`scan_mib`，见[完整示例](examples/task.toml)。

优先级为内置默认值、显式配置文件、命令行参数。命令行提供某个列表时，是**替换**该列表而非追加；`--check`/`--check-json` 替换全部配置检查命令。省略 `protect` 保留默认保护，提供 `protect` 则整体替换，`protect = []` 明确清空保护。空 `scope` 会被拒绝。无效配置不会因为命令行参数覆盖了它而被忽略。

最终策略和精确命令参数在 `start` 时固定。之后编辑配置不会改变当前任务；采用新策略必须明确替换任务。新任务默认保护 `.stewardcheck.toml`。配置和命令参数中不得包含凭据；加载配置并不授权执行命令，仍须 `check --run`。

## 安装

已安装 [pipx](https://pipx.pypa.io/stable/) 时：

```sh
pipx install "git+https://github.com/Afloat16/ai-dev-steward.git#subdirectory=tools/stewardcheck"
stewardcheck --version
```

也可克隆仓库，在已激活的 Python 虚拟环境中执行 `python -m pip install ./tools/stewardcheck`。该包独立于父仓库已有的 Agent Skill。这里使用 Git 安装，不假设它已经发布到 PyPI。

## 上手流程

在需要修改的 Git 项目中运行。下例适用于使用 `unittest` 的 Python 项目，请换成项目真实使用的测试命令。

```sh
stewardcheck start "修复空输入处理" \
  --scope "src/**" --scope "tests/**" \
  --check "python -m unittest discover -s tests" \
  --accept "空输入返回空结果，不改变已有行为"

stewardcheck packet
```

先检查输出，再粘贴给编程助手，让它在声明范围内完成修改。工具只在本地打印上下文，不会发送给任何模型。

检查改动以及声明的测试命令后：

```sh
stewardcheck check --run
stewardcheck report --format json
```

“通过”表示声明的命令执行成功，且当前规则没有要求阻断或复核；**不表示已经证明业务验收条件成立**。这些条件始终以待人工检查的形式保留在记录中。

克隆并安装后，可直接运行独立演示：

```sh
python tools/stewardcheck/examples/demo.py
```

演示在临时 Git 仓库里运行真实测试，依次展示通过、记录过期和越界阻断，不修改当前项目。

## 命令与配置

| 命令 | 用途 |
| --- | --- |
| `start "任务"` | 保存任务约定和真实工作区基线。 |
| `packet` | 输出上下文，默认不超过 32,000 个 UTF-8 字节。 |
| `check` | 静态检查改动，不执行声明的命令。 |
| `check --run` | 静态检查无阻断项后，明确执行已声明命令。 |
| `report` | 输出最近记录并检查是否过期，不重新运行命令。 |
| `doctor` | 检查前提条件、建议可能的检查命令，但不执行。 |

各子命令均支持 `--root PATH`；`check`、`report` 支持 `--format markdown` 或 `--format json`。

**修改范围与上下文范围不同。** `--scope` 可重复指定，路径相对仓库根目录且区分大小写。`*` 不跨目录，`**` 可跨零层或多层目录；不支持负向模式与绝对路径。未指定时为 `**`，记录会提示范围未受限制。`packet --include "docs/**"` 只增加读取上下文，不允许修改这些文件。`--max-bytes` 是字节上限，不冒充某个模型的 token 数；装不下的文件整体省略。输出若需重定向保存，应放到被检查仓库之外，否则新输出文件也可能计入任务改动。

**检查命令不是 shell 脚本。** 重复 `--check` 可声明多个命令；所有平台统一使用 POSIX 风格引号解析，不接受管道或独立重定向操作符。复杂路径或 Windows 参数可用精确 argv：

```sh
stewardcheck start "修复解析" --scope "src/**" \
  --check-json '["python", "-m", "pytest", "-q"]'
```

外层引号需适配当前 shell。命令从仓库根目录运行，继承当前用户权限与环境，**没有沙箱隔离**；它们可能读取凭据、联网或修改文件。不要运行不可信项目的检查，也不要把凭据放进会被本地保存的 argv。Windows 不直接运行 `.bat`/`.cmd`，请显式调用可信解释器及已审阅脚本，例如通过 `node` 运行测试器的 JavaScript 入口，而非 `npm.cmd`。

每条命令默认超时 120 秒，可在任务开始时通过 `--timeout` 修改。输出有容量限制并进行启发式脱敏；超时或输出超限均不能通过。格式化器或测试若修改了受监控内容，会使结果失效，需复核后重新检查。

**保护策略需明确。** 默认保护环境文件、PEM/key、SSH 私钥文件名、`.netrc`、Git 忽略和属性规则、`.gitmodules` 以及 `.github/workflows/**`。`--protect` **替换全部默认保护模式，而非追加**，需要修改这类文件时请审阅完整替换列表。`--max-files` 默认 20；单次快照默认最多散列 256 MiB（`--scan-mib`），路径硬上限 20,000。只对不超过 256 KiB 的 UTF-8 文本进行内容扫描；变化的二进制、大文件和链接需要单独复核。资源超限为错误，不会跳过后宣称通过。

每个 Git 工作区只保留一个活动任务。只有确定放弃此前基线与记录时才使用 `start ... --replace`；没有自动任务历史或源码恢复副本。普通仓库及 linked worktree 分别使用自己的 Git 元数据目录。

## 返回码

| 返回码 | 含义 |
| --- | --- |
| `0` | 通过：声明的检查实际执行成功，且无阻断或复核项。 |
| `1` | 阻断：策略违反、检查失败或检查期间状态变化。 |
| `2` | 待复核：检查缺失/未运行、启发式警告、记录过期或无任务改动。 |
| `3` | 操作错误：状态无效、Git 异常或资源超限。 |
| `130` | 用户中断，需重新检查后再依赖结果。 |

命令行参数语法错误由 Python 参数解析器以 `2` 退出，不生成验收记录；自动化流程应把所有非零状态视为未通过。

## 隐私、边界与维护

状态位于 `<git-dir>/stewardcheck/active.json`，保存任务文字、路径、内容散列、派生指标、精确 argv 及有上限的脱敏命令输出，**不保存源码副本**。POSIX 平台新建状态文件时使用限制性权限。发现文件时尊重未跟踪文件的忽略规则；已跟踪文件仍监控，基线已知路径也不会仅因忽略规则改变而消失。

被忽略的未跟踪文件、子模块/嵌套仓库内部、Git 未列出的特殊文件、外部依赖及两次快照之间的瞬时变化不属于完整监控范围。检测和脱敏都可能误报或漏报；散列用于识别过期与意外损坏，不能防止同权限进程篡改。内置规则不替代 [Gitleaks](https://github.com/gitleaks/gitleaks) 等专用扫描器。共享上下文或记录前仍需审阅。

详细边界见 [SECURITY.md](SECURITY.md)，实现结构见 [架构说明](docs/architecture.md)。安装后在本包目录运行 `python -m unittest discover -s tests -v` 即可执行测试。贡献与发布流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。

调研涵盖 Repomix、Gitingest、Aider、Cline、OpenHands、Gitleaks、pre-commit，以及 Git/Python 官方文档；[调研记录](docs/research.md) 包含来源、关注度快照、设计取舍与证据限制，[THIRD_PARTY.md](THIRD_PARTY.md) 区分概念参考、依赖和代码复用。没有内嵌上游实现或规则库。

本包使用 [MIT 许可证](LICENSE)，适用范围为本目录，不改变父仓库其他材料的许可。
