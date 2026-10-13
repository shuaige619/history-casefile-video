# Natural Narration Pacing

Read this reference when a long TTS narration sounds breathless, mechanically continuous, over-trimmed, or like a text recital.

项目存在 `历史音频生成规范.md` 和音频计划检查工具时，先执行该项目的统一规则与检查。旧作品的参数、数量和脚本仅作实现参考，不能直接作为新稿已经通过的证据。

## Diagnose before regenerating

Check the synthesis and assembly manifest. A common failure is combining several paragraphs into one long TTS request, trimming its edges, then inserting only a tiny fixed gap between requests. Punctuation may create micro-pauses, but paragraph and chapter boundaries disappear. Global `atempo` applied after adding silence compresses those pauses again.

Do not fix breathlessness by adding silence only at the end or by inserting the same gap after every sentence.

## Semantic breath units

先执行项目的供应商选择规则。当前明确选择优先；工作区有用户设置的默认时读取audio-default.json与audio-policy.json并登记继承，无有效默认且未指定时才询问。同批恢复不重复问，失败不自动切换。百炼可沿用 `qwen3-tts-instruct-flash`、`Vincent`（田叔）；火山沿用用户指定的已核复刻音色。已有凭据不等于默认选择。实际服务区域、参数和可用性在调用时核查。不要内置密钥。呼吸单元、章节边界和重音词取自本次稿件，不复制上一片的章节编号或人名。

可复用朗读指令：像熟悉这段历史的说书人坐下来慢慢讲，自然白话，不是课文朗诵、新闻播报、戏曲或夸张评书；铺垫平稳，关键人名和判断略慢，转折前收住，问完留一拍，结论慢下来落稳；情绪克制，悲剧处不煽情。朗读指令与正文分离。

Split narration into units that preserve the exact text:

- normally one or two sentences;
- split a long sentence at a real semicolon, colon, or causal turn;
- keep a short impact sentence as its own unit;
- separate a primary-source quotation from its plain-language translation;
- do not split names, dates, fixed quotations, or tightly coupled clauses.

Use a consistent voice profile across units. Author each unit's narrative function, exact focus words, delivery and reason for its pause from the current script, and verify that the actual request includes them. Ask for natural conversational history narration, clear names and quotations, restrained emotion and sentence-final settling.

For Bailian, record `optimize_instructions` explicitly per unit. For Volcengine, record null and omit this unsupported field from requests; use a verified instruction-capable model and its actual supported context field. Never claim that a provider-specific pronunciation or optimization control remains effective on another provider. Check submitted requests, not just planning files.

## Pause hierarchy

Starting ranges, to be tuned by the voice and script:

| Boundary | Typical pause |
|---|---:|
| light sentence continuation | 220–320 ms |
| short impact sentence | 320–420 ms |
| question within a paragraph | 450–600 ms |
| ordinary paragraph | 450–600 ms |
| paragraph-ending question or major judgment | 600–800 ms |
| opening/chapter transition | 900–1200 ms |

For a restrained storyteller delivery, use a wider hierarchy rather than a single global slowdown:

| Storyteller boundary | Starting pause |
|---|---:|
| light sentence continuation | 380–480 ms |
| short impact sentence | 500–620 ms |
| question within a paragraph | 680–820 ms |
| ordinary paragraph | 700–850 ms |
| paragraph-ending question or major judgment | 900–1100 ms |
| opening/chapter transition | 1300–1600 ms |

Use one or two sentences per semantic breath unit when their meaning and breath fit together. Closely connected short sentences may share a unit; a period does not require restarting the voice. Ask the voice to keep setup lines level, settle before a reversal, lift a question lightly, and slow down into a judgment. Keep the sound conversational and restrained.

Vary pauses by narrative function. Questions, reversals, quoted evidence, deaths, and chapter resets should not all receive the same duration. Keep tragedy restrained; do not add performative sighs or invented emotion.

These tables are planning ranges for the **total gap**, not silence to append unconditionally. At each join measure the previous unit's native trailing quiet and the next unit's native leading quiet, then insert `max(0, target total gap - trailing quiet - leading quiet)`. Record measured and inserted samples. Excess native quiet needs review; do not blindly trim breath, light syllables or word endings. Low-level detection estimates quiet, not exact phoneme boundaries. Do not choose every pause automatically from punctuation or character count.

## 多音字与专名发音

完整合成前建立项目级读音台账，至少盘点人名、地名、宫门/官职名、史书名、年号日期、生僻字，以及语境会改变读音的多音字。

- 每条用完整词组定位，记录 `displayText`、`ttsText`、拼音/声调说明和启用状态。正文与字幕始终保留正确汉字；`ttsText`只用于语音请求。
- 台账绑定当前正文版本并保留唯一冻结来源；明确 `enabled`，禁用项不得进入实际请求。完整短语按长词组优先匹配，已确认的优化参数覆盖也要实际执行。语气词轻声、儿化与收音纳入实际听辨，不临时增删正文。
- 不对“的、还、为、朝、重、长”等单字做全局替换，否则会修对一处、误伤另一处。对“明朝的夺门之变”这类已知语境，只覆盖完整词组并明确“的读轻声 de”。
- 对每个受保护词的首次出现生成短样音，由人耳核对实际读音后再锁定完整轨。ASR文字相同不能证明声调正确，自动解码或波形检查也不能代替听感核对。
- 发现读音错误时，把读音覆盖纳入请求指纹，只使受影响的呼吸单元缓存失效；重生该单元后重组全轨、字幕时钟和响度母带，再做完整性检查。
- 在相关首现样音尚未经人耳确认时，状态只能写“读音待确认”，不宣称“多音字无错”。

## Tempo and pause order

Calibrate speech duration separately from pause duration:

1. Synthesize and measure each speech unit.
2. Measure existing edge quiet and calculate only the additional silence needed at each join.
3. Default to speech tempo 1.0 and derive total duration from actual unit samples plus the additional silence. Do not count native quiet twice. A hard duration constraint requires discussing cuts; a tempo change still needs the user's actual choice.
4. If a speech-only adjustment is explicitly agreed, apply it before adding final pauses, or compensate raw inserted silence so final pauses retain their planned lengths.
5. Do not run a global speed-up that unknowingly shortens the final pause hierarchy.

This workflow uses the project’s duration rule; without a different explicit requirement, a complete narration must fit within 60 minutes including natural pauses. Content determines its length, with no fixed target or minimum and no requirement to fill the hour. Estimate speech plus pauses before generation and verify the final audio duration. If it exceeds the ceiling, revise scope or remove repetition through the manuscript-change workflow instead of silently accelerating approved speech. Never reach a target by adding a silent tail.

Before full generation, produce and inspect a representative sample containing setup, suspense, a question, and a judgment. Current explicit user selection authorizes that provider and voice; do not ask again just because this is a provider change. A new batch without a provider selection must wait for the user's choice. Resume the same authorized batch without repeated approval; never switch provider automatically after failure. If the sample cannot match the agreed delivery, address that specific issue. Preserve the text and natural pauses within the project's duration rules.

## Captions and visual timeline

When captions are in scope, regenerate their times from the final paced audio and clear them during intentional pauses. Unit start/end timestamps may include native edge quiet; label these as unit-based estimates unless actual speech alignment was performed. Cap individual caption duration for readability, then rebuild scene timing and chapter markers from the new audio.

If the visual scene would become too long because of a chapter pause, split the visual event or use a deliberate hold/card. Do not let pacing repairs reintroduce long static shots.

## Resumability and cost

Cache each unit by a hash of the complete effective request: exact TTS text, enabled pronunciation overrides, provider/region/endpoint, model, voice, language, full instructions, optimization flag and other synthesis parameters. Recompute and compare this fingerprint even on the completed-file fast path; a unit-plan hash alone is insufficient. Keep synthesis and assembly fingerprints separate. Adjusting external pauses, subtitle splits or local loudness does not require another TTS request.

Keep every submission and its result. For a timeout or lost connection, mark the request unknown and inspect provider state, retained responses and cache before considering resubmission. If an audio URL/result already exists, retry only the download. Unresolved unknown requests stay pending; do not silently retry generation. Preserve resolvable paths to earlier attempts across versions.

Only persist credentials when the user explicitly requests it. If the user specifies project storage, use a private ignored directory (0700) and file (0600), excluded from delivery bundles; otherwise follow the approved private configuration location. Never include secrets in a public manifest, script, shell command, or log. Read the provider's own credential without echoing it.

## QC

Record:

- unit and paragraph counts;
- pause count and total by reason;
- speech tempo factor;
- final duration, sample rate, channels, integrated loudness, loudness range, and true peak;
- measured silence count, median, upper percentile, and maximum;
- old/new comparison when revising an existing narration;
- caption count and maximum caption duration;
- audio, caption, chapter, and visual-timeline end alignment.

Listen to the opening, a quotation plus translation, a high-emotion passage, a chapter boundary, and the ending. Metrics verify spacing, not whether the delivery feels human.

Also listen to all protected phrases at first occurrence, ASR differences and suspicious joins. Record the inspected audio hash, intervals, actual reviewer identity and remaining issues. Independently transcribe the real audio without supplying the complete correct script as context. ASR similarity cannot establish tones or natural delivery. Unheard audio has no listening score; technical success does not become listening acceptance. Check pure narration and any requested final mix/encoded output separately, with their actual hashes and scope. Follow the project's complete rubric, repair affected units, and listen again before declaring sound acceptance.
