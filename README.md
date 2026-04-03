# doc-executor

面向 Django 项目的结构化文档驱动开发流水线原型。

它的目标不是“直接自动改代码”，而是把结构化主文档转成一条可审计、可恢复、可审批的开发流水线，先产出标准工件，再由人工在关键节点确认。

## 项目定位

v1 聚焦以下范围：

- 输入是一份结构化主文档
- 目标项目优先支持 Django
- 输出是一组标准工件和候选补丁包
- 不直接改业务仓库
- 不自动生成 migration
- 不自动合入主干

当前版本更像一个“文档驱动开发编排器”，而不是一个直接写生产代码的黑盒 agent。

## 仓库内约定驱动

如果你希望在 Codex 里直接使用，而不是每次手填路径，推荐按仓库约定组织输入：

```text
<repo-root>/
  docs/
    spec.md
  rules/
    rules.json
  agents/
    audit_reviewer.md
    ...
  artifacts/
```

约定固定为：

- 主文档：`docs/spec.md`
- 规则文件：`rules/rules.json`
- 项目级 Markdown agent：`agents/**/*.md`
- 工件目录：`artifacts/`

这样 Codex 或其他上层入口只需要知道仓库根目录，就能自动定位文档、规则和工件目录。

如果仓库还没有这些文件，可以先调用初始化模板函数生成最小骨架：

```python
from pathlib import Path

from doc_executor.conventions import initialize_repository_convention


initialize_repository_convention(Path("/path/to/repo"))
```

初始化后会生成：

- `docs/spec.md`
- `rules/rules.json`
- `agents/audit_reviewer.md`
- `artifacts/`

如果这些文件已经存在，默认不会覆盖；只有显式传入 `force=True` 才会重写模板内容。

## 核心流程

当前主链路分为 6 个代码型 agent：

1. `项目画像 agent`
2. `文档标准化 agent`
3. `差异规划 agent`
4. `执行编排 agent`
5. `代码执行 agent`
6. `验证审计 agent`

它们围绕下面这些标准工件工作：

- `ProjectProfile`
- `NormalizedSpec`
- `GapPlan`
- `ExecutionGraph`
- `PatchBundle`
- `AuditReport`

流水线阶段固定为：

- `detected`
- `normalized`
- `planned`
- `plan_approved`
- `tasked`
- `patched`
- `patch_approved`
- `audited`

其中有两道人工审批门：

- `planned` 后需要确认差异计划
- `patched` 后需要确认补丁包

## 当前实现内容

目前仓库已经包含这些核心模块：

- [pipeline.py](/opt/proj/doc-exector/src/doc_executor/pipeline.py)
  - 主流水线编排
- [agents.py](/opt/proj/doc-exector/src/doc_executor/agents.py)
  - 6 个核心 agent 的代码实现
- [models.py](/opt/proj/doc-exector/src/doc_executor/models.py)
  - 所有标准工件与阶段定义
- [rules.py](/opt/proj/doc-exector/src/doc_executor/rules.py)
  - 规则加载
- [approvals.py](/opt/proj/doc-exector/src/doc_executor/approvals.py)
  - 审批状态管理
- [artifacts.py](/opt/proj/doc-exector/src/doc_executor/artifacts.py)
  - 工件落盘
- [guards.py](/opt/proj/doc-exector/src/doc_executor/guards.py)
  - 环境与路径守卫
- [cli.py](/opt/proj/doc-exector/src/doc_executor/cli.py)
  - CLI 命令入口

## CLI 用法

CLI 现在只面向仓库约定模式，不再接受显式 `spec/rules/artifacts_root` 路径参数。

先初始化仓库模板：

```bash
PYTHONPATH=src python3 -m doc_executor init \
  --repo /path/to/django-repo
```

然后编辑：

- `docs/spec.md`
- `rules/rules.json`
- 可选的 `agents/*.md`

运行主链路：

```bash
PYTHONPATH=src python3 -m doc_executor run \
  --repo /path/to/django-repo \
  --stop-after planned
```

审批某个阶段：

```bash
PYTHONPATH=src python3 -m doc_executor approve \
  --repo /path/to/django-repo \
  --run-id <run_id> \
  --stage planned \
  --reviewer reviewer_name
```

恢复执行：

```bash
PYTHONPATH=src python3 -m doc_executor run \
  --repo /path/to/django-repo \
  --run-id <run_id> \
  --resume-from planned \
  --stop-after patched
```

如果仓库缺少 `docs/spec.md` 或 `rules/rules.json`，`run` 会直接报错，并提示先执行 `init`。

## 从零到第一次跑通

下面给一个最小闭环示例，假设目标仓库在 `/tmp/demo-repo`。

先初始化仓库约定：

```bash
PYTHONPATH=src python3 -m doc_executor init \
  --repo /tmp/demo-repo
```

然后把 `docs/spec.md` 改成最小结构化文档，例如：

```md
# Teacher API

## Entity: TeacherProfile
- field: teacher_name:str:required
- field: biography:text:optional

## API: POST /api/teacher-profiles
- request: teacher_name, biography
- response: id, teacher_name, biography

## Rule
- teacher_name must be unique
```

再执行到 `planned`：

```bash
PYTHONPATH=src python3 -m doc_executor run \
  --repo /tmp/demo-repo \
  --stop-after planned
```

终端会返回类似这样的 JSON：

```json
{
  "run_id": "a1b2c3d4e5f6",
  "run_dir": "/tmp/demo-repo/artifacts/a1b2c3d4e5f6",
  "stage": "planned"
}
```

这时先看：

- `/tmp/demo-repo/artifacts/<run_id>/gap_plan.json`
- `/tmp/demo-repo/artifacts/<run_id>/state.json`

`gap_plan.json` 会是类似这种结构：

```json
{
  "model_changes": [
    {
      "action": "create",
      "name": "TeacherProfile",
      "fields": [
        {"definition": "teacher_name:str:required"},
        {"definition": "biography:text:optional"}
      ]
    }
  ],
  "api_changes": [
    {
      "action": "create",
      "method": "POST",
      "path": "/api/teacher-profiles"
    }
  ],
  "logic_changes": [
    {"rule": "teacher_name must be unique"}
  ]
}
```

确认计划后，审批 `planned`：

```bash
PYTHONPATH=src python3 -m doc_executor approve \
  --repo /tmp/demo-repo \
  --run-id a1b2c3d4e5f6 \
  --stage planned \
  --reviewer your_name
```

再继续跑到 `patched`：

```bash
PYTHONPATH=src python3 -m doc_executor run \
  --repo /tmp/demo-repo \
  --run-id a1b2c3d4e5f6 \
  --resume-from planned \
  --stop-after patched
```

这时重点看：

- `/tmp/demo-repo/artifacts/<run_id>/patch_bundle.json`

里面会包含候选补丁，比如：

```json
{
  "file_edits": [
    {
      "path": "teacher_app/models.py",
      "content": "from django.db import models\n..."
    },
    {
      "path": "teacher_app/views.py",
      "content": "from django.http import JsonResponse\n..."
    }
  ],
  "test_additions": [
    {
      "path": "teacher_app/tests/test_generated.py",
      "content": "from django.test import TestCase\n..."
    }
  ]
}
```

确认补丁后，审批 `patched` 并继续跑到最终审计：

```bash
PYTHONPATH=src python3 -m doc_executor approve \
  --repo /tmp/demo-repo \
  --run-id a1b2c3d4e5f6 \
  --stage patched \
  --reviewer your_name
```

```bash
PYTHONPATH=src python3 -m doc_executor run \
  --repo /tmp/demo-repo \
  --run-id a1b2c3d4e5f6 \
  --resume-from patched
```

最后重点看：

- `/tmp/demo-repo/artifacts/<run_id>/audit_report.json`

它会告诉你：

- 文档是否被完整覆盖
- 是否命中规则违规
- 是否存在 N+1 ORM 风险
- 是否建议通过

## 工件说明

每次执行都会生成一个 `run_id` 对应的工件目录，里面会保存：

- `project_profile.json`
- `normalized_spec.json`
- `gap_plan.json`
- `execution_graph.json`
- `patch_bundle.json`
- `audit_report.json`
- `state.json`
- `approvals.json`

这使得系统具备下面这些能力：

- 可恢复
- 可回放
- 可审计
- 可人工审批

## 规则系统

当前规则分两层：

1. `JSON 规则`
   - 由运行参数 `--rules` 指定
   - 用于硬校验和结构化检查

2. `Markdown 规则/说明`
   - 作为内置或项目级说明文件被加载
   - 用于定义职责、边界、检查要求和团队约定

### JSON 规则示例

```json
{
  "forbidden_envs": ["prod_tx"],
  "forbidden_patterns": {
    "join": ".jo" "in(",
    "function_import": "import "
  },
  "n_plus_one_markers": [".get(", ".filter("]
}
```

### 当前内置规则

当前实现会显式关注这些风险：

- 禁止触碰 `prod_tx`
- 禁止 `join`
- 禁止函数内 `import`
- 禁止潜在 N+1 ORM 查询

其中 `prod_tx` 是环境硬门禁，不只是审计提示。

## Markdown 形式的 agent/rule

这个项目支持 `Markdown` 形式的 agent/rule，但定位不是替代代码，而是补充“行为契约”。

推荐理解方式是：

- `Markdown` 负责描述
- `Python` 负责执行

### 当前会扫描哪些 Markdown 文件

内置文件：

- `src/doc_executor/agent_specs/*.md`
- `src/doc_executor/rule_packs/*.md`

项目级自定义文件：

- `agents/**/*.md`
- `rules/**/*.md`

### Markdown 适合表达什么

- agent 职责边界
- 输入输出约定
- 审批要求
- 审计清单
- 项目级规范
- 特定框架约束

### Markdown 不适合单独承担什么

以下能力必须由代码强制执行：

- 阻断 `prod_tx`
- 审批状态变更
- 工件落盘
- 阶段恢复
- CLI 编排
- 规则命中后的硬错误处理

### 推荐目录结构

```text
agents/
  project_profile.md
  spec_normalizer.md
  gap_planner.md
  execution_planner.md
  code_executor.md
  audit_reviewer.md

rules/
  global_rules.md
  django_rules.md
  review_checklist.md
```

### 推荐 Markdown 模板

```md
# 名称

## 目标
- 这个 agent 或规则包要解决什么问题

## 输入
- 它依赖哪些工件或上下文

## 输出
- 它应产出什么结论、检查项或建议

## 必须遵守
- 硬性规则或必须升级人工审批的情况

## 禁止事项
- 明确列出不允许的模式

## 备注
- 对团队或项目的特殊解释
```

## 内置 Markdown 文件

当前仓库已经提供了这些内置 Markdown 说明：

- [project_profile.md](/opt/proj/doc-exector/src/doc_executor/agent_specs/project_profile.md)
- [spec_normalizer.md](/opt/proj/doc-exector/src/doc_executor/agent_specs/spec_normalizer.md)
- [gap_planner.md](/opt/proj/doc-exector/src/doc_executor/agent_specs/gap_planner.md)
- [execution_planner.md](/opt/proj/doc-exector/src/doc_executor/agent_specs/execution_planner.md)
- [code_executor.md](/opt/proj/doc-exector/src/doc_executor/agent_specs/code_executor.md)
- [audit_reviewer.md](/opt/proj/doc-exector/src/doc_executor/agent_specs/audit_reviewer.md)
- [global_rules.md](/opt/proj/doc-exector/src/doc_executor/rule_packs/global_rules.md)

这些文件当前主要承担两件事：

1. 作为内置说明与默认规则来源
2. 作为项目级自定义 Markdown 文件的模板参考

## 设计边界

v1 明确不做这些事情：

- 不支持多语言多框架并行落地
- 不自动生成 migration
- 不自动执行数据库迁移
- 不自动改业务仓库文件
- 不自动 merge 主干
- 不提供 Web 控制台

## 验证

当前可以用下面命令执行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## 后续建议

如果下一步要继续增强，优先建议做这两件事：

1. 为 Markdown 文件增加 front matter
   - 例如 `name`、`scope`、`stage`、`priority`

2. 把 Markdown 中的规则进一步编译成结构化校验项
   - 让 Markdown 从“说明文档”升级成“可执行规则来源”
