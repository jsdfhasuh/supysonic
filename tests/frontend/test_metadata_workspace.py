import unittest
from pathlib import Path


class MetadataWorkspaceTemplateTestCase(unittest.TestCase):
    def test_layout_has_metadata_nav_link(self):
        templatePath = Path(__file__).resolve().parents[2] / "supysonic" / "templates" / "layout.html"
        template = templatePath.read_text(encoding="utf-8")

        self.assertIn("url_for('frontend.metadata')", template)
        self.assertIn('data-i18n-en="Metadata"', template)

    def test_metadata_workspace_has_tabs_and_empty_inbox(self):
        templatePath = Path(__file__).resolve().parents[2] / "supysonic" / "templates" / "metadata-workspace.html"
        inboxPartialPath = Path(__file__).resolve().parents[2] / "supysonic" / "templates" / "partials" / "metadata-inbox-content.html"
        template = templatePath.read_text(encoding="utf-8")
        inboxPartial = inboxPartialPath.read_text(encoding="utf-8")

        self.assertIn("Inbox", template)
        self.assertIn("Artists", template)
        self.assertIn("Albums", template)
        self.assertIn("No pending review tasks yet", inboxPartial)
        self.assertIn("Review", inboxPartial)
        self.assertIn("Confirm", inboxPartial)
        self.assertIn("Dismiss", inboxPartial)
        self.assertIn("url_for('frontend.metadata', tab='inbox')", template)
        self.assertIn("url_for('frontend.metadata', tab='artists')", template)
        self.assertIn("url_for('frontend.metadata', tab='albums')", template)
        self.assertIn("activeTab == 'artists'", template)
        self.assertIn("activeTab == 'albums'", template)
        self.assertNotIn("<iframe", template)
        self.assertIn("metadata-workspace-panel", template)
        self.assertIn('<div class="card mb-4">', template)
        self.assertIn('<div id="metadata-workspace-content">', template)
        self.assertNotIn('<div class="pt-4" id="metadata-workspace-content">', template)

        tabsCardPos = template.index('<div class="card mb-4">')
        contentPos = template.index('<div id="metadata-workspace-content">')
        self.assertGreater(contentPos, tabsCardPos)

    def test_embedded_metadata_templates_do_not_extend_layout(self):
        artistTemplatePath = Path(__file__).resolve().parents[2] / "supysonic" / "templates" / "metadata-embedded.html"
        albumTemplatePath = Path(__file__).resolve().parents[2] / "supysonic" / "templates" / "metadata-album-embedded.html"

        artistTemplate = artistTemplatePath.read_text(encoding="utf-8")
        albumTemplate = albumTemplatePath.read_text(encoding="utf-8")

        self.assertNotIn('{% extends "layout.html" %}', artistTemplate)
        self.assertNotIn('{% extends "layout.html" %}', albumTemplate)
        self.assertIn("bootstrap.min.css", artistTemplate)
        self.assertIn("supysonic.css", artistTemplate)
        self.assertIn("metadata.css", artistTemplate)
        self.assertIn("bootstrap.min.css", albumTemplate)
        self.assertIn("supysonic.css", albumTemplate)
        self.assertIn("metadata.css", albumTemplate)

    def test_artist_metadata_template_has_primary_artist_autocomplete_hooks(self):
        artistTemplatePath = Path(__file__).resolve().parents[2] / "supysonic" / "templates" / "partials" / "metadata-artist-content.html"
        cssPath = Path(__file__).resolve().parents[2] / "supysonic" / "static" / "css" / "metadata.css"
        autocompleteJsPath = Path(__file__).resolve().parents[2] / "supysonic" / "static" / "js" / "artist-autocomplete.js"

        artistTemplate = artistTemplatePath.read_text(encoding="utf-8")
        css = cssPath.read_text(encoding="utf-8")
        autocompleteJs = autocompleteJsPath.read_text(encoding="utf-8") if autocompleteJsPath.exists() else ""

        self.assertIn("primary-artist-suggestions", artistTemplate)
        self.assertIn("artist-autocomplete.js", artistTemplate)
        self.assertIn("url_for('frontend.metadata_artist_suggestions')", artistTemplate)
        self.assertIn("upsertArtistCard", artistTemplate)
        self.assertIn("applyArtistModalChanges", artistTemplate)
        self.assertNotIn("showSuccessToast(successData.message);\n        loadData();", artistTemplate)
        self.assertIn(".list-group-item.active", css)
        self.assertIn("No matching artists found", autocompleteJs)
        self.assertIn("setTimeout", autocompleteJs)
        self.assertIn("Searching artists...", autocompleteJs)
        self.assertIn("artist-autocomplete-match", autocompleteJs)
