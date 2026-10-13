# 历史说书·独立手绘视频

生成或实质优化中文历史说书口播稿，并按用户范围和供应商选择继续配音、独立手绘分镜与完整视频。适用于自主选题、历史故事完整稿和沿用历史项目流程；写稿先执行项目评分、语气审校与复评要求。媒体按当前任务及所在工作区直行规则执行。不用于仅问历史知识或普通短句编辑。

`history-casefile-video` · 原创 Skill · 内容版本 `fddfd50323f8`

## 适用场景

生成或实质优化中文历史说书口播稿，并按用户范围和供应商选择继续配音、独立手绘分镜与完整视频。适用于自主选题、历史故事完整稿和沿用历史项目流程；写稿先执行项目评分、语气审校与复评要求。媒体按当前任务及所在工作区直行规则执行。不用于仅问历史知识或普通短句编辑。

## 安装与使用

```sh
git clone https://github.com/shuaige619/history-casefile-video.git
cd history-casefile-video
```

将此目录按宿主支持的方式登记为本地 Skill，或把 [SKILL.md](SKILL.md) 交给支持 Agent Skills 的助手读取。保留 `scripts/`、`references/` 等配套目录的相对位置；下载完成不代表宿主已加载。

需要能读取本地 Markdown 的 Agent 环境。其他工具与依赖以 SKILL.md 中的要求为准。

## 输入与输出

**输入：** 按 SKILL.md 提供任务材料、必要参数和明确的输出位置。

**输出：** 按 SKILL.md 的交付约定生成结果，并报告未完成或待确认的项目。

## 使用示例

```text
请使用 history-casefile-video 处理我提供的材料。先核对必要输入，再按 SKILL.md 执行并回读实际输出。
```

以上是调用示例，不是已完成业务运行的记录。

## 工作方式

- 先读项目规范，分清交付范围
- 媒体执行范围与直接生成
- 默认创作约定
- 启动与恢复
- 1. 史料与故事主线
- 2. 白话稿与开头钩子
- 3. 先定音频，再锁时间轴

- [references/aspect-and-completion.md](references/aspect-and-completion.md)
- [references/content-routes.md](references/content-routes.md)
- [references/conversational-history-voiceover.md](references/conversational-history-voiceover.md)
- [references/generated-opener.md](references/generated-opener.md)
- [references/narration-pacing.md](references/narration-pacing.md)
- [references/project-contract.md](references/project-contract.md)
- [references/screen-memory-contrast.md](references/screen-memory-contrast.md)
- [references/semantic-visual-mapping.md](references/semantic-visual-mapping.md)
- [references/single-shot-contract.md](references/single-shot-contract.md)
- [references/style-profile.md](references/style-profile.md)
- [references/video-approval.md](references/video-approval.md)

## 验证与限制

本发布步骤核对文件结构、README、上传前后文件摘要；未在本步骤重新执行业务效果验证。

模型输出与业务事实需要结合具体材料核对；结构和上传检查不能替代业务效果测试。

## 来源与二创说明

作者于 2026-10-13 确认本 Skill 为原创；工具文档、外部参考与模型能力仍归各自来源。

文件身份与发布标准版本记录在 [发布清单](skill-release.json) 中。问题反馈请附复现输入、期望结果及内容版本，并先移除私人数据。

## 许可证

以仓库随附的 LICENSE / NOTICE 为准；未附许可证的部分尚未授予额外使用许可，请联系作者。
