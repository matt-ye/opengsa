---
entity_type: "rule"
entity_id: "nstc-conference-supplement"
aliases: ["接受證明最遲會議首日前四週補送；僅適用已按期申請且註明補送者。"]
rule_kind: "relative_deadline"
actor: "student"
scope: "nationwide"
cycle: "112-03-16"
review_status: "pending"
managed: true
tags: ["opengsa/rule"]
---

# 接受證明最遲會議首日前四週補送；僅適用已按期申請且註明補送者。

> [!info] 自動產生的資料檢視
> 正式來源是 repo 的 JSON；請把人工補充寫入 Reviews。改動此頁會令重建停止，不會被靜默覆寫。

[[Generated/Programs/nstc-grad-conference-policy|國科會研究生國際會議補助]]

## 結構化欄位

```json
{
  "anchor": "conference_start",
  "offset": -4,
  "unit": "week",
  "condition": "original_application_submitted_on_time_and_marked_for_supplement"
}
```

## 證據

- [[Generated/Sources/doc-f86ed6a15af02d63eae87cfe|國科會會議補助作業要點]] · body / text-block 42
  - revision: `d1f01d4eec7239af743f5cdcaf441b8747acb13fcd35128028c086a19def163e`
  - block hash: `a84f387602a46a9d2be074cf1c49c1938907b67519c202b695061bb9ba9e7e57`
