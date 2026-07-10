import os
import re
import pdfplumber

def clean_page_text(text, law_name):
    """
    Cleans up noise from the extracted page text, such as footers and headers.
    """
    if not text:
        return ""
    
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line_strip = line.strip()
        
        # Remove Law Ministry footer line: e.g. "법제처 1 국가법령정보센터"
        if "법제처" in line_strip and "국가법령정보센터" in line_strip:
            continue
            
        # Remove page header if it matches the official law name
        if line_strip == law_name:
            continue
            
        cleaned_lines.append(line)
        
    return "\n".join(cleaned_lines)

def join_wrapped_lines(text):
    """
    Joins PDF line-wrap artifacts where pdfplumber inserted a bare newline
    (no space) at a physical line break, splitting a word/어절 in two
    (e.g. "사\\n람" -> "사람", "각\\n호의" -> "각호의"). Only merges when both
    neighboring characters are Hangul syllables, and skips cases where the
    next line starts a 가./나./다. list marker or a "제N조(...)" article
    header, so structural boundaries (list items, and -- critically -- the
    start of the next article) are preserved. Without the article-header
    exclusion this used to merge e.g. "...재학하는 경우\n제22조(영리활동의
    범위)..." into "...경우제22조(영리활동의 범위)...", erasing the boundary
    the downstream article_pattern regex relies on and merging entire
    articles into one chunk (see docs/eval_results.md, issue 5).
    """
    return re.sub(r'(?<=[가-힣])\n(?=[가-힣])(?![가-힣]\.\s)(?!제\d+조)', '', text)

def parse_standard_law(pdf_path, law_name):
    """
    Parses standard military law documents (e.g., Act, Decree, Regulation).
    Extracts structured articles and their internal paragraphs.
    """
    if not os.path.exists(pdf_path):
        print(f"Error: File not found at {pdf_path}")
        return []

    # Step 1: Extract and clean text page-by-page
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            full_text += clean_page_text(page_text, law_name) + "\n"

    # Step 1.5: Repair PDF line-wrap artifacts before any pattern matching
    full_text = join_wrapped_lines(full_text)

    # Step 2: Strip revision history tags to keep the law text clean
    # Remove angle-bracket revision tags: e.g., <개정 2013. 6. 4., 2016. 5. 29.>
    full_text = re.sub(r'<[^>]*(?:개정|신설|삭제|일부개정|타법개정)[^>]*>', '', full_text)
    # Remove bracketed revision metadata: e.g., [전문개정 2009. 6. 9.] or [본조신설 ...]
    full_text = re.sub(r'\[(?:전문개정|본조신설|제목개정|대통령령제[^\]]+)[^\]]*\]', '', full_text)

    # Step 3: Match article headers: e.g., 제60조(병역판정검사 및 입영 등의 연기)
    # Group 1 captures Article No (e.g., 60 or 147조의2)
    # Group 2 captures Article Title (e.g., 병역판정검사 및 입영 등의 연기)
    article_pattern = re.compile(r'(?:^|\n)\s*(제\d+조(?:의\d+)*)\s*\(([^)]+)\)')

    articles = []
    # A genuine article title never itself contains a "제N조" reference --
    # only cross-reference qualifiers do (e.g. a numbered list item citing
    # "법 제46조(법 제54조제1항에서 준용하는 경우를 포함한다)" reads as a header
    # match otherwise, since the qualifier happens to sit in parens right
    # after the article number). Filtering those out avoids treating a
    # citation inside another article's body as a new article boundary.
    matches = [
        m for m in article_pattern.finditer(full_text)
        if not re.search(r'제\d+조', m.group(2))
    ]
    
    for idx, match in enumerate(matches):
        article_raw_no = match.group(1)
        article_title = match.group(2).strip()
        
        # Strip "제" and "조" to get the clean article number (e.g., "147조의2")
        article_no = article_raw_no.replace("제", "").replace("조", "").strip()
        
        # Determine the content indices
        start_idx = match.end()
        end_idx = matches[idx+1].start() if idx + 1 < len(matches) else len(full_text)
        
        # Get article body content
        content = full_text[start_idx:end_idx].strip()
        
        # Step 4: Split content into paragraphs using circular numbers (① to ⑳)
        para_pattern = r'(①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩|⑪|⑫|⑬|⑭|⑮|⑯|⑰|⑱|⑲|⑳)'
        para_parts = re.split(para_pattern, content)
        
        paragraphs = []
        if len(para_parts) == 1:
            # If no circular markers are present, the whole content is treated as paragraph "1"
            paragraphs.append({
                "paragraph_no": "1",
                "text": content.strip()
            })
        else:
            # Process split components: text before first circle, then pairs of (marker, text)
            intro = para_parts[0].strip()
            
            circle_map = {
                "①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5",
                "⑥": "6", "⑦": "7", "⑧": "8", "⑨": "9", "⑩": "10",
                "⑪": "11", "⑫": "12", "⑬": "13", "⑭": "14", "⑮": "15",
                "⑯": "16", "⑰": "17", "⑱": "18", "⑲": "19", "⑳": "20"
            }
            
            for i in range(1, len(para_parts), 2):
                marker = para_parts[i]
                p_text = para_parts[i+1].strip() if i+1 < len(para_parts) else ""
                
                # If there's some intro text before the first paragraph marker, prepend it
                if i == 1 and intro:
                    p_text = intro + " " + p_text
                    
                p_no = circle_map.get(marker, marker)
                paragraphs.append({
                    "paragraph_no": p_no,
                    "text": f"{marker} {p_text}".strip() # keep the circle marker in the text
                })
                
        articles.append({
            "article_no": article_no,
            "article_title": article_title,
            "paragraphs": paragraphs
        })
        
    return articles

def clean_category(cat):
    """
    Cleans up broken spaces/newlines in the category names from 별표3 table.
    """
    cat_clean = re.sub(r'\s+', ' ', cat).strip()

    # PDF table-cell wrapping inserts whitespace at arbitrary points (e.g.
    # "사회복 무요원"), so match against a fully whitespace-stripped copy
    # rather than requiring the substrings to be contiguous.
    compact = re.sub(r'\s+', '', cat_clean)

    # Map the messy extracted string to clean, standardized target categories
    if "병역준비" in compact and "사회복무" in compact:
        return "병역준비역, 사회복무요원 소집대상, 대체복무요원소집대상"

    if "군전공" in compact and "공중보건" in compact:
        return "군전공의요원, 공중보건의사, 병역판정검사 전담의사, 공익법무관, 공중방역수의사, 현역복무를 마치지 아니한 예비역의 장교 및 부사관을 제외한 전 자원"

    return cat_clean

def format_row_to_sentence(category, subject, sub_subject, period, docs):
    """
    Converts structured row data from 별표3 into a natural Korean sentence.
    """
    # Standardize spaces and strip list numbering prefixes for smooth sentence flow
    cat = clean_category(category)
    cat = re.sub(r'^\d+\.\s*', '', cat)
    
    sub = re.sub(r'\s+', ' ', subject).strip()
    sub = re.sub(r'^[가-힣a-zA-Z]\.\s*', '', sub)
    # Fix spacing issues in common words
    sub = sub.replace("복수 국적 자", "복수국적자")
    
    sub_sub = re.sub(r'\s+', ' ', sub_subject).strip() if sub_subject else ""
    sub_sub = re.sub(r'^\d+\)\s*', '', sub_sub)
    
    per = re.sub(r'\s+', ' ', period).strip()
    doc = re.sub(r'\s+', ' ', docs).strip()
    
    # Fix spacing issues in docs
    doc = doc.replace("체류자격(허가서 ) 사본", "체류자격(허가서) 사본")
    doc = doc.replace("공동이용시스템으 로", "공동이용시스템으로")
    doc = doc.replace("전자정 부법", "전자정부법")
    
    # Construct the subject clause of the sentence
    if sub_sub:
        subject_part = f"{cat} 대상자 중 {sub} ({sub_sub})에 해당하는 사람"
    else:
        subject_part = f"{cat} 대상자 중 {sub}에 해당하는 사람"
        
    # Build the full natural language statement
    sentence = f"{subject_part}은 {per} 범위 내에서 국외여행허가 또는 기간연장허가를 받을 수 있다. 구비서류는 {doc}이다."
    
    # Append the footnote note about "living in a 3rd country with parents" for relevant targets
    # This matches 마, 바, 사, 아 1), 아 2) from Section 1
    if any(subject.startswith(k) for k in ["마.", "바.", "사.", "아."]):
        if not subject.startswith("아.") or (sub_subject and any(sub_subject.startswith(s) for s in ["1)", "2)"])):
            sentence += " (※ 제1호 마목부터 아목2)까지의 경우에는 병역의무자가 부ㆍ모의 거주국이 아닌 제3국에서 거주하는 경우에도 부ㆍ모와 같이 거주하는 것으로 본다.)"
            
    return sentence

def parse_별표3(pdf_path):
    """
    Custom parser for 별표3.pdf which contains a layout table of rules.
    Performs forward-fill (merged cells propagation) and generates NL sentences.
    """
    chunks = []
    if not os.path.exists(pdf_path):
        print(f"Error: File not found at {pdf_path}")
        return []
        
    with pdfplumber.open(pdf_path) as pdf:
        # Keep track of last seen non-empty values for vertically/horizontally merged cells
        curr_category = ""
        curr_subject = ""
        curr_sub_sub = ""
        curr_period = ""
        curr_documents = ""
        
        for p_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                for r_idx, row in enumerate(table):
                    # Skip the table header row
                    if r_idx == 0:
                        continue
                        
                    # Page 1 table has 5 columns (includes a sub-subject column)
                    # Page 2 table has 4 columns (does not have sub-subject column)
                    # Normalize Page 2 rows to 5-column format by inserting None at index 2
                    if len(row) == 4:
                        row_norm = [row[0], row[1], None, row[2], row[3]]
                    elif len(row) == 5:
                        row_norm = row
                    else:
                        print(f"Warning: unexpected row length {len(row)} on page {p_idx+1}")
                        continue
                        
                    cat = row_norm[0]
                    sub = row_norm[1]
                    sub_sub = row_norm[2]
                    period = row_norm[3]
                    docs = row_norm[4]
                    
                    cat_val = cat.strip() if cat else ""
                    sub_val = sub.strip() if sub else ""
                    sub_sub_val = sub_sub.strip() if sub_sub else ""
                    period_val = period.strip() if period else ""
                    docs_val = docs.strip() if docs else ""
                    
                    # Forward-fill / merged cell propagation logic
                    if cat_val:
                        curr_category = cat_val
                        
                    if sub_val:
                        curr_subject = sub_val
                        # If a new main subject starts, clear the sub-subject value
                        if not sub_sub_val:
                            curr_sub_sub = ""
                            
                    if sub_sub_val:
                        curr_sub_sub = sub_sub_val
                    else:
                        # If no new sub-subject is specified but we changed main subject, reset it
                        if not sub_val:
                            pass # keep current sub_sub if it belongs to the same main subject (e.g. multi-row sub-subject)
                        else:
                            curr_sub_sub = ""
                            
                    if period_val:
                        curr_period = period_val
                        
                    if docs_val:
                        curr_documents = docs_val
                        
                    # Skip rows that are empty or header leftovers
                    if not curr_subject:
                        continue
                        
                    # Formulate natural sentence
                    sentence = format_row_to_sentence(
                        curr_category, 
                        curr_subject, 
                        curr_sub_sub, 
                        curr_period, 
                        curr_documents
                    )
                    
                    # Create structured chunk output for 별표3
                    chunks.append({
                        "text": sentence,
                        "law_name": "병역법 시행령 별표 3",
                        "article_no": "별표3",
                        "article_title": "국외이주 목적의 국외여행허가 또는 기간연장허가",
                        "paragraph_no": "1",
                        "source_doc": "별표3.pdf"
                    })
                    
    return chunks
