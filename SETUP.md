# DiaryML Setup Guide

## Step-by-Step Installation

### Step 1: Download Model Files

You need to download two GGUF model files. Go to:
https://huggingface.co/huihui-ai/Huihui-Qwen3-VL-2B-Instruct-abliterated/tree/main/GGUF

Download these files:
- `ggml-model-f16.gguf` (~3.6 GB) - Main language model
- `mmproj-model-f16.gguf` (~300 MB) - Vision projection model

**Alternative (if you have limited RAM/VRAM):**
- `huihui-qwen3-vl-2b-instruct-abliterated-q4_k_m.gguf` (~1.5 GB) - Smaller quantized version

Place the downloaded files in the `DiaryML/models/` folder.

### Step 2: Install Python Dependencies

Open a terminal/command prompt in the DiaryML directory and run:

```bash
cd backend
pip install -r requirements.txt
```

This will install:
- FastAPI (web framework)
- SQLCipher (encrypted database)
- ChromaDB (vector database)
- llama-cpp-python (GGUF model runner)
- sentence-transformers (embeddings)
- transformers + torch (emotion detection)

**Installation may take 5-10 minutes.**

#### GPU Acceleration (Optional)

If you have an NVIDIA GPU and want faster AI inference:

```bash
# Uninstall CPU version
pip uninstall llama-cpp-python

# Install CUDA version
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python
```

### Step 3: Verify Installation

Run this to check everything is ready:

```bash
python -c "import fastapi, chromadb, transformers; print('All dependencies installed!')"
```

### Step 4: Start DiaryML

**On Windows:**
```bash
start.bat
```

**On Mac/Linux:**
```bash
cd backend
python main.py
```

The server will start on `http://localhost:8000`

### Step 5: First Launch

1. Open your browser to `http://localhost:8000`
2. You'll see the unlock screen
3. Enter a password (this creates your encrypted diary)
4. Wait for the AI model to load (~30 seconds)
5. Start journaling!

## Troubleshooting

### Error: "sqlcipher3" module not found

SQLCipher can be tricky on Windows. Try:

```bash
pip install pysqlcipher3
```

If that fails, you can temporarily disable encryption by modifying `database.py`:

```python
# Comment out this line in get_connection():
# conn.execute(f"PRAGMA key = '{self.password}'")
```

**Note**: This removes encryption! Only use for testing.

### Error: Model file not found

Make sure:
1. Files are named exactly `ggml-model-f16.gguf` and `mmproj-model-f16.gguf`
2. They are in the `DiaryML/models/` folder
3. The files are fully downloaded (not partial)

### Error: "CUDA out of memory"

The model is trying to use your GPU but running out of memory. Edit `qwen_interface.py`:

```python
# Change this line (around line 37):
n_gpu_layers=-1,  # Change to 0 for CPU-only
```

Or use a smaller quantized model (q4_k_m).

### Server won't start

Make sure port 8000 is not already in use:

```bash
# Windows
netstat -ano | findstr :8000

# Mac/Linux
lsof -i :8000
```

To use a different port, edit `main.py` at the bottom:

```python
uvicorn.run(
    "main:app",
    host="127.0.0.1",
    port=8080,  # Change this
    reload=True
)
```

## System Requirements

### Minimum
- **CPU**: 4-core processor
- **RAM**: 4GB free
- **Disk**: 5GB (3GB models + 2GB for dependencies)
- **OS**: Windows 10+, macOS 10.15+, Linux

### Recommended
- **CPU**: 8-core processor
- **RAM**: 8GB free
- **GPU**: NVIDIA GPU with 4GB+ VRAM (for faster inference)
- **Disk**: 10GB+

## Performance Tips

1. **Use GPU acceleration** if available (5-10x faster)
2. **Use quantized models** (q4_k_m) if RAM is limited
3. **Close other applications** when using DiaryML
4. **Reduce context window** in `qwen_interface.py` if needed:
   ```python
   n_ctx=2048,  # Instead of 4096
   ```

## Next Steps

Once DiaryML is running:

1. Create your first journal entry
2. Try attaching an image
3. Chat with the AI about your entries
4. Check the mood timeline after a few entries
5. See daily suggestions each morning

## Getting Help

If you encounter issues:

1. Check the console/terminal for error messages
2. Review the troubleshooting section above
3. Check the README.md for more details
4. Open an issue on GitHub with your error logs

---

Enjoy your private creative companion!
