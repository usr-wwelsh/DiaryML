"""
AI Model interface for DiaryML
Handles AI responses with mood-awareness
Supports both vision-language models (Qwen-VL) and text-only models (Jamba, etc.)
Optimized for small 1-3B GGUF models running on CPU
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import re
import json
from llama_cpp import Llama
from llama_cpp.llama_chat_format import Llava15ChatHandler, Qwen25VLChatHandler


class QwenInterface:
    """
    AI model interface using GGUF format

    Supports:
    - Vision-language models (Qwen-VL with mmproj file)
    - Text-only models (Jamba, Llama, etc.)
    """

    def __init__(self, model_path: Optional[Path] = None, mmproj_path: Optional[Path] = None):
        """
        Initialize AI model (supports both vision and text-only models)

        Args:
            model_path: Path to the main GGUF model file
            mmproj_path: Path to the mmproj vision file (optional, for vision models)
        """
        self.model_dir = Path(__file__).parent.parent / "models"
        self.config_dir = Path(__file__).parent.parent
        self.has_vision = False
        self.is_thinking_model = False
        self.model_info = {}

        # Auto-detect model files if not provided
        if model_path is None:
            # Try to load saved preference first
            saved_model = self._load_model_preference()
            if saved_model and saved_model.exists():
                model_path = saved_model
                print(f"Loading saved model preference: {model_path.name}")
            else:
                model_path = self._find_model_file()

        # Store the model path and filename
        self.model_path = model_path
        self.model_info['filename'] = model_path.name
        self.model_info['name'] = self._extract_model_name(model_path.name)

        # Analyze model filename to detect capabilities
        self._analyze_model_name(model_path)

        # Determine if we should use vision support
        # Only attempt to load mmproj if the model is actually a vision-language model
        self.vision_handler_type = None
        if mmproj_path is not None:
            # mmproj explicitly provided - use it
            self.has_vision = True
            self.vision_handler_type = self._get_vision_handler_type(model_path)
            print(f"Using explicitly provided mmproj: {mmproj_path}")
        elif self._is_vision_model(model_path):
            # Vision model detected - try to find mmproj automatically
            try:
                mmproj_path = self._find_mmproj_file()
                self.has_vision = True
                self.vision_handler_type = self._get_vision_handler_type(model_path)
                print(f"Auto-detected vision model - found mmproj: {mmproj_path.name}")
                print(f"Vision architecture: {self.vision_handler_type}")
            except FileNotFoundError:
                print("Warning: Vision model detected but no mmproj file found - loading as text-only")
                self.has_vision = False
        else:
            # Text-only model - don't use mmproj
            self.has_vision = False
            print(f"Text-only model detected - skipping mmproj")

        print(f"Loading AI model from: {model_path.name}")
        if self.has_vision:
            print(f"Loading vision projection from: {mmproj_path.name}")
        if self.is_thinking_model:
            print("Detected reasoning/thinking model - will clean output automatically")

        # Determine optimal context window based on model size
        recommended_ctx = self._get_recommended_context()
        print(f"Using context window: {recommended_ctx} tokens")

        try:
            # Initialize with or without vision support
            if self.has_vision:
                # Vision-language model - use appropriate chat handler
                if self.vision_handler_type == 'qwen':
                    print("Using Qwen25VLChatHandler for Qwen-VL model")
                    self.chat_handler = Qwen25VLChatHandler(clip_model_path=str(mmproj_path))
                elif self.vision_handler_type == 'llava':
                    print("Using Llava15ChatHandler for LLaVA model")
                    self.chat_handler = Llava15ChatHandler(clip_model_path=str(mmproj_path))
                elif self.vision_handler_type == 'minicpm':
                    print("Using Qwen25VLChatHandler as fallback for MiniCPM-V")
                    self.chat_handler = Qwen25VLChatHandler(clip_model_path=str(mmproj_path))
                else:
                    print(f"Unknown vision model type, trying Qwen25VLChatHandler as fallback")
                    self.chat_handler = Qwen25VLChatHandler(clip_model_path=str(mmproj_path))

                self.llm = Llama(
                    model_path=str(model_path),
                    chat_handler=self.chat_handler,
                    n_ctx=recommended_ctx,
                    n_gpu_layers=0,  # CPU only
                    verbose=False,
                    n_threads=None  # Auto-detect
                )
                print("✓ Vision-language model loaded successfully")
            else:
                # Text-only model - optimized for CPU
                self.chat_handler = None
                self.llm = Llama(
                    model_path=str(model_path),
                    n_ctx=recommended_ctx,
                    n_batch=min(512, recommended_ctx // 4),  # Batch size proportional to context
                    n_gpu_layers=0,  # CPU only
                    verbose=False,
                    n_threads=None,  # Auto-detect optimal thread count
                    use_mmap=True,  # Memory-map the model for faster loading
                    use_mlock=False  # Don't lock memory (allows swapping if needed)
                )
                print("✓ Text-only model loaded successfully")
                print(f"Model info: {self.model_info.get('size', 'unknown')} parameters, {self.model_info.get('quantization', 'unknown')} quantization")

        except Exception as e:
            print(f"\n✗ Failed to load AI model: {str(e)}")
            print("\nTroubleshooting:")
            print("1. The model file might be corrupted - try re-downloading")
            print("2. Try a different model (recommended: 1B-3B parameter models with Q4_K_M or Q5_K_M quantization)")
            print("3. Check if you have enough RAM:")
            print("   - 1B model needs ~1-2GB RAM")
            print("   - 2B model needs ~2-3GB RAM")
            print("   - 3B model needs ~3-4GB RAM")
            print("\nDiaryML will still work for journaling and mood tracking!")
            print("You just won't have AI chat until the model loads.\n")
            raise

    def _load_model_preference(self) -> Optional[Path]:
        """Load the saved model preference from config file"""
        config_file = self.config_dir / "model_config.json"

        if not config_file.exists():
            return None

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                model_filename = config.get('last_model')

                if model_filename:
                    model_path = self.model_dir / model_filename
                    if model_path.exists():
                        return model_path
        except Exception as e:
            print(f"Warning: Could not load model preference: {e}")

        return None

    def save_model_preference(self):
        """Save the current model as the preferred model"""
        config_file = self.config_dir / "model_config.json"

        try:
            config = {
                'last_model': self.model_path.name,
                'last_updated': str(Path(__file__).stat().st_mtime)
            }

            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)

            print(f"✓ Saved model preference: {self.model_path.name}")
        except Exception as e:
            print(f"Warning: Could not save model preference: {e}")

    def _extract_model_name(self, filename: str) -> str:
        """
        Extract a clean model name from the filename

        Examples:
        - nsfw-ameba-3.2-1b-q5_k_m.gguf -> nsfw-ameba-3.2-1b
        - AI21-Jamba-Reasoning-3B-Q4_K_M.gguf -> AI21-Jamba-Reasoning-3B
        """
        # Remove .gguf extension
        name = filename.replace('.gguf', '')

        # Try to remove quantization suffix (q4_k_m, q5_k_m, etc.)
        name = re.sub(r'[-_](q\d+_k_[ml]|q\d+_\d+|f16|f32)$', '', name, flags=re.IGNORECASE)

        # If name is still too long, just return first 40 chars
        if len(name) > 40:
            name = name[:40] + '...'

        return name

    def _find_model_file(self) -> Path:
        """Auto-detect the main model GGUF file"""
        # Try specific names first (manually downloaded)
        known_files = [
            "nsfw-ameba-3.2-1b-q5_k_m.gguf",
            "ggml-model-f16.gguf",
            "ai21labs_AI21-Jamba-Reasoning-3B-Q4_K_M.gguf",
            "huihui-qwen3-vl-2b-instruct-abliterated-q4_k_m.gguf"
        ]

        for filename in known_files:
            filepath = self.model_dir / filename
            if filepath.exists():
                print(f"Found known model: {filename}")
                return filepath

        # Fallback to pattern matching - prioritize smaller quantized models
        patterns = [
            "*1b*.gguf",      # 1B models (fastest)
            "*2b*.gguf",      # 2B models
            "*3b*.gguf",      # 3B models
            "*ameba*.gguf",   # Ameba series
            "*jamba*.gguf",   # Jamba series
            "*qwen*.gguf",    # Qwen series
            "ggml-model*.gguf",  # Generic GGUF
            "*q5_k_m.gguf",   # Q5 quantization
            "*q4_k_m.gguf",   # Q4 quantization
            "*.gguf"          # Any GGUF file
        ]

        for pattern in patterns:
            files = list(self.model_dir.glob(pattern))
            # Exclude mmproj files
            files = [f for f in files if "mmproj" not in f.name.lower()]
            if files:
                # Sort by file size (smaller = faster) if multiple matches
                files.sort(key=lambda f: f.stat().st_size)
                print(f"Auto-detected model: {files[0].name}")
                return files[0]

        raise FileNotFoundError(
            f"No GGUF model file found in {self.model_dir}. "
            f"Please download a model file to the models/ folder.\n\n"
            f"Recommended models for CPU-only:\n"
            f"  - 1B models (fastest): nsfw-ameba-3.2-1b-q5_k_m.gguf\n"
            f"  - 2B models (balanced): qwen-2b-q4_k_m.gguf\n"
            f"  - 3B models (best quality): AI21-Jamba-Reasoning-3B-Q4_K_M.gguf"
        )

    def _is_vision_model(self, model_path: Path) -> bool:
        """
        Detect if a model is a vision-language model based on filename patterns

        Supports multiple VL architectures:
        - LLaVA (via Llava15ChatHandler)
        - Qwen2-VL/Qwen3-VL (via Qwen25VLChatHandler)
        - MiniCPM-V (via MiniCPMv26ChatHandler)

        Args:
            model_path: Path to the model file

        Returns:
            True if this appears to be a vision-language model
        """
        filename = model_path.name.lower()

        # Vision model indicators
        vision_keywords = [
            'vl',           # Vision-Language
            'vision',       # Explicit vision marker
            'llava',        # LLaVA models
            'qwen-vl',      # Qwen Vision-Language
            'qwen2-vl',     # Qwen2 Vision-Language
            'qwen3-vl',     # Qwen3 Vision-Language
            'qwen2vl',      # Alternative naming
            'qwen3vl',      # Alternative naming
            'qwenvl',       # Alternative naming
            'minicpm-v',    # MiniCPM Vision
            'lfm-vl',       # LFM Vision-Language
            'lfm2-vl',      # LFM2 Vision-Language
        ]

        # Check if any vision keyword is in the filename
        is_vision = any(keyword in filename for keyword in vision_keywords)

        # Text-only model indicators (override vision detection if found)
        text_only_keywords = [
            'ameba',        # Ameba models are text-only
            'jamba',        # Jamba models are text-only
            'reasoning',    # Reasoning models are typically text-only
            'moe',          # MoE models are typically text-only (unless explicitly VL)
        ]

        # If text-only markers found, it's likely not a vision model
        # (unless it explicitly says VL/vision)
        has_text_marker = any(keyword in filename for keyword in text_only_keywords)

        if has_text_marker and not is_vision:
            return False

        return is_vision

    def _get_vision_handler_type(self, model_path: Path) -> str:
        """
        Determine which vision chat handler to use based on model architecture

        Args:
            model_path: Path to the model file

        Returns:
            One of: 'qwen', 'llava', 'minicpm', or 'unknown'
        """
        filename = model_path.name.lower()

        # Qwen-VL models
        if any(kw in filename for kw in ['qwen-vl', 'qwen2-vl', 'qwen3-vl', 'qwen2vl', 'qwen3vl', 'qwenvl']):
            return 'qwen'

        # LLaVA models
        if 'llava' in filename:
            return 'llava'

        # MiniCPM models
        if 'minicpm-v' in filename:
            return 'minicpm'

        # LFM models (might work with Qwen handler - experimental)
        if 'lfm-vl' in filename or 'lfm2-vl' in filename:
            return 'qwen'  # Try Qwen handler as fallback

        return 'unknown'

    def _find_mmproj_file(self) -> Path:
        """Auto-detect the mmproj vision file"""
        # Try specific name first (manually downloaded)
        specific_file = self.model_dir / "mmproj-model-f16.gguf"
        if specific_file.exists():
            return specific_file

        # Fallback to pattern matching
        files = list(self.model_dir.glob("mmproj*.gguf"))
        if files:
            return files[0]

        raise FileNotFoundError(
            f"No mmproj file found in {self.model_dir}. "
            f"Please download mmproj-model-f16.gguf to the models/ folder."
        )

    def _analyze_model_name(self, model_path: Path):
        """
        Analyze model filename to extract information and detect capabilities

        Examples:
        - nsfw-ameba-3.2-1b-q5_k_m.gguf -> 1B, Q5_K_M quantization
        - AI21-Jamba-Reasoning-3B-Q4_K_M.gguf -> 3B, reasoning model, Q4_K_M
        """
        filename = model_path.name.lower()

        # Detect model size (1B, 2B, 3B, etc.)
        size_patterns = [
            (r'(\d+\.?\d*)b[\-_]', '{}B'),  # Matches "1b-", "3.2b-", etc.
            (r'[\-_](\d+\.?\d*)b', '{}B'),  # Matches "-1b", "-3b", etc.
        ]

        for pattern, format_str in size_patterns:
            match = re.search(pattern, filename)
            if match:
                size_num = match.group(1)
                self.model_info['size'] = format_str.format(size_num)
                self.model_info['size_num'] = float(size_num)
                break

        if 'size' not in self.model_info:
            # Default to unknown
            self.model_info['size'] = 'unknown'
            self.model_info['size_num'] = 2.0  # Assume 2B as default

        # Detect quantization level (Q4_K_M, Q5_K_M, F16, etc.)
        quant_patterns = [
            r'q\d+_k_[ml]',  # Matches q4_k_m, q5_k_m, etc.
            r'q\d+_\d+',     # Matches q4_0, q8_0, etc.
            r'f16',          # Matches f16
            r'f32'           # Matches f32
        ]

        for pattern in quant_patterns:
            match = re.search(pattern, filename)
            if match:
                self.model_info['quantization'] = match.group(0).upper()
                break

        if 'quantization' not in self.model_info:
            self.model_info['quantization'] = 'unknown'

        # Detect if this is a thinking/reasoning model
        thinking_keywords = ['reasoning', 'think', 'jamba', 'chain', 'cot', 'moe']
        self.is_thinking_model = any(keyword in filename for keyword in thinking_keywords)

    def _get_recommended_context(self) -> int:
        """
        Get recommended context window size based on model size and quantization
        Large contexts (~30k tokens) for rich diary context and conversation history
        """
        size_num = self.model_info.get('size_num', 2.0)
        quant = self.model_info.get('quantization', 'Q4_K_M')

        # Large context recommendations for diary/journaling use case
        # ~30k tokens allows referencing extensive past entries and conversations
        if size_num <= 1.5:  # 1B-1.5B models
            base_ctx = 24576  # 24k tokens
        elif size_num <= 2.5:  # 2B-2.5B models
            base_ctx = 28672  # 28k tokens
        elif size_num <= 3.5:  # 3B-3.5B models
            base_ctx = 32768  # 32k tokens
        else:  # Larger models
            base_ctx = 32768  # 32k tokens

        # Adjust based on quantization
        if 'Q5' in quant or 'Q6' in quant or 'Q8' in quant:
            # Higher quantization - can push to maximum
            base_ctx = min(base_ctx + 4096, 65536)  # Cap at 64k
        elif 'Q2' in quant or 'Q3' in quant:
            # Lower quantization - slightly reduce for stability
            base_ctx = max(base_ctx - 4096, 16384)  # Min 16k

        # For thinking models, give even more context for complex reasoning
        if self.is_thinking_model:
            base_ctx = min(base_ctx + 4096, 65536)

        return base_ctx

    def _calculate_response_length(self, user_message: str) -> int:
        """
        Calculate optimal response length based on message characteristics

        Returns large token counts to allow full, complete responses without cutoff.

        Args:
            user_message: The user's message

        Returns:
            Recommended max_tokens value
        """
        # Count words and sentences
        words = user_message.split()
        word_count = len(words)
        sentences = re.split(r'[.!?]+', user_message)
        sentence_count = len([s for s in sentences if s.strip()])

        # Check for question marks (questions need more thorough answers)
        has_question = '?' in user_message
        question_count = user_message.count('?')

        # Check for complexity indicators
        complex_words = ['why', 'how', 'explain', 'describe', 'analyze', 'discuss', 'compare']
        is_complex = any(word in user_message.lower() for word in complex_words)

        # Base token count - much larger than before
        base_tokens = 800

        # Adjust based on input length
        if word_count < 10:
            # Very short message - still allow substantial response
            tokens = 512
        elif word_count < 30:
            # Short message - good sized response
            tokens = 1024
        elif word_count < 100:
            # Medium message - large response
            tokens = 1536
        else:
            # Long message - very detailed response
            tokens = 2048

        # Adjust for questions (they typically need more explanation)
        if has_question:
            tokens += 256 * min(question_count, 3)

        # Adjust for complexity
        if is_complex:
            tokens += 512

        # Cap based on model size - much higher caps now
        size_num = self.model_info.get('size_num', 2.0)
        if size_num <= 1.5:  # 1B models
            max_cap = 2048  # Was 300, now 2048
        elif size_num <= 2.5:  # 2B models
            max_cap = 3072  # Was 400, now 3072
        else:  # 3B+ models
            max_cap = 4096  # Was 512, now 4096

        # For thinking models, allow even more tokens for reasoning
        if self.is_thinking_model:
            max_cap = min(max_cap + 1024, 8192)

        # Ensure we're within reasonable bounds
        tokens = max(512, min(tokens, max_cap))

        return tokens

    def generate_response(
        self,
        user_message: str,
        mood_context: Optional[Dict[str, float]] = None,
        past_context: Optional[List[str]] = None,
        image_path: Optional[str] = None,
        max_tokens: Optional[int] = None,  # Auto-detect if None
        temperature: float = 0.7
    ) -> str:
        """
        Generate AI response with mood and context awareness

        Args:
            user_message: The user's journal entry or question
            mood_context: Dict of emotion scores (e.g., {"joy": 0.8, "sadness": 0.1})
            past_context: List of relevant past entries from RAG
            image_path: Optional path to image attached to entry
            max_tokens: Maximum response length (auto-detected if None)
            temperature: Creativity (0.0-1.0, higher = more creative)

        Returns:
            AI-generated response string
        """
        # Auto-detect optimal response length if not specified
        if max_tokens is None:
            max_tokens = self._calculate_response_length(user_message)

        # Build system prompt with mood awareness
        system_prompt = self._build_system_prompt(mood_context, past_context)

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # Add image if provided and model supports vision
        if image_path and self.has_vision:
            messages[-1]["content"] = [
                {"type": "text", "text": user_message},
                {"type": "image_url", "image_url": {"url": f"file://{image_path}"}}
            ]
        elif image_path and not self.has_vision:
            # Text-only model - just mention the image exists
            messages[-1]["content"] = user_message + "\n\n[Note: Image attached but model doesn't support vision analysis]"

        # Generate response
        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        content = response["choices"][0]["message"]["content"]

        # Clean up reasoning model output if needed
        return self._clean_reasoning_output(content)

    def _build_system_prompt(
        self,
        mood_context: Optional[Dict[str, float]],
        past_context: Optional[List[str]]
    ) -> str:
        """Build system prompt with mood and context awareness"""

        prompt = """You are DiaryML, a private creative companion and emotional mirror.
You help your user reflect, create, and explore their inner world through journaling.

Your role is to:
- Be emotionally attuned and respond to the user's current mood
- Remember past projects, activities, and patterns
- Offer creative suggestions and gentle nudges
- Help capture emotions that words alone cannot express
- Be a supportive partner in the user's artistic journey

Respond with warmth, insight, and creativity. Keep responses concise but meaningful.
IMPORTANT: Provide direct responses without showing your reasoning process or explaining how you arrived at your answer."""

        # Add mood context
        if mood_context:
            emotions = ", ".join([f"{emotion} ({score:.0%})"
                                 for emotion, score in sorted(mood_context.items(),
                                                             key=lambda x: -x[1])[:3]])
            prompt += f"\n\nCurrent emotional tone: {emotions}"

            # Adjust response style based on dominant mood
            dominant_mood = max(mood_context.items(), key=lambda x: x[1])[0]
            if dominant_mood in ["sadness", "fear", "anxiety"]:
                prompt += "\nBe gentle and supportive in your response."
            elif dominant_mood in ["joy", "excitement"]:
                prompt += "\nMatch their energy with enthusiasm."
            elif dominant_mood in ["anger", "frustration"]:
                prompt += "\nBe understanding and help them process these feelings."

        # Add relevant past context (truncated to save tokens)
        if past_context:
            prompt += "\n\nRelevant past entry:"
            # Only include first entry, truncated to 100 chars
            prompt += f"\n{past_context[0][:100]}..."

        return prompt

    def _clean_reasoning_output(self, content: str) -> str:
        """
        Extract final answer from reasoning model output
        Different models use different thinking markers:
        - Jamba: <output>...</output>
        - Qwen MOE: <think>...</think>
        - Others: Answer:, Response:, etc.
        """
        # First, let's see what we're getting (debug)
        if len(content) > 200:
            print(f"\n=== RAW MODEL OUTPUT (first 500 chars) ===")
            print(content[:500])
            print(f"=== END RAW OUTPUT ===\n")

        # Pattern 1: Remove <think>...</think> blocks (Qwen MOE models)
        if '<think>' in content.lower():
            # Remove everything between <think> and </think> (case insensitive)
            import re
            # Match <think> or <THINK> with optional whitespace
            cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.IGNORECASE | re.DOTALL)
            cleaned = cleaned.strip()
            if cleaned:  # Make sure we have content left
                print("Removed <think> blocks from output")
                return cleaned

        # Pattern 2: Look for explicit answer markers and tags
        for marker in ['<output>', 'Answer:', 'Response:', 'Final answer:', 'Output:']:
            if marker in content:
                parts = content.split(marker, 1)
                if len(parts) > 1:
                    result = parts[1].strip()
                    # Remove closing tag if present
                    if '</output>' in result:
                        result = result.split('</output>')[0].strip()
                    print(f"Extracted using marker '{marker}'")
                    return result

        # Try pattern 2: Look for content after triple newlines (common separator)
        if '\n\n\n' in content:
            parts = content.split('\n\n\n')
            if len(parts) > 1:
                print("Extracted using triple newline separator")
                return parts[-1].strip()

        # Try pattern 3: If content starts with obvious reasoning, take last paragraph
        first_line = content.split('\n')[0].lower()
        if any(phrase in first_line for phrase in ['we need', 'let me', 'i need', 'first,']):
            paragraphs = content.split('\n\n')
            if len(paragraphs) > 1:
                print("Extracted last paragraph (detected reasoning in first line)")
                return paragraphs[-1].strip()

        # Default: return as-is
        print("No reasoning pattern detected, returning original")
        return content

    def generate_daily_greeting(
        self,
        recent_projects: List[str],
        mood_pattern: str,
        suggestions: List[str]
    ) -> str:
        """
        Generate personalized morning greeting with suggestions

        Args:
            recent_projects: List of recent projects/activities
            mood_pattern: Description of recent mood trends
            suggestions: List of potential activities/suggestions

        Returns:
            Greeting message
        """
        prompt = f"""Generate a warm, personalized morning greeting for the user.

Recent activities: {', '.join(recent_projects) if recent_projects else 'Starting fresh'}
Recent mood: {mood_pattern}

Suggest ONE of these activities in a natural, conversational way:
{chr(10).join(f'- {s}' for s in suggestions)}

Keep it brief (2-3 sentences), warm, and encouraging. Do NOT explain your reasoning - just provide the greeting."""

        messages = [
            {"role": "system", "content": "You are DiaryML, a supportive creative companion. Provide direct responses without explaining your reasoning process."},
            {"role": "user", "content": prompt}
        ]

        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=512,  # Increased from 150 to allow fuller greetings
            temperature=0.8
        )

        content = response["choices"][0]["message"]["content"]

        # Clean up reasoning model output
        return self._clean_reasoning_output(content)


# Singleton instance
_qwen_instance: Optional[QwenInterface] = None


def get_qwen_interface() -> QwenInterface:
    """Get or create the Qwen interface singleton"""
    global _qwen_instance
    if _qwen_instance is None:
        _qwen_instance = QwenInterface()
    return _qwen_instance
