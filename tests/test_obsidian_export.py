"""Linked-note exports and file-ownership boundaries; all checks are offline."""
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from scripts.export_obsidian_vault import ROOT,MANIFEST,build_files,export_vault,fingerprint

class ObsidianExportTests(unittest.TestCase):
    def test_registry_sources_deduplicated_and_restrictions_preserved(self):
        files,queue=build_files()
        original=json.loads((ROOT/'data/audits/source-coverage-2026-10-31.json').read_text(encoding='utf-8'))['rows']
        urls={x['url'] for x in queue['items']}
        self.assertEqual(len(urls),len(queue['items']))
        self.assertTrue({r['url'] for r in original}<=urls)
        self.assertEqual(len(queue['items']),184)
        self.assertEqual(queue['counts']['manual_only'],37)
        self.assertEqual(queue['counts']['ready'],13)
        self.assertTrue(all(q['raw_retention']=='memory_only' and q['requires_fresh_robots_check'] and q['model_mode']=='off' for q in queue['items']))

    def test_wikilinks_and_canvas_resolve_to_real_files(self):
        files,_=build_files()
        for path,text in files.items():
            if not path.endswith('.md'):continue
            for target in re.findall(r'\[\[([^]|]+)(?:\|[^]]*)?\]\]',text):
                candidate=target if Path(target).suffix in ('.md','.canvas','.base') else target+'.md'
                self.assertTrue(candidate in files or (ROOT/'vault'/candidate).exists(),(path,candidate))
        graph=json.loads(files['Maps/來源資訊鏈.canvas'])
        self.assertEqual(sum(n['type']=='file' for n in graph['nodes']),71)
        self.assertTrue(all(n['file'] in files and 'text' not in n for n in graph['nodes'] if n['type']=='file'))

    def test_export_is_idempotent_and_offline(self):
        with TemporaryDirectory() as directory,patch('scripts.scan_sources.Fetcher.get',side_effect=AssertionError('unexpected network')):
            first=export_vault(directory);second=export_vault(directory,check=True)
            self.assertGreater(first['changed'],0);self.assertEqual(second['changed'],0);self.assertEqual(second['network_requests'],0)

    def test_edited_generated_note_blocks_all_writes(self):
        with TemporaryDirectory() as directory:
            export_vault(directory);root=Path(directory)
            note=root/'Generated/Programs/faos-student-conference.md';note.write_text('SYNTH manual change',encoding='utf-8')
            before=(root/'00-首頁.md').read_bytes()
            with self.assertRaisesRegex(ValueError,'edited_generated_file'):export_vault(directory)
            self.assertEqual(note.read_text(encoding='utf-8'),'SYNTH manual change')
            self.assertEqual(before,(root/'00-首頁.md').read_bytes())

    def test_manual_notes_not_overwritten_or_removed_by_manifest_path(self):
        with TemporaryDirectory() as directory:
            export_vault(directory);root=Path(directory);private=root/'Reviews/private.md';private.parent.mkdir();private.write_text('SYNTH PRIVATE',encoding='utf-8')
            base=root/'Views/custom.base';base.write_text('SYNTH VIEW',encoding='utf-8')
            export_vault(directory);self.assertEqual(private.read_text(),'SYNTH PRIVATE')
            self.assertEqual(base.read_text(),'SYNTH VIEW')
            path=root/MANIFEST;manifest=json.loads(path.read_text(encoding='utf-8'));manifest['files']['Generated/../Reviews/private.md']=fingerprint('SYNTH PRIVATE');path.write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'unsafe_generated_path'):export_vault(directory)
            self.assertEqual(private.read_text(),'SYNTH PRIVATE')

    def test_stale_unmodified_owned_files_only_are_removed(self):
        with TemporaryDirectory() as directory:
            export_vault(directory);root=Path(directory);files,queue=build_files();old='Generated/Rules/faos-ntu-contact.md';files.pop(old)
            with patch('scripts.export_obsidian_vault.build_files',return_value=(files,queue)):
                result=export_vault(directory)
            self.assertEqual(result['stale'],1);self.assertFalse((root/old).exists())

    def test_native_canvas_formatting_allowed_but_content_edit_blocked(self):
        with TemporaryDirectory() as directory:
            export_vault(directory);path=Path(directory)/'Maps/來源資訊鏈.canvas'
            graph=json.loads(path.read_text(encoding='utf-8'))
            path.write_text(json.dumps(graph,ensure_ascii=False,indent='\t',sort_keys=True),encoding='utf-8')
            self.assertEqual(export_vault(directory,check=True)['changed'],0)
            graph['nodes'][0]['x']+=10
            path.write_text(json.dumps(graph),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'edited_generated_file'):export_vault(directory)
