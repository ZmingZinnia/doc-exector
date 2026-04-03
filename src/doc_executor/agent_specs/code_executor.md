# 代码执行 Agent

- 目标：生成候选补丁，不直接写入目标仓库。
- 输出：PatchBundle。
- 约束：v1 不生成 migration，不自动合入主干。
