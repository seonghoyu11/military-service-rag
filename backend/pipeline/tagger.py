def tag_chunk(chunk):
    """
    Applies metadata tags to a single law chunk.
    Tags are categorized into user types (e.g., 영주권자, 이중국적자, 유학생, 재외동포2세)
    and topics (e.g., 국외여행허가, 허가취소, 영리활동, 여비지급, 복무, 연기, 제재, 감면).
    If no user tags match, defaults to ["전체"].
    If no topic tags match, defaults to ["일반"].
    """
    text = chunk["text"]
    title = chunk["article_title"]
    
    # Create search space combining the title and the body content (case-insensitive search)
    search_space = f"{title} {text}".lower()
    
    # 1. User Type Tagging
    user_type_tags = []
    
    # "영주권" matches 영주권자 (Permanent Resident)
    if "영주권" in search_space:
        user_type_tags.append("영주권자")
        
    # "재외국민 2세" or "재외국민2세" matches 재외동포2세 (Second-generation overseas Korean)
    if "재외국민 2세" in search_space or "재외국민2세" in search_space:
        user_type_tags.append("재외동포2세")
        
    # "복수국적" matches 이중국적자 (Dual Citizen)
    if "복수국적" in search_space:
        user_type_tags.append("이중국적자")
        
    # "유학" matches 유학생 (International Student)
    if "유학" in search_space:
        user_type_tags.append("유학생")
        
    # Fallback to "전체" (all / common) if no specific user category matches
    if not user_type_tags:
        user_type_tags = ["전체"]
        
    # 2. Topic Tagging
    topic_tags = []
    
    # "허가취소" (Cancellation of permit)
    if any(kw in search_space for kw in ["허가취소", "허가 취소", "취소"]):
        topic_tags.append("허가취소")
        
    # "영리활동" (For-profit activities)
    if any(kw in search_space for kw in ["영리", "취업", "생업"]):
        topic_tags.append("영리활동")
        
    # "여비지급" (Travel expenses payment)
    if any(kw in search_space for kw in ["여비", "항공료", "귀가", "귀향"]):
        topic_tags.append("여비지급")
        
    # "국외여행허가" (Overseas travel permit)
    if any(kw in search_space for kw in ["국외여행", "국외체재", "해외체재"]):
        topic_tags.append("국외여행허가")
        
    # "휴가" (Leave / vacation)
    if "휴가" in search_space:
        topic_tags.append("휴가")
        
    # "복무" (Military service duties)
    if any(kw in search_space for kw in ["복무", "소집", "의무부과"]):
        topic_tags.append("복무")
        
    # "연기" (Postponement of enlistment)
    if "연기" in search_space:
        topic_tags.append("연기")
        
    # "제재" (Sanctions / penalties)
    if any(kw in search_space for kw in ["위반", "제재", "벌칙", "고발", "형사"]):
        topic_tags.append("제재")
        
    # "감면" (Reduction / exemption)
    if any(kw in search_space for kw in ["감면", "면제"]):
        topic_tags.append("감면")
        
    # Fallback to "일반" (General) if no topic tags match
    if not topic_tags:
        topic_tags = ["일반"]
        
    # Apply tags to the chunk
    chunk["user_type_tags"] = user_type_tags
    chunk["topic_tags"] = topic_tags
    
    return chunk

def tag_chunks(chunks):
    """
    Applies tagging to a list of chunks in place.
    """
    for chunk in chunks:
        tag_chunk(chunk)
    return chunks
