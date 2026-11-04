---
entity_type: "rule"
entity_id: "nstc-conference-institution"
aliases: ["機構彙送：會議首日所屬月份前一個月的首日；遇例假日順延至次一上班日。"]
rule_kind: "relative_deadline"
actor: "institution"
scope: "nationwide"
cycle: "112-03-16"
review_status: "pending"
managed: true
tags: ["opengsa/rule"]
---

# 機構彙送：會議首日所屬月份前一個月的首日；遇例假日順延至次一上班日。

> [!info] 自動產生的資料檢視
> 正式來源是 repo 的 JSON；請把人工補充寫入 Reviews。改動此頁會令重建停止，不會被靜默覆寫。

[[Generated/Programs/nstc-grad-conference-policy|國科會研究生國際會議補助]]

## 結構化欄位

```json
{
  "anchor": "conference_start_month_first",
  "offset": -1,
  "unit": "calendar_month",
  "holiday_adjustment": "next_working_day"
}
```

## 證據

- [[Generated/Sources/doc-f86ed6a15af02d63eae87cfe|國科會會議補助作業要點]] · body / text-block 45
  - revision: `d1f01d4eec7239af743f5cdcaf441b8747acb13fcd35128028c086a19def163e`
  - block hash: `ae9066abd4df5ce17883074d95947b5286ea3dc39278176ba82cce2bc605182b`
