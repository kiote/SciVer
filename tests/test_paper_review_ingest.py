import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_review.ingest import prepare
from paper_review.report import build
from paper_review.schema import digest
from paper_review.store import load, approved


@unittest.skipUnless(importlib.util.find_spec('pymupdf'), 'Install requirements-review.txt for PDF ingestion tests')
class GenericIngestTests(unittest.TestCase):
    def pdf(self):
        import pymupdf
        doc=pymupdf.open()
        page=doc.new_page()
        page.insert_text((72,72),'Synthetic research paper')
        page.insert_text((72,95),'PrivateSurname')
        page.insert_text((72,130),'Abstract')
        page.insert_text((72,160),'Model A outperforms Model B in every setting. Two settings are reported.')
        page.insert_text((72,205),'anonymous'+'@'+'example.invalid')
        page=doc.new_page()
        page.insert_text((72,72),'2 Results')
        page.insert_text((72,110),'Table 1 reports Model A 0.78 and Model B 0.84 for the first setting.')
        result=doc.tobytes();doc.close();return result

    def test_any_pdf_has_all_pages_units_images_and_no_implicit_upload_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'input.pdf';source.write_bytes(self.pdf())
            with patch('paper_review.store.WORK',base/'data'),patch('paper_review.report.OUT',base/'outputs'),patch('paper_review.report.ROOT',base):
                with patch('paper_review.pipeline.PiRpcClient') as model:
                    identifier=prepare(source,'generic-paper','Synthetic paper',['PrivateSurname'])
                    path,doc,state=load(identifier)
                    report=build(path,doc,state)
                    first=report.read_bytes();mtime=report.stat().st_mtime_ns
                    self.assertEqual(build(path,doc,state),report)
                    self.assertEqual(report.read_bytes(),first)
                    self.assertEqual(report.stat().st_mtime_ns,mtime)
                    model.assert_not_called()
                self.assertEqual(len(doc['pages']),2)
                self.assertEqual(doc['source_sha256'],digest(source.read_bytes()))
                self.assertTrue(all(p['units'] and (path/p['image']).exists() for p in doc['pages']))
                self.assertTrue(all(any(u['role']=='visual' for u in p['units']) for p in doc['pages']))
                self.assertFalse(any(approved(p,state) for p in doc['pages']))
                text=' '.join(u['text'] for p in doc['pages'] for u in p['units'])
                self.assertNotIn('PrivateSurname',text)
                self.assertNotIn('@',text)
                self.assertNotIn(str(source),str(doc['source_reference']))
                self.assertIn('The review is not complete.',report.read_text())

    def test_existing_history_not_overwritten_for_new_source(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'input.pdf';source.write_bytes(self.pdf())
            with patch('paper_review.store.WORK',base/'data'):
                prepare(source,'same-id')
                with self.assertRaisesRegex(ValueError,'differs'):
                    prepare(source,'same-id','New title')

    def test_source_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'input.pdf';source.write_bytes(self.pdf())
            with patch('paper_review.store.WORK',base/'data'):
                prepare(source,'check-source')
                (base/'data/check-source/original.pdf').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'Original PDF changed'):
                    load('check-source')

    def test_authenticated_url_rejected_before_network(self):
        with patch('paper_review.ingest.requests.get') as network:
            with self.assertRaisesRegex(ValueError,'Authenticated'):
                prepare('https://someone:password@example.invalid/paper.pdf')
            network.assert_not_called()
