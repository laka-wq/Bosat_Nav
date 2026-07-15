import argparse
import os
import re
import sys
from collections import Counter

import fitz  # PyMuPDF


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


def _normalize_whitespace(value):
    return re.sub(r"\s+", " ", value).strip()


def _title_search_variants(title):
    cleaned = _normalize_whitespace(re.sub(r"[()\[\]{}.,;:!?]", " ", title))
    words = [word for word in cleaned.split(" ") if word]
    stopwords = {
        "a", "an", "and", "as", "at", "by", "for", "from", "in", "of",
        "on", "or", "the", "to", "with", "that", "this", "is", "are"
    }

    variants = []
    seen = set()

    def add_variant(value):
        value = _normalize_whitespace(value)
        if len(value) < 3 or value.lower() in seen:
            return
        seen.add(value.lower())
        variants.append(value)

    add_variant(title)
    add_variant(cleaned)

    content_words = [word for word in words if word.lower() not in stopwords]

    for size in range(min(6, len(words)), 0, -1):
        add_variant(" ".join(words[:size]))
        add_variant(" ".join(words[-size:]))

    for size in range(min(5, len(content_words)), 0, -1):
        for start in range(0, len(content_words) - size + 1):
            add_variant(" ".join(content_words[start:start + size]))

    for start in range(0, max(0, len(words) - 2)):
        for size in range(min(5, len(words) - start), 2, -1):
            add_variant(" ".join(words[start:start + size]))

    return variants


def _find_toc_title_rect(page, title):
    for phrase in _title_search_variants(title):
        rects = page.search_for(phrase)
        if rects:
            return rects[0], phrase
    return None, None


def _resolve_page_offset(doc, toc_page_idx, toc_entries):
    total_pages = len(doc)
    sorted_entries = sorted(toc_entries, key=lambda x: x["printed_page"])
    candidates = []

    for entry in sorted_entries[: min(5, len(sorted_entries))]:
        query = entry["title"][:30].strip()
        if len(query) < 5:
            continue

        for idx in range(toc_page_idx + 1, total_pages):
            page_text = doc[idx].get_text("text")
            if query.lower() in page_text.lower() or doc[idx].search_for(query):
                candidate = idx - entry["printed_page"] + 1
                if candidate > 0:
                    candidates.append(candidate)
                break

    if candidates:
        return Counter(candidates).most_common(1)[0][0]

    return toc_page_idx + 1


def extract_toc_and_analyze(doc):
    toc_page_idx = None
    toc_text = ""
    total_pages = len(doc)

    for idx in range(min(10, total_pages)):
        page_text = doc[idx].get_text("text")
        upper_text = page_text.upper()
        if "TABLE OF CONTENTS" in upper_text or "CONTENTS" in upper_text:
            toc_page_idx = idx
            toc_text = page_text
            break

    if toc_page_idx is None:
        raise ValueError("Could not automatically locate a 'CONTENTS' page in the PDF.")

    print(f"[Auto-Detect] Found Table of Contents on absolute PDF Page: {toc_page_idx + 1}")

    lines = [line.strip() for line in toc_text.split('\n') if line.strip()]

    toc_entries = []
    current_title_parts = []

    ignore_keywords = [
        "THE BOSAT", "NEW SERIES", "PAGE SETTING",
        "VOL:", "NO:", "VOLUME", "ISSUE", "PUBLICATION",
        "CHANDRANI", "MEDIUM OR FORMAT", "CONTENTS"
    ]

    found_contents_header = False

    for line in lines:
        line_clean = line.strip().strip('"').strip(',').strip('"').strip()
        if not line_clean:
            continue

        if line_clean.upper() == "CONTENTS":
            current_title_parts = []
            found_contents_header = True
            continue

        if not found_contents_header:
            continue

        if line_clean.isdigit():
            p_num = int(line_clean)
            if 0 < p_num <= total_pages:
                full_title = _normalize_whitespace(" ".join(current_title_parts))

                if full_title and not any(k in full_title.upper() for k in ignore_keywords):
                    toc_entries.append({
                        "title": full_title,
                        "printed_page": p_num
                    })
            current_title_parts = []

        else:
            match = re.search(r'^(.*\D)\s+(\d+)$', line_clean)
            if match:
                title_part = match.group(1).strip().strip('"').strip('.').strip()
                p_num = int(match.group(2))

                if title_part:
                    current_title_parts.append(title_part)
                full_title = _normalize_whitespace(" ".join(current_title_parts))

                if 0 < p_num <= total_pages:
                    if full_title and not any(k in full_title.upper() for k in ignore_keywords):
                        toc_entries.append({
                            "title": full_title,
                            "printed_page": p_num
                        })
                current_title_parts = []
            else:
                current_title_parts.append(line_clean)

    if not toc_entries:
        raise ValueError("Failed to parse any valid structural titles from the TOC page layout.")

    print(f"[Auto-Detect] Successfully extracted {len(toc_entries)} valid articles from the TOC.")

    page_offset = _resolve_page_offset(doc, toc_page_idx, toc_entries)

    print(f"[Auto-Detect] Determined dynamic page offset layout is: {page_offset}")
    return toc_page_idx, toc_entries, page_offset


def automate_any_month_pdf(input_filename, output_filename=None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = input_filename if os.path.isabs(input_filename) else os.path.join(base_dir, input_filename)
    input_path = os.path.abspath(input_path)

    if output_filename:
        output_path = output_filename if os.path.isabs(output_filename) else os.path.join(base_dir, output_filename)
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        output_name_for_log = os.path.basename(output_path)
    else:
        output_name_for_log = os.path.splitext(os.path.basename(input_path))[0] + "_Navigated.pdf"
        output_dir = os.path.dirname(input_path) or base_dir
        output_path = os.path.join(output_dir, output_name_for_log)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"File not found at {input_path}")

    doc = fitz.open(input_path)
    total_pages = len(doc)

    try:
        toc_page_idx, toc_entries, page_offset = extract_toc_and_analyze(doc)
    except Exception:
        doc.close()
        raise

    toc_page = doc[toc_page_idx]
    sorted_entries = sorted(toc_entries, key=lambda x: x['printed_page'])
    back_linked_pages = set()

    for i, entry in enumerate(sorted_entries):
        title = entry['title']
        printed_start = entry['printed_page']

        abs_start_page = printed_start + page_offset - 1

        if i < len(sorted_entries) - 1:
            abs_end_page = (sorted_entries[i + 1]['printed_page'] + page_offset - 1) - 1
        else:
            abs_end_page = total_pages - 1

        if abs_start_page >= total_pages or abs_end_page >= total_pages or abs_start_page < 0:
            continue

        safe_title = title[:40].encode("ascii", "backslashreplace").decode("ascii")
        print(f" -> Linking: '{safe_title}...' (Absolute Pages {abs_start_page + 1} to {abs_end_page + 1})")

        rect, matched_phrase = _find_toc_title_rect(toc_page, title)

        if rect:
            rect = fitz.Rect(rect.x0 - 1, rect.y0 - 1, rect.x1 + 1, rect.y1 + 1)
            link_to_article = {
                "kind": fitz.LINK_GOTO,
                "from": rect,
                "page": abs_start_page,
                "to": fitz.Point(0, 0)
            }
            toc_page.insert_link(link_to_article)

            try:
                fontsize = 11
                fontname = "helv"
                color_blue = (0, 0.2, 0.8)
                bbox = rect
                toc_page.insert_textbox(
                    bbox,
                    matched_phrase,
                    fontsize=fontsize,
                    color=color_blue,
                    fontname=fontname,
                    align=0,
                )

                underline_y = bbox.y1 - 2
                toc_page.draw_line(
                    fitz.Point(bbox.x0, underline_y),
                    fitz.Point(bbox.x1, underline_y),
                    color=color_blue,
                    width=0.8,
                )
            except Exception:
                pass
        else:
            safe_title = title[:40].encode("ascii", "backslashreplace").decode("ascii")
            print(f"    [Warning] Could not find TOC text rect for: '{safe_title}'")

        if 0 <= abs_end_page < total_pages and abs_end_page not in back_linked_pages:
            target_page = doc[abs_end_page]
            page_width = target_page.rect.width
            page_height = target_page.rect.height

            link_text = "Go to Table of Contents"
            fontsize = 10
            text_width = fitz.get_text_length(link_text, fontname="helv", fontsize=fontsize)
            padding_x = 6
            padding_y = 4
            rect_width = text_width + (padding_x * 2)
            rect_height = fontsize + (padding_y * 2)
            text_x = max(12, page_width - rect_width - 18)
            text_y = page_height - rect_height - 14
            text_rect = fitz.Rect(text_x, text_y, text_x + rect_width, text_y + rect_height)

            target_page.insert_textbox(
                text_rect,
                link_text,
                fontsize=fontsize,
                color=(0, 0.2, 0.8),
                fontname="helv",
                align=0,
            )

            link_back_to_toc = {
                "kind": fitz.LINK_GOTO,
                "from": text_rect,
                "page": toc_page_idx,
                "to": fitz.Point(0, 0)
            }
            target_page.insert_link(link_back_to_toc)
            back_linked_pages.add(abs_end_page)

    doc.save(output_path, deflate=True)
    doc.close()
    print(f"[Success] Processed file saved as: {output_name_for_log}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate a navigated PDF from a raw PDF.")
    parser.add_argument("--input", required=True, help="Path to the input raw PDF")
    parser.add_argument("--output", required=False, help="Path to the output navigated PDF")
    args = parser.parse_args()

    output_path = automate_any_month_pdf(args.input, args.output)
    print(output_path)


if __name__ == "__main__":
    main()
