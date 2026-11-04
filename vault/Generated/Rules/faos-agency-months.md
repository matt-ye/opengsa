---
entity_type: "rule"
entity_id: "faos-agency-months"
aliases: ["學校負責人向基金會申請：會議開始前兩個月；不換算為60天。"]
rule_kind: "relative_deadline"
actor: "institution"
scope: "nationwide"
cycle: "current"
review_status: "pending"
managed: true
tags: ["opengsa/rule"]
---

# 學校負責人向基金會申請：會議開始前兩個月；不換算為60天。

> [!info] 自動產生的資料檢視
> 正式來源是 repo 的 JSON；請把人工補充寫入 Reviews。改動此頁會令重建停止，不會被靜默覆寫。

[[Generated/Programs/faos-student-conference|傑出人才基金會優秀學生出國開會補助]]

## 結構化欄位

```json
{
  "anchor": "conference_start",
  "offset": -2,
  "unit": "calendar_month",
  "holiday_adjustment": "not_stated"
}
```

## 證據

- [[Generated/Sources/doc-8dbd63e96b3f5bba3534bc8b|基金會補助辦法（113.05.29）]] · body / text-block 20
  - revision: `abf6d15b5df5056771260b933a378ab681686093c23a8376693e3fe37acbbd0f`
  - block hash: `7312985328050df2ec04f6517abe0e14326dac557fc8817aca43174b3746b6d5`
