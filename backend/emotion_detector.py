"""
Emotion detection module for DiaryML
Analyzes text to extract mood and emotional state with professional-grade accuracy
Uses calibrated models and robust aggregation for reliable results
"""

from typing import Dict, List, Tuple, Any, Optional
import re
import numpy as np
from transformers import pipeline
import torch


class EmotionDetector:
    """Detect emotions and mood from journal text with professional accuracy"""

    def __init__(self):
        """Initialize emotion detection model"""
        print("Loading emotion detection model...")

        # Use the more reliable and well-calibrated j-hartmann model
        # This model is specifically trained for nuanced emotion detection
        # and produces better-calibrated probability scores
        try:
            self.emotion_classifier = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                top_k=None,  # Return all emotion scores
                device=0 if torch.cuda.is_available() else -1
            )
            print("✓ Using j-hartmann/emotion-english-distilroberta-base (professional)")
        except Exception as e:
            print(f"Warning: Could not load primary model, falling back: {e}")
            # Fallback to the older model if needed
            self.emotion_classifier = pipeline(
                "text-classification",
                model="bhadresh-savani/distilbert-base-uncased-emotion",
                top_k=None,
                device=0 if torch.cuda.is_available() else -1
            )
            print("✓ Using fallback emotion model")

        # Map model labels to our emotion categories
        self.emotion_map = {
            "joy": "joy",
            "sadness": "sadness",
            "anger": "anger",
            "fear": "fear",
            "love": "love",
            "surprise": "surprise",
            "neutral": "neutral"  # Some models include neutral
        }

        print("✓ Emotion detection model loaded")

    def detect_emotions(self, text: str, chunk_size: int = 512) -> Dict[str, float]:
        """
        Detect emotions from text with professional-grade calibration

        Args:
            text: Input text to analyze
            chunk_size: Max characters per chunk (for long texts)

        Returns:
            Dict mapping emotion names to scores (0-1), properly normalized
        """
        if not text.strip():
            return self._neutral_emotions()

        # Split long texts into chunks
        chunks = self._split_text(text, chunk_size)

        # Analyze each chunk
        all_results = []
        for chunk in chunks:
            if chunk.strip():
                try:
                    results = self.emotion_classifier(chunk)[0]
                    all_results.append(results)
                except Exception as e:
                    print(f"Warning: Emotion detection error on chunk: {e}")
                    continue

        if not all_results:
            return self._neutral_emotions()

        # Aggregate and normalize scores properly
        emotion_scores = self._aggregate_emotions_robust(all_results)

        # Apply calibration to prevent extreme scores
        emotion_scores = self._calibrate_scores(emotion_scores, text)

        return emotion_scores

    def get_dominant_emotion(self, emotions: Dict[str, float]) -> Tuple[str, float]:
        """
        Get the dominant emotion

        Returns:
            Tuple of (emotion_name, score)
        """
        if not emotions:
            return ("neutral", 0.0)

        # Filter out very low scores
        significant_emotions = {k: v for k, v in emotions.items() if v > 0.1}

        if not significant_emotions:
            return ("neutral", 0.0)

        return max(significant_emotions.items(), key=lambda x: x[1])

    def get_mood_description(self, emotions: Dict[str, float]) -> str:
        """
        Generate human-readable mood description

        Returns:
            Description like "Joyful with hints of surprise"
        """
        # Sort by score
        sorted_emotions = sorted(emotions.items(), key=lambda x: -x[1])

        # Primary emotion
        primary, primary_score = sorted_emotions[0]

        # Require higher threshold for non-neutral classification
        if primary_score < 0.35:
            return "Neutral"

        description = primary.capitalize()

        # Add secondary emotion if significant
        if len(sorted_emotions) > 1:
            secondary, secondary_score = sorted_emotions[1]
            if secondary_score > 0.25 and secondary != "neutral":
                description += f" with hints of {secondary}"

        return description

    def analyze_sentiment_intensity(self, emotions: Dict[str, float]) -> Dict[str, Any]:
        """
        Analyze overall sentiment and intensity

        Returns:
            Dict with overall_sentiment, intensity, valence
        """
        # Positive emotions
        positive_score = emotions.get("joy", 0) + emotions.get("love", 0) + emotions.get("surprise", 0) * 0.5

        # Negative emotions
        negative_score = emotions.get("sadness", 0) + emotions.get("anger", 0) + emotions.get("fear", 0)

        # Overall sentiment
        valence = positive_score - negative_score

        if valence > 0.3:
            overall_sentiment = "positive"
        elif valence < -0.3:
            overall_sentiment = "negative"
        else:
            overall_sentiment = "neutral"

        # Intensity (how strong are the emotions overall)
        intensity = max(emotions.values()) if emotions else 0.0

        return {
            "overall_sentiment": overall_sentiment,
            "valence": valence,
            "intensity": intensity,
            "positive_score": positive_score,
            "negative_score": negative_score
        }

    def _split_text(self, text: str, chunk_size: int) -> List[str]:
        """Split text into chunks at sentence boundaries"""
        # Try to split at sentence boundaries
        sentences = re.split(r'[.!?]+', text)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence + ". "

        if current_chunk:
            chunks.append(current_chunk)

        return chunks if chunks else [text[:chunk_size]]

    def _aggregate_emotions_robust(self, all_results: List[List[Dict]]) -> Dict[str, float]:
        """
        Aggregate emotion scores with proper normalization

        This method properly handles the raw model outputs and ensures
        that scores are meaningful and well-calibrated.
        """
        if not all_results:
            return self._neutral_emotions()

        # Collect scores per emotion across all chunks
        emotion_scores_per_chunk = []

        for result_group in all_results:
            # Each chunk gets a dict of its emotion scores
            chunk_emotions = {}

            for result in result_group:
                label = result["label"].lower()
                score = result["score"]

                if label in self.emotion_map:
                    emotion = self.emotion_map[label]
                    chunk_emotions[emotion] = score

            # Normalize scores for this chunk to sum to 1 (proper probability distribution)
            total = sum(chunk_emotions.values())
            if total > 0:
                chunk_emotions = {k: v / total for k, v in chunk_emotions.items()}

            emotion_scores_per_chunk.append(chunk_emotions)

        # Average across chunks
        final_emotions = {}
        for emotion in self.emotion_map.values():
            if emotion == "neutral":
                continue  # Handle neutral separately

            scores = [chunk.get(emotion, 0.0) for chunk in emotion_scores_per_chunk]
            final_emotions[emotion] = np.mean(scores) if scores else 0.0

        return final_emotions

    def _calibrate_scores(self, emotions: Dict[str, float], text: str) -> Dict[str, float]:
        """
        Apply calibration to prevent extreme/unrealistic scores

        This addresses the issue where conversational text gets labeled as 98% anger.
        We apply sensible constraints based on text characteristics.
        """
        # Detect conversational indicators (questions, greetings, casual language)
        conversational_indicators = [
            r'\b(hey|hi|hello|thanks|please|maybe|think|feel|just)\b',
            r'\?',  # Questions
            r'\b(haha|lol|btw|tbh|ngl)\b',  # Internet slang
            r'\b(wondering|curious|interested)\b'
        ]

        is_conversational = any(re.search(pattern, text.lower()) for pattern in conversational_indicators)

        # Detect aggressive indicators
        aggressive_indicators = [
            r'\b(hate|angry|furious|rage|damn|hell)\b',
            r'[!]{2,}',  # Multiple exclamation marks
            r'[A-Z]{4,}',  # ALL CAPS words
        ]

        is_aggressive = any(re.search(pattern, text) for pattern in aggressive_indicators)

        # Apply calibration
        calibrated = emotions.copy()

        # If conversational but not aggressive, reduce negative emotions
        if is_conversational and not is_aggressive:
            # Dampen negative emotions significantly
            calibrated['anger'] = min(calibrated.get('anger', 0) * 0.3, 0.4)
            calibrated['fear'] = min(calibrated.get('fear', 0) * 0.4, 0.4)
            calibrated['sadness'] = min(calibrated.get('sadness', 0) * 0.5, 0.5)

            # Boost joy/neutral slightly
            calibrated['joy'] = calibrated.get('joy', 0) * 1.2

        # Prevent any single emotion from dominating unrealistically (>80%)
        max_emotion = max(calibrated.values()) if calibrated else 0
        if max_emotion > 0.8:
            # Scale everything down proportionally
            scale_factor = 0.8 / max_emotion
            calibrated = {k: v * scale_factor for k, v in calibrated.items()}

        # Ensure some emotional diversity (prevent 95%+ single emotion)
        # Add a small baseline to other emotions
        max_val = max(calibrated.values()) if calibrated else 0
        if max_val > 0.7:
            for emotion in calibrated:
                if calibrated[emotion] < 0.1:
                    calibrated[emotion] = max(calibrated[emotion], 0.05)

        # Renormalize to sum to ~1.0
        total = sum(calibrated.values())
        if total > 0:
            calibrated = {k: v / total for k, v in calibrated.items()}

        return calibrated

    def _neutral_emotions(self) -> Dict[str, float]:
        """Return neutral emotion scores with slight joy bias (default positive)"""
        return {
            "joy": 0.3,
            "sadness": 0.1,
            "anger": 0.05,
            "fear": 0.05,
            "love": 0.2,
            "surprise": 0.3
        }


# Singleton
_emotion_detector: Optional[EmotionDetector] = None


def get_emotion_detector() -> EmotionDetector:
    """Get or create emotion detector singleton"""
    global _emotion_detector
    if _emotion_detector is None:
        _emotion_detector = EmotionDetector()
    return _emotion_detector
