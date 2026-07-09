import re

def extract_references(text):
    """
    Extracts article reference citations (e.g., '법 제70조제1항', '영 제145조', '제60조') 
    from the chunk text using regular expressions.
    Formats them to have a clean space after the prefix but no internal spaces.
    """
    # Matches optional prefix (법/영/규칙/이 규정/훈령) followed by article/paragraph/item details
    ref_pattern = re.compile(
        r'(법|영|규칙|이\s+규정|훈령)?\s*(제\d+조(?:의\d+)*(?:\s*제\d+항)*(?:\s*제\d+호)*(?:\s*제\d+목)*)'
    )
    
    matches = ref_pattern.findall(text)
    cleaned_matches = []
    
    for prefix, ref in matches:
        # Remove any internal whitespaces in the reference part (e.g., "제 60 조" -> "제60조")
        ref_clean = re.sub(r'\s+', '', ref).strip()
        
        # Standardize the format: space only between the prefix and the reference
        if prefix:
            prefix_clean = prefix.strip()
            full_ref = f"{prefix_clean} {ref_clean}"
        else:
            full_ref = ref_clean
            
        if full_ref and full_ref not in cleaned_matches:
            cleaned_matches.append(full_ref)
            
    return cleaned_matches

def chunk_articles(articles, law_name, source_doc):
    """
    Chunks a list of parsed articles.
    If the article text length is <= 500 characters, it creates an Article-level chunk.
    If the article text length > 500 characters, it splits it into Paragraph-level chunks.
    Prepends the context header to each chunk and extracts references.
    """
    chunks = []
    
    for art in articles:
        art_no = art["article_no"]
        art_title = art["article_title"]
        paragraphs = art["paragraphs"]
        
        # Calculate the total length of all paragraph texts joined by newlines
        all_para_text = "\n".join(p["text"] for p in paragraphs)
        
        # If total content size is <= 500 chars, or there is only 1 paragraph, chunk as Article
        if len(all_para_text) <= 500 or len(paragraphs) <= 1:
            prefix = f"[{law_name} 제{art_no}조({art_title})]" if art_title else f"[{law_name} 제{art_no}조]"
            full_text = f"{prefix}\n{all_para_text}"
            
            refers_to = extract_references(full_text)
            
            chunks.append({
                "text": full_text,
                "law_name": law_name,
                "article_no": art_no,
                "article_title": art_title,
                "paragraph_no": "all",
                "source_doc": source_doc,
                "refers_to": refers_to
            })
        else:
            # Otherwise, split into Paragraph-level chunks to keep chunks small and localized
            for p in paragraphs:
                p_no = p["paragraph_no"]
                p_text = p["text"]
                
                prefix = f"[{law_name} 제{art_no}조({art_title}) 제{p_no}항]" if art_title else f"[{law_name} 제{art_no}조 제{p_no}항]"
                full_text = f"{prefix}\n{p_text}"
                
                refers_to = extract_references(full_text)
                
                chunks.append({
                    "text": full_text,
                    "law_name": law_name,
                    "article_no": art_no,
                    "article_title": art_title,
                    "paragraph_no": p_no,
                    "source_doc": source_doc,
                    "refers_to": refers_to
                })
                
    return chunks

def chunk_별표3_chunks(별표3_raw_chunks):
    """
    Processes raw chunks from 별표3 (which are already sentence-level chunks).
    Extracts the references and adds the refers_to field to complete the schema.
    """
    processed = []
    for c in 별표3_raw_chunks:
        refers_to = extract_references(c["text"])
        
        processed.append({
            "text": c["text"],
            "law_name": c["law_name"],
            "article_no": c["article_no"],
            "article_title": c["article_title"],
            "paragraph_no": c["paragraph_no"],
            "source_doc": c["source_doc"],
            "refers_to": refers_to
        })
    return processed
