# 独立镜头项目契约与运行方法

这是新主题的当前格式。不要把上一部的角色、章节编号、41.3秒开篇、影片时长或素材路径当作默认输入。每个主题独立建项目；新项目不依赖任何旧影片目录。

## 本地依赖与命令

Python 3.10+、Pillow、NumPy、FFmpeg/ffprobe和可用中文字体。优先使用当前环境已有的依赖；桌面环境可查询工作区依赖运行时路径。以下 `<skill目录>` 是实际安装目录，`<项目>` 是本次主题目录。字体用 `meta.fontPath` 或 `CASEFILE_FONT` 指向合法安装的中文字体；不把系统字体复制进skill。

```bash
python3 <skill目录>/scripts/single_shot_assets.py init <项目> --title "<历史主题>"
```

目录核心：

```text
brief.md / progress.md
source-ledger.json / story-architecture.json / hook-ledger.json
script-tagged.md / script.md / narration.txt
production.json / video-approvals.json
assets/images/ / assets/clips/ / assets/audio/
subtitles/ / outputs/ / .build/
```

辅助脚本只做本地登记、编排与检查；**不会调用任何远程模型**。真实图像/TTS工具由代理按阶段使用，视频模型另按确认规则取得授权。

项目另有《历史图片素材规范》《历史视频素材规范》、visual-policy及审核模板时，一并执行。现有脚本仅实现部分基础技术/清单条件：不能凭validate成功、accepted或一条reviewNotes证明逐项语义、原生来源、完整动作、真实生成请求及最终完成已经审核。缺失的新规范记录先补齐，保持pending；未经补充验证的旧执行器不得直接用于新批次提交。

若项目已维护《历史图片风格与调用规范》及 image_style_pipeline，新增图片和封面先通过该入口锁定风格/参考/通道并完成实际校准，再衔接本页的时间轴登记器。项目级 image_studio_adapter 的 `--execute` 会发图片 API 请求；本页的素材登记器仍不生成图片。不要把旧项目私有 .build 执行脚本复制到新主题，或把本页 register/validate 结果当成已通过完整风格审查。

## production.json

```json
{
  "meta": {
    "schema": "history-single-v1",
    "title": "本次主题",
    "durationMode": "natural",
    "durationHintMinutes": 25,
    "durationFrames": 240,
    "fps": 30,
    "orientation": "landscape",
    "aspectRatio": "16:9",
    "width": 1920,
    "height": 1080,
    "audio": "assets/audio/narration.m4a",
    "audioTempo": 1.0,
    "fontPath": "实际字体路径",
    "minimumImagePixels": [1280, 720],
    "minimumVideoPixels": [1280, 720]
  },
  "protectedTerms": ["本片人名", "本片地名", "不可拆开的词组"],
  "chapters": [{"index": 1, "title": "具体章节名称", "startFrame": 0}],
  "captions": [
    {"id": 1, "paragraph": 1, "startFrame": 0, "endFrame": 105, "text": "本句实际口播"},
    {"id": 2, "paragraph": 1, "startFrame": 120, "endFrame": 230, "text": "下一句实际口播"}
  ],
  "shots": [{
    "id": "SC001",
    "startFrame": 0,
    "endFrame": 120,
    "cueIds": [1],
    "narration": "本句实际口播",
    "visualGoal": "这一刻要看懂什么",
    "matchReason": "为什么具体主体、动作和证据层级与口播相符",
    "artDirection": "独立画面简报，含主体、方向、状态、禁项",
    "evidenceClass": "F/I/D等，与证据台账一致",
    "visualFamily": "用于复核重复语义，不是禁止再次出现这个人物",
    "layout": "single-full-frame",
    "asset": "登记器填入",
    "imageReview": "pending",
    "imageSource": null,
    "video": null
  }]
}
```

示例仅说明字段；实际shots必须完整覆盖0至测得的durationFrames。所有帧号为整数，镜头区间前闭后开。每条**原始**字幕cue完整分配到一个镜头且只分配一次；需要更短镜头时，先在音频定稿阶段按自然词组细分cue，不能为切镜头拆人名或否定词。纯停顿镜头可无cue，但要有继续停留的视觉理由。画面镜头覆盖停顿，字幕不必覆盖停顿。

`narration.txt`只含朗读正文，以换行分段；去掉段落换行后必须与原字幕文字逐字一致。图像提示词、史料标签和朗读指令不能混入正文。

## 音频冻结

先完成实际口播与cue时间，再运行：

```bash
python3 <skill目录>/scripts/single_shot_assets.py freeze <项目>
```

记录音频SHA、真实时长与原字幕快照的SHA。后续验证不允许偷偷改字、改时间或换音轨。要重新配音时，应按用户的新要求另存音频与字幕版本、保留旧基线和修订原因，再明确建立新基线；不得改哈希来掩盖未经允许的变化。

研究台账沿用F/Q/I/D分级：每条主张有source_ids、出处位置、置信度、争议与使用段落。图像与视频记录不是史实证据本身。

## 素材登记与审核

先准备镜头数据，工具生成结果保存为单个独立源文件。调用登记器只建立候选：

```bash
python3 <skill目录>/scripts/single_shot_assets.py register <项目> --id SC001 --source <真实图片路径> --kind image --origin generated-image
```

看过真实画面并和对应口播比较后，才用同一命令加 `--review accepted --note "<具体检查结论>"`。失败用rejected并保留文件，不删旧版。注册器用内容哈希命名、检查原生像素和画幅，并保留替换历史；生成成功不自动通过审核。

这个命令的备注是入口摘要，不能替代完整审核记录。先完成项目检查表，再绑定资产SHA、正文和镜头语义快照；改变对应口播、evidenceClass、画面目标或来源关系后重审。orientation、aspectRatio必须与实际宽高一致，不能只核对其中一种表示。联系表、同源派生和先放大后登记需实际追溯，不能仅信任自填字段。

- 每个imageSource/video包含asset、sha256、nativeWidth/Height、review、reviewNotes、origin和layout。
- 补记实际generationPrompt、参考图路径/哈希、生成请求ID等可追溯数据。
- 网络来源origin=web必须补sourcePage、creator、license、rightsStatus=allowed及必要的“非该事件原物/后世画像”披露；下载不等于可用。
- 同源裁切、改色、重编码应记录共同derivedFromSourceId，使重用可被检查。广义visualFamily重复只是人工/模型视觉复核提示，不能把所有竹简、城门、同一人物永久禁掉。
- 原生尺寸门槛用于正式素材，不能先放大再声称满足原生门槛。测试/低清预览若调整门槛，必须标明，不作为正式质量证明。

## 生成视频的技术记录

决定确需动态的镜头才增加videoPlan：

```json
{
  "videoPlan": {
    "provider": "用户确认的服务",
    "model": "真实模型ID",
    "prompt": "准确的一次动作、起点与终点",
    "durationSeconds": 5,
    "resolution": "服务实际支持的横向原生尺寸"
  }
}
```

如果服务还要求fps、帧数、seed、端点或其他生成设置，也放入videoPlan；不要包含密钥。批次记录会对整个videoPlan生成参数指纹，因此这些设置改变也需重新确认。

读 [视频确认规则](video-approval.md)，再创建**不提交任何生成任务**的待确认记录：

```bash
python3 <skill目录>/scripts/single_shot_assets.py draft-video-batch <项目> --batch VB001 --ids SC001 SC004
```

把数量/时长/参考图/动作/费用范围展示给用户并等待。真实回复明确批准后，记录status=approved与 `userConfirmation: {"text":"真实用户回复摘要","source":"可信对话中可定位的回复" }`。不得自行制造确认。

每次提交前先检查参数与批准是否一致：

```bash
python3 <skill目录>/scripts/single_shot_assets.py check-video-approval <项目> --batch VB001 --id SC001
```

检查通过仍不替代真实授权。开始提交时记录该job的attempts；标明submitting/running/completed/failed/unknown以及可用任务ID、幂等键。unknown不得再发。默认maxAttempts=1。

提交前另外检查参考图当前未撤回、审核仍对应当前语义；核对实际参考、模型、提示词优化开关及其生效记录与确认范围。现有参数检查不包含全部运行期证据。生成类视频缺少真实completed任务结果、原件或实际动作审查时不能接受。动态改为static-approved也须引用真实用户选择，不能只改标记。

下载已获准任务并抽帧审核后，用 `register --kind video --origin generated-video --batch VB001` 登记，仍先pending、再明确accepted。应另外确认该次真实生成实际用了记录的参考图与参数。本地代码渲染使用origin=local-render，网络片段使用web并检查版权；不得把模型视频伪标local-render来绕过确认。

视频接受前还应连续检查完整使用区间，或连续逐帧检查其动作；保存首中尾、关键帧和实际审查区间。关键帧抽样不替代全段连续性检查，不声称全片逐帧观看。

videoPlan未完成时正式构建会失败。只有用户明确接受静帧替代才记videoDecision=static-approved；`--draft`只允许标明“待动态”的本地预览，不能交付为承诺已兑现。

## 合成

若项目存在 `历史视频翻页与运镜规范.md`，先按其当前规则准备封面、页面清单、运镜与翻页计划。本AI写作工作区要求同画幅封面先停留再翻入正文、每幅正文静图仅一次固定缩放的单向水平平移、所有相邻页翻页。下列旧执行器命令只有在已支持该计划并核对实际输出时才能用于正式交付；否则先适配，不得静默回落为硬切、章节翻页或zoom默认值。本工作区旁白从第0帧随封面直接播放，字幕按源cue同步显示；封面和开场翻页占开头介绍的原画面时间，不延长成片，不给旁白/字幕/贴字/章节统一加偏移。受影响的开场画面按口播语义重排并记录映射，不能漏掉必要画面或让音频等翻页。

```bash
python3 <skill目录>/scripts/single_shot_assets.py validate <项目>
python3 <skill目录>/scripts/single_shot_render.py <项目> --prepare-only
python3 <skill目录>/scripts/single_shot_render.py <项目> --name final-video.mp4
```

重复构建选择新版本名称，不覆盖用户已有成片。缓存先写临时文件、核对帧数，再原子替换；坏缓存留存为invalid。完整视频沿用音轨1.0，不循环素材填长度。段视频音轨丢弃，只使用批准的连续旁白。默认不加音乐；若明确添加音乐，另做有版权记录和旁白避让的混音，并把该批准混音作为比较基线。

当前渲染器会将所用视频按镜头时长调整速度，不能把这个默认行为当作已审编辑决定。采用前记录源片段区间、速度、停帧/光流和最终时长，复核实际派生动作；若不符合本片计划则先修正编辑设置或执行器。源视频accepted不自动传递到不同速度或裁取区间。模型素材的本地派生仍保留模型根来源与原任务记录。

`--from-frame/--until-frame`用于章节预览，`--draft`可临时以静帧预览待批准动态；报告不会自动变成完成。

选用准确贴字时，shots.labels可含text、x/y、fontSize、vertical、startOffsetFrames/endOffsetFrames。出现时机必须对应具体口播。普通视频不支持物件跟踪，因此带标签的视频镜头会被拒绝；确需追踪时先在独立结构合成中完成并审核，不静态叠到漂移物件上。

## QC与完成

```bash
python3 <skill目录>/scripts/single_shot_caption_qc.py <项目> outputs/final-video.mp4
python3 <skill目录>/scripts/single_shot_audio_qc.py <项目> outputs/final-video.mp4
ffmpeg -nostdin -hide_banner -nostats -i <项目>/outputs/final-video.mp4 -vf blackdetect=d=0.12:pic_th=0.98:pix_th=0.08 -af volumedetect -f null -
```

本工作区片头不造成音频偏移：完整输出从0秒与源音轨比较，包含封面停留和翻页期间的首句；章节预览给字幕QC传相同帧区间，音轨QC的reference-offset为该预览起始秒数，不额外减去封面时长。核对开头没有新增静音、延迟、重复介绍或字幕空缺，并检查封面/开场画面与当时口播语义及字幕布局。音轨比较检查完整波形的连续30秒区块，不是逐字ASR或音素审核。

还须：

1. 重新核对实际素材哈希、许可、语义、画面方向和文字完整；哈希唯一不证明语义唯一。近似图像可用感知哈希筛候选，最终看图判断。
2. 检查实际成片的开篇、每章边界、关键证据/转折、否定/假设、结尾；有静图运镜规则时另按SP01—SP06覆盖片头封面、每页完整平移及全部相邻页翻页，不只查章节转场。字幕不挡重要道具，也不跟随翻页变形。必要时试听对应段落。
3. 检查输出视频实际duration/frames/尺寸/帧率/声道。长片拼接的毫秒级量化与缺帧要分开判断。若精确末秒seek无图，从尾部短区间实际解码取最后帧，不直接判缺帧。
4. 记录字幕像素检测、全轨波形、黑段、音量及视觉抽查路径到qc-report.md与final-qc.json，并绑定输出SHA。dB/峰值不冒称LUFS；模型视觉审核不冒称真人逐帧验收。
5. 仅在完整时间轴、承诺范围、自动检查和实际视听抽查都完成后，更新导出报告fullFilmComplete=true并引用final-qc.json。预览/审批pending/缺素材不得完成。

此skill的元数据采用 [官方技能格式](https://learn.chatgpt.com/docs/build-skills)，详细指令与可复用本地脚本分开加载。
