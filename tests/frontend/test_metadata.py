import unittest
from pathlib import Path


class MetadataTemplateTestCase(unittest.TestCase):
    def test_artists_modal_uses_show_class(self):
        templatePath = Path(__file__).resolve().parents[2] / "supysonic" / "templates" / "partials" / "metadata-artist-content.html"
        template = templatePath.read_text(encoding="utf-8")

        self.assertIn("Primary artist name:", template)
        self.assertIn("Biography:", template)
        self.assertIn("Artist photo:", template)
        self.assertIn("id=\"biography\"", template)
        self.assertIn("id=\"artistPhoto\"", template)
        self.assertIn("new FormData()", template)
        self.assertIn("URL.createObjectURL", template)
        self.assertIn("artistPhotoInput.addEventListener('change'", template)
        self.assertNotIn("Canonical artist name:", template)
        self.assertIn("modal.classList.add('show');", template)
        self.assertIn("document.getElementById('editModal').classList.remove('show');", template)
        self.assertNotIn("modal.style.display = 'block';", template)

    def test_album_modal_uses_show_class(self):
        templatePath = Path(__file__).resolve().parents[2] / "supysonic" / "templates" / "partials" / "metadata-album-content.html"
        template = templatePath.read_text(encoding="utf-8")

        self.assertIn("modal.classList.add('show');", template)
        self.assertIn("document.getElementById('editModal').classList.remove('show');", template)
        self.assertNotIn("document.getElementById('editModal').style.display = 'block';", template)
