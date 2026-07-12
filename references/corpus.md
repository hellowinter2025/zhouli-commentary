# 语料与检索说明

## 收录范围

随 Skill 发布的数据库包含 **11752** 个句子级片段，全部转换为简体中文并以 UTF-8 保存：

| 作品 | 句子数 |
| --- | ---: |
| 《大学》 | 142 |
| 《中庸》 | 283 |
| 《孟子》 | 2922 |
| 《论语》 | 1419 |
| 《诗经》 | 3689 |
| 《周礼》 | 3297 |

其中《大学》《中庸》《孟子》《论语》《诗经》来自 `chinese-poetry` 项目；《周礼》正文来自 Kanripo `KR1d0001`（六官全文），经本地清洗、分篇后纳入同一检索库。

Skill 名中的“周礼”仍可作风格代称，但语料现已**真实收录**《周礼》原文。回答时勿声称收录了未列出的其他经籍（如《仪礼》《礼记》《周易》注疏等）。

## 技术信息

- 向量模型：`BAAI/bge-small-zh-v1.5`
- 向量维度：512
- 数据库：SQLite，向量以 `float32` 保存
- 切分粒度：句子级
- 检索方式：查询向量与语料向量的余弦相似度；数据库向量已经归一化
- 文本编码：UTF-8
- 《周礼》简繁：Kanripo 原文为繁体；`rag_pipeline.py normalize` 阶段统一 OpenCC `t2s` 转简体

首次检索需要下载并加载嵌入模型。模型缓存约 92 MB；数据库约 47 MB；向量矩阵原始内存约 24 MB。Python 与模型框架本身还会占用额外磁盘和运行内存。

## 数据来源与许可

1. 四书五经 / 论语 / 诗经语料整理自 `chinese-poetry`：
   - 项目地址：`https://github.com/chinese-poetry/chinese-poetry`
   - 上游许可：MIT License
   - 上游版权声明：Copyright (c) 2016 JackeyGao
   - 发布包含转换后语料或向量数据库副本时，保留 [chinese-poetry-LICENSE.txt](chinese-poetry-LICENSE.txt)

2. 《周礼》正文整理自 Kanripo：
   - 仓库：`https://github.com/kanripo/KR1d0001`
   - 本地 raw：`data/raw/zhouli/kanripo/`
   - 转换脚本：`scripts/convert_zhouli_kanripo.py`
   - 规范化 JSON：`chinese-poetry-master/周礼/zhouli.json`

向量结果可能出现误匹配；最终引用必须由模型结合原句和元数据判断，不能仅依据分数。

## 路径配置

检索脚本依次查找：

1. 命令行 `--db` 指定的文件。
2. 环境变量 `ZHOU_LI_RAG_DB` 指定的文件。
3. Skill 内的 `data/poetry_embeddings.sqlite`。
4. 开发目录根级的 `data/rag/poetry_embeddings.sqlite`。

因此公开仓库可以直接捆带数据库，也可以只发布脚本，由使用者通过环境变量连接自己的兼容数据库。
