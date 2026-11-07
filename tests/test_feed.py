"""Unit tests for OpenGSA RSS 2.0 Feed generation and deadline notifications."""
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
import tempfile
from urllib.parse import parse_qs, urlsplit
import unittest
import xml.etree.ElementTree as ET
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_feed import build_feeds
from scripts.build_site import load_full_library
from scripts.radar_metadata import known_hand_authored


class RSSFeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates, cls.observations = load_full_library(ROOT)
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls.temp_dir.name)
        cls.main_file, cls.deadlines_file = build_feeds(
            cls.output_dir, cls.candidates["candidates"], cls.observations
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_main_feed_structure_and_coverage(self):
        """Verifies that feed.xml is valid RSS 2.0 and covers all 254 schemes."""
        self.assertTrue(self.main_file.exists())
        tree = ET.parse(self.main_file)
        root = tree.getroot()
        self.assertEqual(root.tag, "rss")
        self.assertEqual(root.attrib.get("version"), "2.0")

        channel = root.find("channel")
        self.assertIsNotNone(channel)
        self.assertIn("OpenGSA", channel.find("title").text)
        self.assertEqual(channel.find("language").text, "zh-TW")

        last_build = channel.find("lastBuildDate").text
        parsed_build_date = parsedate_to_datetime(last_build)
        self.assertIsInstance(parsed_build_date, datetime)

        items = channel.findall("item")
        self.assertEqual(len(items), 254, "All 254 candidates must be present in the main feed")

        for item in items:
            title = item.find("title").text
            link = item.find("link").text
            guid = item.find("guid").text
            pub_date = item.find("pubDate").text
            desc = item.find("description").text

            self.assertTrue(title and len(title.strip()) > 0)
            self.assertTrue(link.startswith("https://opengsa.mattye.dev/?tab=detail&id="))
            self.assertTrue(guid and len(guid.strip()) > 0)
            self.assertTrue(desc and "【身分資格】" in desc)

            # Ensure pubDate conforms to RFC 822 / 2822
            parsed_dt = parsedate_to_datetime(pub_date)
            self.assertIsInstance(parsed_dt, datetime)

            # Verify no undefined or raw None leakages
            for text in (title, link, guid, desc):
                self.assertNotIn("undefined", text)
                self.assertNotIn("None", text)

    def test_item_links_open_the_matching_document_on_the_page(self):
        """The page keys each document by candidate_id; any other id silently opens a different item."""
        page_ids = {cand["candidate_id"] for cand in self.candidates["candidates"]}
        for feed_file in (self.main_file, self.deadlines_file):
            for item in ET.parse(feed_file).getroot().find("channel").findall("item"):
                query = parse_qs(urlsplit(item.find("link").text).query)
                self.assertEqual(query["tab"], ["detail"])
                self.assertIn(query["id"][0], page_ids)
                self.assertTrue(item.find("guid").text.startswith(query["id"][0]))

    def test_hand_authored_items_carry_a_warning_and_extracted_items_do_not(self):
        known = known_hand_authored()
        items = ET.parse(self.main_file).getroot().find("channel").findall("item")
        for item in items:
            warned = item.find("description").text.startswith("⚠ 尚未經來源查證")
            self.assertEqual(warned, item.find("guid").text in known, item.find("guid").text)

    def test_deadlines_feed_filtering_and_formatting(self):
        """Verifies that feed-deadlines.xml contains only verified deadlines with countdown markers."""
        self.assertTrue(self.deadlines_file.exists())
        tree = ET.parse(self.deadlines_file)
        root = tree.getroot()
        channel = root.find("channel")
        self.assertIsNotNone(channel)

        items = channel.findall("item")
        self.assertGreater(len(items), 0, "Must contain items with confirmed deadlines")
        self.assertLessEqual(len(items), 254)

        for item in items:
            title = item.find("title").text
            desc = item.find("description").text
            self.assertTrue(title.startswith("⏱️ [即將截止]"))
            self.assertIn("【申請截止提醒：", desc)

    def test_feed_ordering_by_date(self):
        """Verifies that items in both feeds are ordered descending by publication/observation date."""
        for feed_file in (self.main_file, self.deadlines_file):
            tree = ET.parse(feed_file)
            channel = tree.getroot().find("channel")
            dates = [parsedate_to_datetime(it.find("pubDate").text) for it in channel.findall("item")]
            self.assertEqual(dates, sorted(dates, reverse=True), f"Items in {feed_file.name} must be sorted desc")


if __name__ == "__main__":
    unittest.main()
