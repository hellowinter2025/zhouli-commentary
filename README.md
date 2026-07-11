# 周礼评论与今译（Zhouli Commentary & Modern Paraphrase）

一个面向 AI 智能体的 Skill：对**内置的简体中文古籍语料**做语义检索，生成两种风格的中文写作——

- **评论模式**：以"文言文课文译文"的口吻评论现代事件，并自然援引贴切的古籍原句；
- **翻译模式**：把用户的话扩写成"文言文被认真翻译成现代白话"的板正白话，保留原人称、立场与事实。

> “周礼”只是本 Skill 的风格代称，不代表语料只收录《周礼》。

## 两种模式

| 模式 | 触发词 | 输出 |
| --- | --- | --- |
| 评论模式 | 评论 / 分析 / 评价 | 4 段现代白话：重述事件 → 分析处境 → 援引 1–3 句古文并解释 → 收束小道理 |
| 翻译模式 | 翻译 / 改写 / 扩充 | 保留原人称与立场的扩写白话，古句仅作自然点染（0–2 句） |

两种模式都**必须输出现代简体白话**，不得写成可以直接冒充古文的句子。

## 语料

随仓库发布的向量数据库包含 **8455** 个句子级片段（已转简体、UTF-8 保存）：

| 作品 | 句子数 |
| --- | ---: |
| 《大学》 | 142 |
| 《中庸》 | 283 |
| 《孟子》 | 2922 |
| 《论语》 | 1419 |
| 《诗经》 | 3689 |

## 工作原理

1. 语料经 `BAAI/bge-small-zh-v1.5` 编码为 **512 维**向量，存入 SQLite（`float32`，已归一化）；
2. 检索时把查询向量化，与语料向量做**余弦相似度**，取最相关原句；
3. Skill 在写作前运行语义检索，依据 `work` / `chapter` 等元数据**逐字引用**并标注出处，不凭记忆补写。

## 仓库结构

```
zhouli-commentary/
├── SKILL.md                    # Skill 指令（模式、流程、质量检查）
├── agents/openai.yaml          # 智能体接口定义（显示名、默认提示词）
├── scripts/search_classics.py  # 语义检索脚本
├── data/
│   ├── normalized_chunks.jsonl     # 归一化后的句子片段
│   └── poetry_embeddings.sqlite    # 预构建的向量数据库
├── references/
│   ├── corpus.md                   # 语料与检索技术说明
│   ├── style-guide.md              # 文风指南（写作前必读）
│   └── chinese-poetry-LICENSE.txt  # 源语料许可证
├── requirements.txt            # numpy / opencc / torch / transformers
├── LICENSE                     # MIT
├── .gitignore
└── .gitattributes
```

## 安装与运行

```bash
pip install -r requirements.txt
```

语义检索示例（在仓库根目录内执行）：

```powershell
python scripts/search_classics.py `
  --query "用户原文" --query "处境与情绪" --query "可解释此事的道理" `
  --top-k 12 --max-per-work 4 --json
```

参数说明：

- `--query`：可重复使用，一次检索多个语义角度（推荐 2–4 条互补查询）；
- `--db`：SQLite 数据库路径，默认自动查找或读取环境变量 `ZHOU_LI_RAG_DB`；
- `--model`：覆盖数据库记录的模型名称（通常不需要设置）；
- `--top-k` / `--max-per-work`：返回总数与各典籍上限；
- `--min-score`：相似度下限；
- `--json`：以 UTF-8 JSON 输出（便于程序调用）。

## 许可证

代码与文档以 **MIT License** 发布（见 `LICENSE`）；源语料依 `references/chinese-poetry-LICENSE.txt`。
