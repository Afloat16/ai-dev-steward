# AI Dev Steward

[English](README.md) | **简体中文**

**改动有边界，证据可追溯，项目少残留。**

本仓库包含两个可以独立使用、也可以协同工作的组件：用于实验产物治理与算法优化审查的 Agent Skill，以及用于日常编码任务验收的 **StewardCheck**。无需模型账号、API Key、服务器或第三方 Python 运行时依赖。

## 选择入口

| 你要做什么 | 使用哪个组件 | 环境 |
| --- | --- | --- |
| 检查本次任务改了什么、是否越界、测试结果是否仍有效 | [StewardCheck](tools/stewardcheck/README.zh-CN.md)，**0.2.0 alpha** | Python 3.11+、Git |
| 审计旧产物、保留可复现证据、核对多项算法优化的归因 | [Agent Skill](SKILL.md) 与 `scripts/steward.py`，**v1.1.0** | Python 3.10+、Git |

原有 Skill 的四个工具保持只读。StewardCheck 会在 Git 元数据中保存一份当前任务记录，只有 `check --run` 才运行已经声明的程序。两者都不会自动修改源码、删除项目产物、回滚工作或合并改动。

## 从 StewardCheck 开始

使用已安装的 [pipx](https://pipx.pypa.io/stable/) 安装：

```sh
pipx install "git+https://github.com/Afloat16/ai-dev-steward.git#subdirectory=tools/stewardcheck"
stewardcheck --version
```

也可克隆本仓库，在已激活的 Python 3.11+ 虚拟环境中执行 `python -m pip install ./tools/stewardcheck`。CLI 不要求安装 Agent Skill，也不假设已经发布到 PyPI。

进入待修改的 Git 项目：

```sh
stewardcheck start "修复空输入处理" \
  --scope "src/**" --scope "tests/**" \
  --check "python -m unittest discover -s tests" \
  --accept "保持本次修复范围以外的既有行为"

stewardcheck packet
# 先审阅上下文，再交给现有编程助手。
# 审阅改动和已声明命令后才执行检查。
stewardcheck check --run
stewardcheck report --format json
```

请替换为项目真实使用的测试命令。基线包含任务开始时已有的未提交修改和未忽略的未跟踪文件；规则检查范围、受保护路径以及疑似凭据和测试削弱，验收记录绑定工作区状态。结果分为 `passed`、`blocked`、`needs-review`，不把测试成功当作人工验收条件已经被证明。

重复任务可以复用一份经过审阅的 TOML 配置：

```sh
stewardcheck start "修复解析逻辑" --config .stewardcheck.toml
```

配置可选，**不会自动加载**。见[配置示例](tools/stewardcheck/examples/task.toml)、[完整中文指南](tools/stewardcheck/README.zh-CN.md)和[英文指南](tools/stewardcheck/README.md)。策略在任务开始时固定，配置中的命令也必须经 `check --run` 明确授权才能执行。

## 使用原有 Agent Skill

把整个仓库放入宿主支持的技能目录，并保持名称 `ai-dev-steward`。对于支持 `.agents/skills` 的宿主：

```sh
git clone https://github.com/Afloat16/ai-dev-steward.git .agents/skills/ai-dev-steward
```

也可克隆到单独目录，明确要求读取其中的 `SKILL.md`。遵循宿主发现规则，不重复安装多份活跃副本；不宣称所有客户端均已实测。

> 使用 ai-dev-steward 审计旧计划、日志和实验产物。只读，区分保留、待确认和隔离候选，解释证据，不创建新的计划文件。

> 使用 ai-dev-steward 审查优化分支。固定比较的提交，分别追踪重构、算法、精度和缓存改动，指出测试、消融和回滚缺口，把结论放在现有 PR，不重写历史。

从待审计项目运行只读工具：

```sh
SKILL=.agents/skills/ai-dev-steward
python -B "$SKILL/scripts/steward.py" audit --root .
python -B "$SKILL/scripts/steward.py" diff --root . --base main --head HEAD
python -B "$SKILL/scripts/steward.py" gate --input /path/to/actual-evidence.json
python -B "$SKILL/scripts/steward.py" review --root . --base main --head HEAD \
  --input /path/to/actual-evidence.json --format markdown
```

安装位置、基线和证据文件需要替换为真实值。`diff` 盘点已提交的分支差异，并单独报告未提交工作；`gate` 检查输入的配对测量和比较条件；`review` 核对提交对齐、声明的改动覆盖、依赖、测试、回滚与消融。它们不运行实验，也不验证输入结果的真实性。

## 协同而不重复

编码前用 StewardCheck 记录真实起点，编码后检查范围并显式运行测试。涉及算法或性能收益时，再用 Skill 的 `diff`、`gate`、`review` 核对实测证据。验收记录不是性能测量，也不能自动转换成模型加速结论。

讨论复用现有 Issue、PR 或实验平台，不另造计划层级。只有不存在等价入口且确需持久状态时，Skill 才最多使用一个 `.ai/state.md` 和一个 `.ai/artifacts.json`；StewardCheck 的当前任务位于 `<git-dir>/stewardcheck/`，不在源码树新增计划目录。

## 安全与结果解释

**先保留。** 文件名、年龄、忽略状态和重复哈希都不是清理授权。保护源码、原始数据、基线/发布证据、活动任务、Git 跟踪文件和保留依赖。隔离候选需要生命周期声明、合格的普通单硬链接文件、匹配的哈希和新近引用审阅证据，仍须逐路径明确批准并验证恢复；最终删除需要单独授权。移动文件本身不会释放磁盘空间。

**收益必须对应证据。** 固定提交、配置、数据及划分指纹、评测协议、环境、硬件、精度、预算、配对单位、随机种子和原始结果指针。审阅基线、各因素、完整组合及声明的高风险交互，公开无法隔离验证的部分，不伪造消融。比较条件变化时应设计受控对比。`CHECKS_PASS` 只表示输入结构和数值检查通过，不证明真实性、因果性、统计显著性，也不批准合并。示例指标故意返回 `EXAMPLE_ONLY` 和非零退出码。

**检查不是沙箱。** StewardCheck 获得明确授权后运行的程序继承当前用户的权限和环境，可以执行项目代码、访问凭据、改文件或联网。扫描规则可能误报和漏报，被忽略的未跟踪文件、不透明仓库内部、外部依赖及两次快照之间的瞬时修改都不属于完整覆盖。哈希不防御同权限进程篡改。详见[Skill 操作手册](references/playbook.md)和[StewardCheck 安全边界](tools/stewardcheck/SECURITY.md)。

## 目录与维护

| 路径 | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | Agent 入口、模式、停止条件与交付要求 |
| [scripts/steward.py](scripts/steward.py) | 只读产物审计、已提交差异、指标门槛与审查包 |
| [tools/stewardcheck/](tools/stewardcheck/) | 可独立安装的任务基线、上下文和验收 CLI |
| [references/playbook.md](references/playbook.md) | 生命周期、归因、证据格式与迁移 |
| [assets/](assets/) | 合成账本和指标示例，不是实测结果 |
| [tests/](tests/) | Skill 回归与跨组件文档、版本检查 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 两套测试、打包及贡献流程 |
| [Skill 更新记录](CHANGELOG.md) / [CLI 更新记录](tools/stewardcheck/CHANGELOG.md) | 两个组件独立版本历史 |

主介绍以英文为主，两个组件均有中文 README；详细 Skill 和操作手册保持中文。v1.0 账本仍可读，缺少审阅证据的条目不会被视为通过。StewardCheck 0.2.0 保留 schema-1 任务记录兼容性，不会静默改变既有任务策略。

[MIT 许可证](tools/stewardcheck/LICENSE)适用于 StewardCheck 包目录。[第三方说明](tools/stewardcheck/THIRD_PARTY.md)与[设计调研](tools/stewardcheck/docs/research.md)区分概念参考、代码复用与依赖；仓库其他材料保留其原有声明和许可状态。
