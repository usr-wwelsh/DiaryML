"""
Temporal Intelligence Engine for DiaryML
Discovers hidden patterns, rhythms, and correlations in your life over time

Features:
- Mood cycle detection (weekly patterns, time-of-day trends)
- Project momentum tracking (stall detection, acceleration phases)
- Emotional trigger correlation (what topics/events trigger emotions)
- Activity-emotion correlation (what activities boost/drain you)
- Temporal anomaly detection (unusual patterns worth noting)
"""

from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re
import numpy as np
from database import DiaryDatabase


class TemporalIntelligence:
    """Discover patterns and rhythms in your life data"""

    def __init__(self, db: DiaryDatabase):
        """
        Initialize temporal intelligence engine

        Args:
            db: DiaryDatabase instance
        """
        self.db = db

    # ========================================
    # MOOD CYCLE DETECTION
    # ========================================

    def detect_mood_cycles(self, days: int = 90) -> Dict[str, Any]:
        """
        Detect patterns in mood over time

        Returns insights like:
        - Weekly patterns (e.g., "low on Sundays, high on Wednesdays")
        - Time-of-day patterns (e.g., "morning anxiety, evening calm")
        - Seasonal trends
        """
        entries = self._get_entries_with_mood(days)

        if len(entries) < 7:
            return {"status": "insufficient_data", "message": "Need at least 7 days of data"}

        # Analyze by day of week
        day_patterns = self._analyze_day_of_week_patterns(entries)

        # Analyze by time of day
        time_patterns = self._analyze_time_of_day_patterns(entries)

        # Find most volatile emotions
        volatile_emotions = self._find_volatile_emotions(entries)

        # Detect mood streak patterns
        streak_patterns = self._detect_mood_streaks(entries)

        return {
            "status": "success",
            "data_points": len(entries),
            "day_of_week": day_patterns,
            "time_of_day": time_patterns,
            "volatile_emotions": volatile_emotions,
            "streaks": streak_patterns,
            "summary": self._generate_mood_cycle_summary(day_patterns, time_patterns, volatile_emotions)
        }

    def _analyze_day_of_week_patterns(self, entries: List[Dict]) -> Dict[str, Any]:
        """Analyze mood by day of week (Monday=0, Sunday=6)"""
        day_emotions = defaultdict(lambda: defaultdict(list))

        for entry in entries:
            timestamp = datetime.fromisoformat(entry['timestamp'])
            day_of_week = timestamp.weekday()

            for emotion, score in entry['moods'].items():
                day_emotions[day_of_week][emotion].append(score)

        # Calculate averages
        day_averages = {}
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        for day_idx in range(7):
            day_avg = {}
            for emotion, scores in day_emotions[day_idx].items():
                if scores:
                    day_avg[emotion] = np.mean(scores)
            day_averages[day_names[day_idx]] = day_avg

        # Find most positive and negative days
        best_day, worst_day = self._find_best_worst_days(day_averages, day_names)

        return {
            "averages": day_averages,
            "best_day": best_day,
            "worst_day": worst_day,
            "insights": self._generate_day_insights(day_averages)
        }

    def _analyze_time_of_day_patterns(self, entries: List[Dict]) -> Dict[str, Any]:
        """Analyze mood by time of day (morning, afternoon, evening, night)"""
        time_emotions = {
            'morning': defaultdict(list),     # 5am-12pm
            'afternoon': defaultdict(list),   # 12pm-5pm
            'evening': defaultdict(list),     # 5pm-10pm
            'night': defaultdict(list)        # 10pm-5am
        }

        for entry in entries:
            timestamp = datetime.fromisoformat(entry['timestamp'])
            hour = timestamp.hour

            if 5 <= hour < 12:
                period = 'morning'
            elif 12 <= hour < 17:
                period = 'afternoon'
            elif 17 <= hour < 22:
                period = 'evening'
            else:
                period = 'night'

            for emotion, score in entry['moods'].items():
                time_emotions[period][emotion].append(score)

        # Calculate averages
        time_averages = {}
        for period, emotions in time_emotions.items():
            period_avg = {}
            for emotion, scores in emotions.items():
                if scores:
                    period_avg[emotion] = np.mean(scores)
            if period_avg:
                time_averages[period] = period_avg

        return {
            "averages": time_averages,
            "insights": self._generate_time_insights(time_averages)
        }

    def _find_volatile_emotions(self, entries: List[Dict]) -> List[Dict[str, Any]]:
        """Find emotions with high variance (emotional volatility)"""
        emotion_scores = defaultdict(list)

        for entry in entries:
            for emotion, score in entry['moods'].items():
                emotion_scores[emotion].append(score)

        volatility = []
        for emotion, scores in emotion_scores.items():
            if len(scores) >= 5:
                variance = np.var(scores)
                mean = np.mean(scores)
                volatility.append({
                    "emotion": emotion,
                    "variance": float(variance),
                    "mean": float(mean),
                    "stability": "volatile" if variance > 0.08 else "stable"
                })

        return sorted(volatility, key=lambda x: -x['variance'])[:3]

    def _detect_mood_streaks(self, entries: List[Dict]) -> Dict[str, Any]:
        """Detect consecutive days of similar dominant moods"""
        # Sort entries by timestamp
        sorted_entries = sorted(entries, key=lambda x: x['timestamp'])

        streaks = []
        current_streak = None

        for entry in sorted_entries:
            # Get dominant emotion
            dominant = max(entry['moods'].items(), key=lambda x: x[1])
            emotion, score = dominant

            if score < 0.3:  # Only count significant emotions
                continue

            if current_streak and current_streak['emotion'] == emotion:
                current_streak['length'] += 1
                current_streak['end_date'] = entry['timestamp'][:10]
            else:
                if current_streak and current_streak['length'] >= 3:
                    streaks.append(current_streak)

                current_streak = {
                    "emotion": emotion,
                    "length": 1,
                    "start_date": entry['timestamp'][:10],
                    "end_date": entry['timestamp'][:10]
                }

        # Add final streak if long enough
        if current_streak and current_streak['length'] >= 3:
            streaks.append(current_streak)

        return {
            "notable_streaks": sorted(streaks, key=lambda x: -x['length'])[:5],
            "longest_positive": self._find_longest_positive_streak(streaks),
            "longest_negative": self._find_longest_negative_streak(streaks)
        }

    # ========================================
    # PROJECT MOMENTUM TRACKING
    # ========================================

    def track_project_momentum(self, days: int = 90) -> Dict[str, Any]:
        """
        Track project activity over time to detect:
        - Stalled projects (mentioned once, then abandoned)
        - Accelerating projects (increasing mention frequency)
        - Consistent projects (steady engagement)
        """
        projects = self.db.get_active_projects()

        if not projects:
            return {"status": "no_projects", "message": "No projects found in entries"}

        momentum_data = []

        for project in projects:
            # Get entries mentioning this project
            entries = self._get_project_entries(project['name'], days)

            if not entries:
                continue

            # Calculate momentum metrics
            momentum = self._calculate_project_momentum(entries, project['name'])
            momentum['project_name'] = project['name']

            momentum_data.append(momentum)

        # Classify projects
        stalled = [p for p in momentum_data if p['status'] == 'stalled']
        accelerating = [p for p in momentum_data if p['status'] == 'accelerating']
        consistent = [p for p in momentum_data if p['status'] == 'consistent']

        return {
            "status": "success",
            "total_projects": len(momentum_data),
            "stalled": stalled,
            "accelerating": accelerating,
            "consistent": consistent,
            "insights": self._generate_momentum_insights(stalled, accelerating)
        }

    def _calculate_project_momentum(self, entries: List[Dict], project_name: str) -> Dict[str, Any]:
        """Calculate momentum metrics for a single project"""
        if len(entries) < 2:
            return {"status": "insufficient_data", "mention_count": len(entries)}

        # Sort by timestamp
        sorted_entries = sorted(entries, key=lambda x: x['timestamp'])

        first_mention = datetime.fromisoformat(sorted_entries[0]['timestamp'])
        last_mention = datetime.fromisoformat(sorted_entries[-1]['timestamp'])
        days_active = (last_mention - first_mention).days or 1

        # Calculate mention frequency in different time windows
        recent_mentions = len([e for e in sorted_entries if self._is_recent(e['timestamp'], 14)])
        older_mentions = len([e for e in sorted_entries if not self._is_recent(e['timestamp'], 14) and self._is_recent(e['timestamp'], days_active)])

        # Determine status
        if days_active > 10 and recent_mentions == 0:
            status = "stalled"
            days_since_last = (datetime.now() - last_mention).days
        elif recent_mentions > older_mentions:
            status = "accelerating"
            days_since_last = (datetime.now() - last_mention).days
        else:
            status = "consistent"
            days_since_last = (datetime.now() - last_mention).days

        return {
            "status": status,
            "mention_count": len(entries),
            "days_active": days_active,
            "days_since_last_mention": days_since_last,
            "recent_activity": recent_mentions,
            "frequency": len(entries) / max(days_active, 1)
        }

    # ========================================
    # EMOTIONAL TRIGGER CORRELATION
    # ========================================

    def find_emotional_triggers(self, days: int = 90) -> Dict[str, Any]:
        """
        Find correlations between topics/keywords and emotions

        Example: "money" + "anxiety" co-occur 80% of the time
        """
        entries = self._get_entries_with_mood(days)

        if len(entries) < 10:
            return {"status": "insufficient_data"}

        # Extract keywords from entries
        keyword_emotion_pairs = []

        for entry in entries:
            content = entry['content'].lower()
            keywords = self._extract_keywords(content)

            for emotion, score in entry['moods'].items():
                if score > 0.4:  # Only significant emotions
                    for keyword in keywords:
                        keyword_emotion_pairs.append((keyword, emotion, score))

        # Calculate correlations
        correlations = self._calculate_keyword_emotion_correlations(keyword_emotion_pairs)

        # Find strongest triggers
        positive_triggers = [c for c in correlations if c['emotion'] in ['joy', 'love']]
        negative_triggers = [c for c in correlations if c['emotion'] in ['anger', 'sadness', 'fear']]

        return {
            "status": "success",
            "positive_triggers": sorted(positive_triggers, key=lambda x: -x['correlation_strength'])[:10],
            "negative_triggers": sorted(negative_triggers, key=lambda x: -x['correlation_strength'])[:10],
            "insights": self._generate_trigger_insights(positive_triggers, negative_triggers)
        }

    # ========================================
    # HELPER METHODS
    # ========================================

    def _get_entries_with_mood(self, days: int) -> List[Dict]:
        """Get recent entries with mood data"""
        with self.db.get_connection() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)

            entries = conn.execute(
                """
                SELECT e.id, e.timestamp, e.content
                FROM entries e
                WHERE e.timestamp >= ?
                ORDER BY e.timestamp DESC
                """,
                (cutoff_date,)
            ).fetchall()

            result = []
            for entry in entries:
                moods = conn.execute(
                    "SELECT emotion, score FROM moods WHERE entry_id = ?",
                    (entry['id'],)
                ).fetchall()

                result.append({
                    "id": entry['id'],
                    "timestamp": entry['timestamp'],
                    "content": entry['content'],
                    "moods": {m['emotion']: m['score'] for m in moods}
                })

            return result

    def _get_project_entries(self, project_name: str, days: int) -> List[Dict]:
        """Get entries mentioning a specific project"""
        with self.db.get_connection() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)

            entries = conn.execute(
                """
                SELECT DISTINCT e.id, e.timestamp, e.content
                FROM entries e
                JOIN project_mentions pm ON e.id = pm.entry_id
                JOIN projects p ON pm.project_id = p.id
                WHERE p.name = ? AND e.timestamp >= ?
                ORDER BY e.timestamp ASC
                """,
                (project_name, cutoff_date)
            ).fetchall()

            return [dict(e) for e in entries]

    def _is_recent(self, timestamp_str: str, days: int) -> bool:
        """Check if timestamp is within last N days"""
        timestamp = datetime.fromisoformat(timestamp_str)
        cutoff = datetime.now() - timedelta(days=days)
        return timestamp >= cutoff

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract significant keywords from text"""
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'been', 'be',
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                     'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
                     'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my', 'your', 'his',
                     'her', 'its', 'our', 'their', 'just', 'really', 'very', 'so'}

        # Extract words
        words = re.findall(r'\b[a-z]{3,}\b', text)

        # Filter and return significant keywords
        keywords = [w for w in words if w not in stop_words and len(w) >= 4]

        # Get most common words
        word_counts = Counter(keywords)
        return [word for word, count in word_counts.most_common(20)]

    def _calculate_keyword_emotion_correlations(self, pairs: List[Tuple]) -> List[Dict]:
        """Calculate correlation strength between keywords and emotions"""
        # Count co-occurrences
        keyword_emotion_counts = defaultdict(lambda: {'count': 0, 'total_score': 0.0})

        for keyword, emotion, score in pairs:
            key = (keyword, emotion)
            keyword_emotion_counts[key]['count'] += 1
            keyword_emotion_counts[key]['total_score'] += score

        # Calculate correlations
        correlations = []
        for (keyword, emotion), data in keyword_emotion_counts.items():
            if data['count'] >= 2:  # Minimum 2 occurrences
                avg_score = data['total_score'] / data['count']
                correlations.append({
                    "keyword": keyword,
                    "emotion": emotion,
                    "co_occurrences": data['count'],
                    "correlation_strength": float(avg_score * data['count'] / 10),  # Weighted
                    "avg_emotion_score": float(avg_score)
                })

        return correlations

    # ========================================
    # INSIGHT GENERATION
    # ========================================

    def _generate_mood_cycle_summary(self, day_patterns: Dict, time_patterns: Dict, volatile: List) -> str:
        """Generate human-readable summary of mood cycles"""
        insights = []

        # Day patterns
        if day_patterns.get('best_day') and day_patterns.get('worst_day'):
            best = day_patterns['best_day']
            worst = day_patterns['worst_day']
            insights.append(f"You tend to feel best on {best['day']} (high {best['emotion']}) and lowest on {worst['day']} (high {worst['emotion']}).")

        # Volatility
        if volatile:
            most_volatile = volatile[0]
            insights.append(f"Your {most_volatile['emotion']} is most volatile, varying significantly day-to-day.")

        return " ".join(insights) if insights else "Not enough data to detect clear patterns yet."

    def _find_best_worst_days(self, day_averages: Dict, day_names: List[str]) -> Tuple[Dict, Dict]:
        """Find the best and worst days based on positive/negative emotion balance"""
        day_scores = {}

        for day, emotions in day_averages.items():
            if emotions:
                positive = emotions.get('joy', 0) + emotions.get('love', 0)
                negative = emotions.get('sadness', 0) + emotions.get('anger', 0) + emotions.get('fear', 0)
                day_scores[day] = positive - negative

        if day_scores:
            best_day = max(day_scores.items(), key=lambda x: x[1])
            worst_day = min(day_scores.items(), key=lambda x: x[1])

            best_emotion = max(day_averages[best_day[0]].items(), key=lambda x: x[1])[0]
            worst_emotion = max(day_averages[worst_day[0]].items(), key=lambda x: x[1])[0]

            return {"day": best_day[0], "emotion": best_emotion}, {"day": worst_day[0], "emotion": worst_emotion}

        return {}, {}

    def _generate_day_insights(self, day_averages: Dict) -> List[str]:
        """Generate specific insights about day-of-week patterns"""
        insights = []

        # Check for weekend vs weekday patterns
        weekday_scores = []
        weekend_scores = []

        for day, emotions in day_averages.items():
            if emotions:
                score = sum(emotions.values())
                if day in ['Saturday', 'Sunday']:
                    weekend_scores.append(score)
                else:
                    weekday_scores.append(score)

        if weekday_scores and weekend_scores:
            avg_weekday = np.mean(weekday_scores)
            avg_weekend = np.mean(weekend_scores)

            if avg_weekend > avg_weekday * 1.2:
                insights.append("Significantly more positive on weekends")
            elif avg_weekday > avg_weekend * 1.2:
                insights.append("Energized by weekdays, might need better weekend structure")

        return insights

    def _generate_time_insights(self, time_averages: Dict) -> List[str]:
        """Generate insights about time-of-day patterns"""
        insights = []

        # Compare different time periods
        if 'morning' in time_averages and 'evening' in time_averages:
            morning_anxiety = time_averages['morning'].get('fear', 0) + time_averages['morning'].get('sadness', 0)
            evening_calm = time_averages['evening'].get('joy', 0)

            if morning_anxiety > 0.4:
                insights.append("Morning anxiety detected - consider morning routines")
            if evening_calm > 0.4:
                insights.append("Evenings are your calm time")

        return insights

    def _find_longest_positive_streak(self, streaks: List[Dict]) -> Optional[Dict]:
        """Find longest streak of positive emotions"""
        positive_streaks = [s for s in streaks if s['emotion'] in ['joy', 'love', 'surprise']]
        return max(positive_streaks, key=lambda x: x['length']) if positive_streaks else None

    def _find_longest_negative_streak(self, streaks: List[Dict]) -> Optional[Dict]:
        """Find longest streak of negative emotions"""
        negative_streaks = [s for s in streaks if s['emotion'] in ['sadness', 'anger', 'fear']]
        return max(negative_streaks, key=lambda x: x['length']) if negative_streaks else None

    def _generate_momentum_insights(self, stalled: List, accelerating: List) -> List[str]:
        """Generate insights about project momentum"""
        insights = []

        if stalled:
            stalled_names = [p['project_name'] for p in stalled[:3]]
            insights.append(f"Stalled projects: {', '.join(stalled_names)}")

            # Check for common stall pattern
            avg_stall_time = np.mean([p['days_active'] for p in stalled])
            if avg_stall_time < 15:
                insights.append(f"Projects tend to stall around {int(avg_stall_time)} days - early momentum is key")

        if accelerating:
            accel_names = [p['project_name'] for p in accelerating[:3]]
            insights.append(f"Accelerating projects: {', '.join(accel_names)} - great momentum!")

        return insights

    def _generate_trigger_insights(self, positive: List, negative: List) -> List[str]:
        """Generate insights about emotional triggers"""
        insights = []

        if positive:
            top_positive = positive[0]
            insights.append(f"'{top_positive['keyword']}' strongly correlates with {top_positive['emotion']}")

        if negative:
            top_negative = negative[0]
            insights.append(f"'{top_negative['keyword']}' triggers {top_negative['emotion']} - worth noting")

        return insights


# Singleton
_temporal_intelligence: Optional[TemporalIntelligence] = None


def get_temporal_intelligence(db: DiaryDatabase) -> TemporalIntelligence:
    """Get or create temporal intelligence singleton"""
    global _temporal_intelligence
    if _temporal_intelligence is None:
        _temporal_intelligence = TemporalIntelligence(db)
    return _temporal_intelligence
