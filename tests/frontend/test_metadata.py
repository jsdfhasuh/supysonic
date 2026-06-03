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

    def test_artists_wall_has_search_filter(self):
        rootPath = Path(__file__).resolve().parents[2]
        templatePath = rootPath / "supysonic" / "templates" / "partials" / "metadata-artist-content.html"
        cssPath = rootPath / "supysonic" / "static" / "css" / "metadata.css"

        template = templatePath.read_text(encoding="utf-8")
        css = cssPath.read_text(encoding="utf-8")

        self.assertIn("id=\"artistSearchInput\"", template)
        self.assertIn("placeholder=\"Search artists...\"", template)
        self.assertIn("id=\"artistSearchCount\"", template)
        self.assertIn("filterArtistCards", template)
        self.assertIn("No matching artists found.", template)
        self.assertIn(".artist-search-bar", css)

    def test_album_modal_uses_show_class(self):
        templatePath = Path(__file__).resolve().parents[2] / "supysonic" / "templates" / "partials" / "metadata-album-content.html"
        template = templatePath.read_text(encoding="utf-8")

        self.assertIn("modal.classList.add('show');", template)
        self.assertIn("document.getElementById('editModal').classList.remove('show');", template)
        self.assertNotIn("document.getElementById('editModal').style.display = 'block';", template)

    def test_albums_wall_has_search_filter(self):
        rootPath = Path(__file__).resolve().parents[2]
        templatePath = rootPath / "supysonic" / "templates" / "partials" / "metadata-album-content.html"
        cssPath = rootPath / "supysonic" / "static" / "css" / "metadata.css"

        template = templatePath.read_text(encoding="utf-8")
        css = cssPath.read_text(encoding="utf-8")

        self.assertIn("id=\"albumSearchInput\"", template)
        self.assertIn("placeholder=\"Search albums...\"", template)
        self.assertIn("id=\"albumSearchCount\"", template)
        self.assertIn("filterAlbumCards", template)
        self.assertIn("No matching albums found.", template)
        self.assertIn(".album-search-bar", css)
