import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from sqlite_utils import Database

OUTPUT = Path("staticevolution.db")
PUBLIC_NOW = "created <= now()"
PUBLIC_TAG_IDS = """
SELECT x.tag_id FROM blog_entry_tags x JOIN blog_entry p ON p.id = x.entry_id
WHERE NOT p.is_draft AND p.created <= now()
UNION SELECT x.tag_id FROM blog_blogmark_tags x JOIN blog_blogmark p ON p.id = x.blogmark_id
WHERE NOT p.is_draft AND p.created <= now()
UNION SELECT x.tag_id FROM blog_quotation_tags x JOIN blog_quotation p ON p.id = x.quotation_id
WHERE NOT p.is_draft AND p.created <= now()
UNION SELECT x.tag_id FROM blog_note_tags x JOIN blog_note p ON p.id = x.note_id
WHERE NOT p.is_draft AND p.created <= now()
UNION SELECT x.tag_id FROM guides_chapter_tags x
JOIN guides_chapter c ON c.id = x.chapter_id JOIN guides_guide g ON g.id = c.guide_id
WHERE NOT c.is_draft AND NOT c.is_unlisted AND NOT g.is_draft AND c.created <= now()
"""
TABLES = {
    "blog_entry": f"""
        SELECT id, created, slug, card_image, series_id, title, body, tweet_html,
               extra_head_html
        FROM blog_entry WHERE NOT is_draft AND {PUBLIC_NOW}
    """,
    "blog_blogmark": f"""
        SELECT id, created, slug, card_image, series_id, link_url, link_title,
               title, via_url, via_title, commentary, use_markdown
        FROM blog_blogmark WHERE NOT is_draft AND {PUBLIC_NOW}
    """,
    "blog_quotation": f"""
        SELECT id, created, slug, card_image, series_id, quotation, source,
               source_url, context
        FROM blog_quotation WHERE NOT is_draft AND {PUBLIC_NOW}
    """,
    "blog_note": f"""
        SELECT id, created, slug, card_image, series_id, body, title
        FROM blog_note WHERE NOT is_draft AND {PUBLIC_NOW}
    """,
    "blog_liveupdate": """
        SELECT u.id, u.created, u.content, u.entry_id
        FROM blog_liveupdate u JOIN blog_entry e ON e.id = u.entry_id
        WHERE NOT e.is_draft AND e.created <= now()
    """,
    "blog_series": """
        SELECT s.id, s.created, s.slug, s.title, s.summary
        FROM blog_series s WHERE EXISTS (
            SELECT 1 FROM blog_entry e
            WHERE e.series_id = s.id AND NOT e.is_draft AND e.created <= now()
        )
    """,
    "blog_photo": """
        SELECT id, created, title, alt_text, caption, width, height
        FROM blog_photo WHERE NOT is_draft
    """,
    "blog_photoset": """
        SELECT id, created, title, description, slug, primary_id
        FROM blog_photoset WHERE NOT is_draft
    """,
    "guides_guide": """
        SELECT id, created, updated, title, slug, description
        FROM guides_guide WHERE NOT is_draft
    """,
    "guides_guidesection": """
        SELECT s.id, s.guide_id, s.title, s.slug, s.order
        FROM guides_guidesection s JOIN guides_guide g ON g.id = s.guide_id
        WHERE NOT g.is_draft
    """,
    "guides_chapter": """
        SELECT c.id, c.created, c.slug, c.card_image, c.series_id, c.guide_id,
               c.section_id, c.updated, c.title, c.body, c.order
        FROM guides_chapter c JOIN guides_guide g ON g.id = c.guide_id
        WHERE NOT c.is_draft AND NOT c.is_unlisted AND NOT g.is_draft
              AND c.created <= now()
    """,
    "guides_chapterchange": """
        SELECT h.id, h.chapter_id, h.created, h.title, h.body, h.is_notable,
               h.change_note
        FROM guides_chapterchange h
        JOIN guides_chapter c ON c.id = h.chapter_id
        JOIN guides_guide g ON g.id = c.guide_id
        WHERE NOT h.is_draft AND NOT c.is_draft AND NOT c.is_unlisted
              AND NOT g.is_draft AND c.created <= now()
    """,
    "pages_page": """
        SELECT id, title, slug, body, meta_description FROM pages_page
        WHERE status = 'published'
              AND slug IN ('consulting', 'about', 'contact', 'privacy',
                           'terms', 'support')
    """,
    "products_product": """
        SELECT id, name, slug, summary, body, platform_links, support_url,
               featured, redirect_to_id, meta_description
        FROM products_product WHERE status = 'published'
    """,
    "blog_entry_tags": f"SELECT x.id, x.entry_id, x.tag_id FROM blog_entry_tags x JOIN blog_entry p ON p.id = x.entry_id WHERE NOT p.is_draft AND {PUBLIC_NOW}",
    "blog_blogmark_tags": f"SELECT x.id, x.blogmark_id, x.tag_id FROM blog_blogmark_tags x JOIN blog_blogmark p ON p.id = x.blogmark_id WHERE NOT p.is_draft AND {PUBLIC_NOW}",
    "blog_quotation_tags": f"SELECT x.id, x.quotation_id, x.tag_id FROM blog_quotation_tags x JOIN blog_quotation p ON p.id = x.quotation_id WHERE NOT p.is_draft AND {PUBLIC_NOW}",
    "blog_note_tags": f"SELECT x.id, x.note_id, x.tag_id FROM blog_note_tags x JOIN blog_note p ON p.id = x.note_id WHERE NOT p.is_draft AND {PUBLIC_NOW}",
    "guides_chapter_tags": "SELECT x.id, x.chapter_id, x.tag_id FROM guides_chapter_tags x JOIN guides_chapter c ON c.id = x.chapter_id JOIN guides_guide g ON g.id = c.guide_id WHERE NOT c.is_draft AND NOT c.is_unlisted AND NOT g.is_draft AND c.created <= now()",
    "blog_photoset_photos": "SELECT x.id, x.photoset_id, x.photo_id FROM blog_photoset_photos x JOIN blog_photoset s ON s.id = x.photoset_id JOIN blog_photo p ON p.id = x.photo_id WHERE NOT s.is_draft AND NOT p.is_draft",
    "blog_tag": f"SELECT t.id, t.tag, t.description FROM blog_tag t WHERE t.id IN ({PUBLIC_TAG_IDS})",
    "blog_previoustagname": f"SELECT p.id, p.tag_id, p.previous_name FROM blog_previoustagname p WHERE p.tag_id IN ({PUBLIC_TAG_IDS})",
}


def normalize(value):
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, memoryview):
        return bytes(value)
    return value


def main():
    database_url = os.environ["DATABASE_URL"]
    OUTPUT.unlink(missing_ok=True)
    destination = Database(OUTPUT)
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        for table, query in TABLES.items():
            rows = [
                {key: normalize(value) for key, value in row.items()}
                for row in connection.execute(query)
            ]
            if rows:
                destination[table].insert_all(rows, pk="id", replace=True)
    destination.vacuum()


if __name__ == "__main__":
    main()
