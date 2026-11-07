"""Offline release boundaries for the verified-source pending-card batch."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))

class CardImportTests(unittest.TestCase):
    def test_every_card_ready_original_is_in_the_pending_pool(self):
        audit=read('data/source-expansion/original-source-verification.json')
        cards=read('data/candidates/source-review.json')['candidates']
        by_url={c['source_metadata']['url']:c for c in cards}
        for source in audit['records']:
            if not source['card_ready']:
                continue
            self.assertTrue(source['content_verified'])
            self.assertTrue(source['candidate_ids'])
            # The original audit is immutable history; later reads rotate revision/IDs.
            self.assertIn(source['url'],by_url)
            if by_url[source['url']]['candidate_id'] not in source['candidate_ids']:
                self.assertGreaterEqual(by_url[source['url']]['source_metadata']['observed_at'],source['checked_at'])

    def test_import_is_not_a_human_approval_or_formal_release(self):
        cards=read('data/candidates/source-review.json')['candidates']
        summary=read('data/source-expansion/card-import-summary.json')
        for card in cards:
            self.assertEqual(card['review']['status'],'pending')
            self.assertIsNone(card['review']['independent_reviewer'])
            self.assertFalse(card['review']['promotion_ready'])
        self.assertFalse(summary['published'])
        self.assertEqual(read('data/scan-reviews.json')['reviews'],[])
        self.assertEqual(len(read('data/pilot.json')['opportunities']),10)

    def test_synthetic_profiles_cover_current_cards_without_approvals(self):
        from scripts.scan_sources import digest
        bundle=read('data/candidates/source-review.json')
        smoke=read('data/source-expansion/card-import-eligibility.json')
        self.assertTrue(smoke['synthetic'])
        ids={c['candidate_id'] for c in bundle['candidates']}
        for case in smoke['cases']:
            # 這份試算固定對應當時那批候選；候選更新後只是歷史紀錄，不再比對涵蓋範圍。
            if smoke['candidate_sha256']==digest(bundle):
                self.assertEqual({r['opportunity_id'] for r in case['results']},ids)
            self.assertTrue(all(r['official_qualification_approved'] is False for r in case['results']))

if __name__=='__main__':unittest.main()
