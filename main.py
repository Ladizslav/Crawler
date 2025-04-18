import json
import os

def shrink_large_json(input_file="data.json", output_file="data_400mb.json", target_size_mb=400):
    print("Loading input file...")
    
    # Načtení celého vstupního souboru
    with open(input_file, "r", encoding="utf-8") as infile:
        data = json.load(infile)
    
    print(f"Original size: {len(data)} records")
    
    target_bytes = target_size_mb * 1024 * 1024
    current_size = 0
    kept_records = 0
    
    # Najdeme index, kde překročíme cílovou velikost
    for i, record in enumerate(data):
        # Odhad velikosti záznamu - serializujeme do JSON stringu
        record_size = len(json.dumps(record).encode("utf-8"))
        
        if current_size + record_size > target_bytes:
            break
        
        current_size += record_size
        kept_records += 1
    
    # Oříznutí dat na požadovanou velikost
    trimmed_data = data[:kept_records]
    
    # Uložení oříznutých dat
    print(f"Saving {kept_records} records (~{current_size/(1024*1024):.2f} MB)...")
    with open(output_file, "w", encoding="utf-8") as outfile:
        json.dump(trimmed_data, outfile, ensure_ascii=False, indent=2)
    
    print("Done.")

if __name__ == "__main__":
    shrink_large_json()