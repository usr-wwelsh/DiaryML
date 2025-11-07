"""
Test script to verify DiaryML setup
Run this to check if all components are working
"""

import sys
from pathlib import Path

print("=" * 60)
print("DiaryML Setup Verification")
print("=" * 60)
print()

# Test 1: Check Python version
print("1. Checking Python version...")
if sys.version_info >= (3, 10):
    print(f"   ✓ Python {sys.version_info.major}.{sys.version_info.minor} (OK)")
else:
    print(f"   ✗ Python {sys.version_info.major}.{sys.version_info.minor} (Need 3.10+)")
    sys.exit(1)

# Test 2: Import dependencies
print("\n2. Checking dependencies...")

dependencies = {
    "fastapi": "FastAPI",
    "uvicorn": "Uvicorn",
    "chromadb": "ChromaDB",
    "sentence_transformers": "Sentence Transformers",
    "transformers": "Transformers",
    "torch": "PyTorch",
    "llama_cpp": "llama-cpp-python",
    "PIL": "Pillow"
}

failed = []
for module, name in dependencies.items():
    try:
        __import__(module)
        print(f"   ✓ {name}")
    except ImportError:
        print(f"   ✗ {name} (not installed)")
        failed.append(name)

if failed:
    print(f"\n   Missing dependencies: {', '.join(failed)}")
    print("   Run: pip install -r requirements.txt")
    sys.exit(1)

# Test 3: Check model files
print("\n3. Checking model files...")

model_dir = Path(__file__).parent.parent / "models"
model_files = {
    "ggml-model-f16.gguf": "Main model",
    "mmproj-model-f16.gguf": "Vision projection"
}

model_found = False
for filename, description in model_files.items():
    filepath = model_dir / filename
    if filepath.exists():
        size_mb = filepath.stat().st_size / (1024 * 1024)
        print(f"   ✓ {description}: {filename} ({size_mb:.1f} MB)")
        model_found = True
    else:
        print(f"   ✗ {description}: {filename} (not found)")

# Check for alternative model files
if not model_found:
    print("\n   Checking for alternative models...")
    gguf_files = list(model_dir.glob("*.gguf"))

    if gguf_files:
        print("   Found GGUF files:")
        for f in gguf_files:
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"     - {f.name} ({size_mb:.1f} MB)")

        # Check if we have at least one model and one mmproj
        has_model = any("mmproj" not in f.name.lower() for f in gguf_files)
        has_mmproj = any("mmproj" in f.name.lower() for f in gguf_files)

        if has_model and has_mmproj:
            print("   ✓ Model files detected (using alternative names)")
        else:
            print("   ✗ Need both main model and mmproj file")
    else:
        print("   ✗ No GGUF files found in models/ directory")
        print("   Download from: https://huggingface.co/huihui-ai/Huihui-Qwen3-VL-2B-Instruct-abliterated/tree/main/GGUF")

# Test 4: Test database creation
print("\n4. Testing database...")
try:
    from database import DiaryDatabase

    test_db = DiaryDatabase(
        db_path=model_dir / "test.db",
        password="test123"
    )
    test_db.initialize_schema()

    # Test write and read
    entry_id = test_db.add_entry("Test entry", None)
    entry = test_db.get_entry(entry_id)

    if entry and entry["content"] == "Test entry":
        print("   ✓ Database working")
    else:
        print("   ✗ Database read/write failed")

    # Clean up
    import os
    db_path = model_dir / "test.db"
    if db_path.exists():
        os.remove(db_path)

except Exception as e:
    print(f"   ✗ Database error: {e}")

# Test 5: Test emotion detector
print("\n5. Testing emotion detector...")
try:
    from emotion_detector import EmotionDetector

    print("   Loading emotion model (this may take a moment)...")
    detector = EmotionDetector()

    emotions = detector.detect_emotions("I feel happy and excited today!")

    if emotions and "joy" in emotions:
        print(f"   ✓ Emotion detector working (detected joy: {emotions['joy']:.2f})")
    else:
        print("   ✗ Emotion detector not returning expected results")

except Exception as e:
    print(f"   ✗ Emotion detector error: {e}")

# Test 6: Test RAG engine
print("\n6. Testing RAG engine...")
try:
    from rag_engine import RAGEngine
    import shutil

    print("   Initializing ChromaDB...")
    test_chroma_dir = model_dir / "test_chroma"
    rag = RAGEngine(persist_directory=test_chroma_dir)

    from datetime import datetime
    rag.add_entry(1, "Test entry about coding", datetime.now())

    results = rag.search_entries("programming", n_results=1)

    if results:
        print("   ✓ RAG engine working")
    else:
        print("   ⚠ RAG search returned no results (may be OK)")

    # Clean up
    if test_chroma_dir.exists():
        shutil.rmtree(test_chroma_dir)

except Exception as e:
    print(f"   ✗ RAG engine error: {e}")

# Summary
print("\n" + "=" * 60)
print("Setup Verification Complete!")
print("=" * 60)
print()
print("Next steps:")
print("1. Make sure model files are in models/ directory")
print("2. Run: python main.py")
print("3. Open: http://localhost:8000")
print()
