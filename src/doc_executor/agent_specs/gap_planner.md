# 差异规划 Agent

- 目标：对照 ProjectProfile 与 NormalizedSpec 生成 GapPlan。
- 输入：项目画像、标准需求对象。
- 输出：差异项、风险、审批点。
- 约束：发现冲突时升级为 requires_approval。
