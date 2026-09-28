# AI Dev Steward

面向 AI 辅助算法开发的 Agent Skill：收敛 planning/planing 等重复计划，审计过期实验产物，把多项算法优化变成可定位、可验证、可回滚的审查单元。

**v1.1.0 · Python 3.10+ · Git · 无第三方 Python 依赖 · 默认只读**

## 核心原则

不要为了治理残留再制造更多文件。优先复用现有 Issue、PR、实验平台；没有等价入口时，最多维护一个 `.ai/state.md` 和一个 `.ai/artifacts.json`。不按文件名、mtime、Git 忽略状态或重复哈希决定删除。

本工具没有删除、移动、自动训练或自动合并功能。隔离候选不是删除许可；数值门槛通过不是算法正确性证明。运行记录、账本和审查映射都是输入者声明，仍须独立核对。

## 目录

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | Agent 入口、模式选择、停止条件与交付要求 |
| `scripts/steward.py` | 只读审计、差异盘点、指标门槛与审查包 |
| `tests/` | 临时 Git 仓库和合成指标的回归测试 |
| `references/playbook.md` | 生命周期、安全边界、实验归因和格式说明 |
| `assets/ledger.example.json` | 产物账本示例，不能当作真实登记 |
| `assets/metrics.example.json` | 指标、逻辑改动、消融示例，不能当作实测 |
| `CHANGELOG.md` | 版本变更和迁移说明 |

## 安装与使用

把整个仓库放入宿主支持的技能目录，并保持目录名为 `ai-dev-steward`。以下以支持 `.agents/skills` 的宿主为例；其他宿主按各自发现规则配置，不重复安装多份活跃副本。

```sh
git clone https://github.com/Afloat16/ai-dev-steward.git .agents/skills/ai-dev-steward
```

也可以放在独立目录，在对话中明确要求读取其中的 `SKILL.md`。不宣称所有客户端均已实测。

从待审计项目的根目录运行：

```sh
SKILL=.agents/skills/ai-dev-steward

# 没有账本时只盘点；不会创建治理文件。
python -B "$SKILL/scripts/steward.py" audit --root .

# 盘点分支已提交差异，并单独列出未提交工作。
python -B "$SKILL/scripts/steward.py" diff --root . --base main --head HEAD

# 使用可信评测流程产生的真实数据，不使用示例冒充实测。
python -B "$SKILL/scripts/steward.py" gate --input /path/to/actual-evidence.json

# 在同一份证据中补充 changes/ablations，输出可粘贴到 PR 的审查包。
python -B "$SKILL/scripts/steward.py" review --root . --base main --head HEAD \
  --input /path/to/actual-evidence.json --format markdown

python -B -m unittest discover -s "$SKILL/tests" -v
```

输出默认到终端，不自动落盘。需要保存时复用一个已批准的位置，不生成时间戳副本或提交原始敏感日志。

## 适合怎样提问

> 使用 ai-dev-steward 审计项目中的旧计划、日志和实验中间产物。只读，区分保留、待确认和隔离候选，解释每项理由。

> 使用 ai-dev-steward 审查当前优化分支。固定基线，分别追踪重构、算法、精度和缓存改动，指出测试、消融和回滚缺口，不重写分支历史。

## 安全与适用范围

保护源码、原始数据、模型、基线/发布证据、运行中的任务、Git 跟踪文件及保留节点的传递依赖。跨仓库、子模块、符号链接和硬链接不得作为普通清理目标。未登记、证据过期、哈希不符、示例输入或无法核对引用时均不产生可执行清理授权。

账本只表达已知依赖，不能发现全部动态引用、远程训练任务或对象存储消费者。工具不是恶意并发文件系统的安全沙箱；实际隔离必须停写、重新核验、逐路径审批，并验证恢复。

指标比较要求同条件配对；硬件、精度等本身是实验变量时，保留不可比结论并人工设计受控对比，不伪造相同元数据。大型优化不强制执行指数级全部组合，但必须公开缺失的单项和高风险交互证据。

退出码及 v1.0 账本迁移要求见 `references/playbook.md` 和 `CHANGELOG.md`。示例指标有意返回 `EXAMPLE_ONLY` 和非零退出码。测试使用合成数据，不代表真实模型加速、真实项目清理或跨平台验证。
