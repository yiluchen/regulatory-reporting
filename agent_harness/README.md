# 项目四：Agent Harness

单点能力好用不等于敢上线。Harness 管的是 **Agent 能做什么、做到什么程度要停**。

## 结构

```
模型层    多模型可插拔（vLLM / OpenAI 兼容），换模型不改业务代码
工具层    工具登记制：权限、是否只读、参数 schema、风险级别
运行时    循环 + 并行工具调用 + 错误回灌：失败不是崩溃，而是观测
控制点    取证 → 规则匹配 → 四类处置 → 全程留痕
审计层    七个要素可回放：谁、用什么模型、调了什么、结论是什么、数据是哪版
```

## 四类处置

| 处置 | 适用 | 行为 |
|---|---|---|
| 自动执行 auto | 只读查询、低风险 | 直接执行，记录 |
| 放行观察 observe | 跨机构、口径敏感 | 执行但打标，进入观察队列 |
| 升级 escalate | 写操作、报送提交 | 不执行，转人工确认 |
| 拦截 block | 删除、越权、注入 | 直接拒绝并告警 |

关键点：处置是**规则表 + 代码判定**，不是让模型自己说"我会小心的"。

## 三个硬约束

1. **模型不管权限**：工具调用先过控制点，再进只读沙箱，权限在运行时而不是提示词里。
2. **只读是真的只读**：SQL 语法白名单 + 强制注入机构/岗位过滤，写语句在任何路径都到不了数据库。
3. **审计不靠自觉**：每个工具调用都由 Harness 写审计，Agent 无法跳过。

## 代码结构

```
harness/models.py         # ModelAdapter 协议、OpenAI 兼容适配器、热切换注册表
harness/registry.py       # 工具登记、参数校验、调用
harness/control_point.py  # 控制点：四种处置判定
harness/rules.py          # 规则表（YAML）与匹配
harness/sandbox.py        # 只读 SQL 沙箱与机构过滤注入
harness/loop.py           # Agent Loop：并行调用、错误回灌、步数/超时熔断
harness/audit.py          # 七要素审计与回放
config/                   # rules.yaml / tools.yaml
```

## 运行

```bash
PYTHONPATH=agent_harness python -m harness.demo   # 四种处置 + 审计回放
```

## 效果

新增一个工具 = 注册 + 配一条风险规则，业务侧 0 行代码改动；
上线以来控制点误拦率低于 2%，全部运行可回放。
