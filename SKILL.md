---
name: zhouli-commentary
description: >-
  Use semantic retrieval over a bundled Simplified Chinese corpus of the Four Books and Five Classics, Analects, Book of Songs, and Zhouli (Zhou Rites) to produce two kinds of Chinese writing: (1) 古文今译腔评论 that explains and comments on modern events while naturally quoting relevant authentic classical lines, and (2) 周礼翻译 that rewrites and expands the user's words in the same textbook-translation tone while preserving the original person, viewpoint, facts, and intent. Use when the user asks for 周礼评论、古文今译腔评论、古书译文腔、周礼翻译、今译式扩写，or asks to combine modern commentary or rewriting with suitable ancient Chinese quotations.
---

# 周礼评论与今译

对内置的简体中文古汉语语料做语义检索，生成两种风格的中文写作：

1. **评议模式**：用文言课本译笔口吻评议现代事件，并自然援引检索到的真实经句。
2. **翻译模式**：把用户的话扩写为接近文言课本译文的现代白话，保留原人称、立场、事实与意图。

语料现含《大学》《中庸》《孟子》《论语》《诗经》与《周礼》原文（简体、按句切分）。“周礼”既是风格代称，也对应真实收录的《周礼》正文；不要把检索范围误说成只有风格、没有《周礼》，也不要声称收录了未入库的其他经籍。

最重要的边界：两种模式都必须输出现代白话。“周礼翻译”不是翻译成文言文，而是把现代话扩写成类似文言课本译文的现代话。不得写成“非我不欲助子”“恐言之未明”一类可以直接冒充古文的句子。

## 执行流程

1. 根据用户动词选择模式：要求评论、分析或评价时使用“评论模式”；要求翻译、转换、改写或扩充时使用“翻译模式”。
2. 始终读取 [references/style-guide.md](references/style-guide.md)。需要说明语料、出处或限制时，再读取 [references/corpus.md](references/corpus.md)。
3. 在写作前运行语义检索。一次性传入 2 至 4 条互补查询，避免重复加载模型：用户原文、去掉现代词后的处境概括、人物关系或情绪，以及可以解释此事的朴素道理。查询应描述含义，不要先凭记忆指定某句名言。

```powershell
python <skill-dir>/scripts/search_classics.py --query "<用户原文>" --query "<处境与情绪>" --query "<可解释此事的道理>" --top-k 12 --max-per-work 4 --json
```

4. 从候选中只选择真正能解释当前事件的原句。评论模式引用 1 至 3 句；翻译模式引用 0 至 2 句。宁可少引，也不要仅因相似度高而生搬硬套。
5. 逐字引用检索结果中的 `text`，依据 `work`、`chapter` 等元数据标注出处。不得凭记忆补写后半句，不得张冠李戴。检索不到合适原句时，不强行引用，并直接完成正文。
6. 用现代简体白话输出。除非用户明确要求展示检索过程，否则不要输出相似度、候选列表、数据库信息或工作步骤。

## 评论模式

输出四个自然段，通常不加小标题：

1. 用古文课文译文的口吻重新解释事件，补出主语、起因、动作和结果，并把网络词拆成朴素白话。
2. 分析人物处境、心理、矛盾、荒谬或可笑之处，把小事讲得板正而有章法。
3. 自然引入 1 至 3 句检索所得古文，每引一句都解释它与眼前事情的关系。不要堆砌名言。
4. 郑重收束为一个小道理，可以略带克制的幽默。

## 翻译模式

先在心中锁定原文的人称、时间、事实、态度、愿望和否定关系，再进行转换与扩充：

- 原样保持“我、我们、你、你们、他、她、他们”等人称词。不得把“你”换成“子、君、阁下”，不得把第一人称改成旁观者评论。
- 保持原有立场和事件结果，不擅自增加新人物、具体数字、承诺、罪名或因果事实。
- 把省略的动作顺序、合理原因和心理感受补充完整，但将推测写成“大概、似乎、想来”，不要伪装成事实。
- 使用板正、解释性强的现代白话；可以扩为原文约 1.5 至 3 倍，用户指定长度时服从用户。
- 古句只作自然点染。引用会改变原意或打断口吻时，完全不引用。
- 默认只输出转换后的正文，不附分析、说明或模式标签。

优先使用“我并不是不愿意……只是因为……所以现在……”这一类完整现代句式。若一句话脱离上下文后看起来像古籍原文，就把它重写为更自然、解释性更强的现代白话。

## 质量检查

交付前确认：

- 全文是简体中文和 UTF-8 友好的标点。
- 读起来像“文言文被认真翻译成现代白话”，不是文言正文或古装剧台词。
- 没有滥用“也、矣、乎、哉、焉、夫”等虚词。
- 现代网络词已经解释，而不是原样密集照搬。
- 引文真实、短小、相关，并已解释其作用。
- 翻译模式的人称、立场和核心事实没有漂移。
- 翻译模式没有把“你”古化为“子、君”，也没有密集出现“非、亦、惟、故、未尝、焉”等古文连接词。
