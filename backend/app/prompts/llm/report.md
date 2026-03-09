Generate only the report title and global summary for an AI daily report.
Return strict JSON only with keys: title, global_tldr.
Do not return markdown body content.
Keep factual info, avoid adding unverified claims.
Focus on the most important developments and cross-event trends.
Write `global_tldr` as 1-3 concise Chinese daily-brief sentences (about 60-140 Chinese characters total).
The tone must be a daily brief, not an academic abstract or research overview.
Do not use labels like "总结:" or "锐评:".
Do not include any count-style phrasing such as "收录/整理/共计 X 条".
Do not include category distribution phrasing such as "要闻 X 条，模型发布 Y 条".
Do not use label headers like "核心突破:" or "趋势洞察:"; write natural sentences directly.
Do not use academic wording such as "本报告围绕", "系统梳理", "本文基于", "研究基于", "结果显示".
Preferred structure: main storyline judgment first, 1-2 key signals next, one forward-looking focus last.

Current title: $title
Report date: $date
Current global TLDR: $global_tldr
Events (JSON):
$events_json
