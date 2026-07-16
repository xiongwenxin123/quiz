# 本地分级词汇与语法候选

## 目标

文章提取后，系统先在本地分级资料中匹配词汇和语法，再把最多 10 个
词汇候选和 6 个语法候选交给模型，最终最多保留 8 个词汇和 5 个语法目标。模型只负责判断语境是否合适、生成
语境义、摘要和题目表达，不再从全文自由猜测学习目标。

模型返回后还有确定性约束：

- 候选表外的词汇和语法会被移除；
- 词汇等级、lemma、读音、词性和句号以本地资料为准；
- 只选择目标等级上下一级的项目；
- 日语和西班牙语估计等级不会被描述为官方认证。

## 数据来源

| 语言 | 词汇 | 语法 | 等级性质 |
| --- | --- | --- | --- |
| 英语 | CEFR-J 1.5 + Octanove C1/C2 | CEFR-J Grammar Profile | Profile 等级 |
| 日语 | Waller/Japanese Language Data | Japanese Language Data | 社区 JLPT 估计，非官方 |
| 西班牙语 | OpenSLR 21 Spanish Gigaword | 本项目高精度表面规则 | 频率带 CEFR 估计 |

具体署名和许可证见 `src/polyglot_quiz/data/ATTRIBUTION.md`。西班牙语的
频率带边界是 A1 1000、A2 2500、B1 5000、B2 10000、C1 20000、C2
40000；它用于稳定排序候选，不代表 Instituto Cervantes 或 CEFR 官方词表。

## 更新资料

生成文件已压缩并随 Python 包安装，正常出题不联网。更新时执行：

```bash
.venv/bin/python scripts/fetch_learning_profiles.py
```

也可以复用已下载的 OpenSLR 压缩包：

```bash
.venv/bin/python scripts/fetch_learning_profiles.py \
  --spanish-archive /path/to/es_wordlist.json.tgz
```

脚本固定了英语与日语上游 Git revision；更新 revision 时应重新运行全部测试，
检查命中数量和许可证是否变化。

## 日志

`learning_targets_selected` 记录本地匹配耗时、候选数量和来源；
`analysis_targets_grounded` 记录模型返回后被拒绝或纠正的目标数量。日志不包含
整篇文章或完整候选内容。

## 局限

- 英语仅使用轻量规则处理复数、过去式和进行时，不等同于完整词形还原器；
- 西班牙语使用语料表面词形，等级受词频和新闻语域影响；
- JLPT 自 2010 年后没有官方词汇表，边界词可能存在争议；
- 日语语法只匹配至少三个连续字符，优先准确率，因此会主动漏掉短语法点。
