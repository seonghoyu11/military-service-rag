import os
import sys
import json
from collections import Counter

# Add backend directory to sys.path to allow pipeline imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.parser import parse_standard_law, parse_별표3
from pipeline.chunker import chunk_articles, chunk_별표3_chunks
from pipeline.tagger import tag_chunks

def main():
    raw_dir = "/Users/steveyoo/Desktop/military-service-rag/backend/data/raw"
    processed_dir = "/Users/steveyoo/Desktop/military-service-rag/backend/data/processed"
    output_file = os.path.join(processed_dir, "law_chunks.json")
    
    # Ensure processed directory exists
    os.makedirs(processed_dir, exist_ok=True)
    
    # Define files and their official law names
    standard_files = [
        ("병역법.pdf", "병역법"),
        ("병역법_시행령.pdf", "병역법 시행령"),
        ("병역법_시행규칙.pdf", "병역법 시행규칙"),
        ("국외여행_업무처리_규정.pdf", "병역의무자 국외여행 업무처리 규정"),
        ("국외영주권자_여비지급_훈령.pdf", "국외영주권자 등 병 복무시 휴가여비 및 전역시 귀가여비 지급 훈령")
    ]
    
    all_chunks = []
    distribution = Counter()
    
    print(">>> Starting Military Law PDF Data Parsing Pipeline...")
    
    # 1. Process 5 Standard Laws
    for filename, law_name in standard_files:
        pdf_path = os.path.join(raw_dir, filename)
        print(f"Processing standard law: {filename}...")
        
        # Parse PDF into structured article/paragraph hierarchy
        articles = parse_standard_law(pdf_path, law_name)
        
        # Chunk articles (handling Article vs Paragraph level splits)
        chunks = chunk_articles(articles, law_name, filename)
        
        all_chunks.extend(chunks)
        distribution[filename] += len(chunks)
        print(f"  Generated {len(chunks)} chunks from {filename}.")
        
    # 2. Process 별표3 (Custom Table rules)
    별표3_filename = "별표3.pdf"
    별표3_path = os.path.join(raw_dir, 별표3_filename)
    if os.path.exists(별표3_path):
        print(f"Processing layout table: {별표3_filename}...")
        
        # Parse 별표3 custom rows into natural sentences
        raw_별표3_chunks = parse_별표3(별표3_path)
        
        # Structure chunks and extract references
        별표3_chunks = chunk_별표3_chunks(raw_별표3_chunks)
        
        all_chunks.extend(별표3_chunks)
        distribution[별표3_filename] += len(별표3_chunks)
        print(f"  Generated {len(별표3_chunks)} chunks from {별표3_filename}.")
    else:
        print(f"Warning: {별표3_filename} not found!")
        
    # 3. Apply Tagging to all chunks
    print("Tagging chunks...")
    tag_chunks(all_chunks)
    
    # 4. Save processed chunks list to law_chunks.json
    print(f"Writing chunks to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        
    # 5. Output Summary Statistics
    print("\n" + "="*50)
    print("PIPELINE COMPLETED SUCCESSFULLY!")
    print("="*50)
    print(f"Total Chunks Generated: {len(all_chunks)}")
    print("\nDistribution per raw document:")
    for doc, count in distribution.items():
        print(f"  - {doc}: {count} chunks")
        
    # Calculate count of untagged chunks (user_type_tags contains "전체")
    untagged_count = sum(1 for chunk in all_chunks if "전체" in chunk["user_type_tags"])
    print(f"\nUntagged Chunks (tagged as '전체'): {untagged_count}")
    
    # 6. Display a few sample chunks
    print("\n" + "="*50)
    print("SAMPLE CHUNKS:")
    print("="*50)
    
    # Display 1 standard chunk and 1 별표3 chunk as samples
    samples = []
    standard_sample = next((c for c in all_chunks if c["source_doc"] != "별표3.pdf"), None)
    별표3_sample = next((c for c in all_chunks if c["source_doc"] == "별표3.pdf"), None)
    
    if standard_sample:
        samples.append(standard_sample)
    if 별표3_sample:
        samples.append(별표3_sample)
        
    for i, sample in enumerate(samples):
        print(f"\nSample {i+1} (Source: {sample['source_doc']}):")
        print(json.dumps(sample, ensure_ascii=False, indent=2))
    print("="*50)

if __name__ == "__main__":
    main()
