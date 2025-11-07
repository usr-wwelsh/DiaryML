"""
Advanced analytics for DiaryML
Temporal awareness, pattern detection, and deeper insights
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import statistics


class DeepAnalytics:
    """Advanced analytics engine for deeper insights"""

    def __init__(self, db):
        self.db = db

    def get_writing_streak(self) -> Dict[str, Any]:
        """
        Calculate current writing streak and longest streak

        Returns:
            Dict with current_streak, longest_streak, last_entry_date
        """
        entries = self.db.get_recent_entries(limit=1000)

        if not entries:
            return {
                "current_streak": 0,
                "longest_streak": 0,
                "last_entry_date": None,
                "total_entries": 0
            }

        # Group entries by date
        entries_by_date = defaultdict(list)
        for entry in entries:
            date = datetime.fromisoformat(entry["timestamp"]).date()
            entries_by_date[date].append(entry)

        # Sort dates
        dates = sorted(entries_by_date.keys(), reverse=True)

        # Calculate current streak
        current_streak = 0
        today = datetime.now().date()

        # Check if there's an entry today or yesterday
        if dates and (dates[0] == today or dates[0] == today - timedelta(days=1)):
            check_date = dates[0]
            for date in dates:
                if date == check_date:
                    current_streak += 1
                    check_date = check_date - timedelta(days=1)
                elif date < check_date - timedelta(days=1):
                    break

        # Calculate longest streak
        longest_streak = 0
        temp_streak = 1

        for i in range(len(dates) - 1):
            if dates[i] - dates[i + 1] == timedelta(days=1):
                temp_streak += 1
                longest_streak = max(longest_streak, temp_streak)
            else:
                temp_streak = 1

        longest_streak = max(longest_streak, temp_streak)

        return {
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "last_entry_date": dates[0].isoformat() if dates else None,
            "total_entries": len(entries),
            "entries_this_week": sum(1 for d in dates if d >= today - timedelta(days=7)),
            "entries_this_month": sum(1 for d in dates if d >= today - timedelta(days=30))
        }

    def analyze_temporal_mood_patterns(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze how moods change over time

        Args:
            days: Number of days to analyze

        Returns:
            Mood patterns and trends
        """
        cutoff = datetime.now() - timedelta(days=days)
        timeline = self.db.get_mood_timeline(days=days)

        if not timeline:
            return {"patterns": [], "trends": {}}

        # Group by emotion
        emotions_over_time = defaultdict(list)
        for entry in timeline:
            emotions_over_time[entry["emotion"]].append({
                "date": entry["date"],
                "score": entry["avg_score"]
            })

        # Calculate trends (increasing/decreasing)
        trends = {}
        for emotion, data_points in emotions_over_time.items():
            if len(data_points) >= 2:
                scores = [d["score"] for d in sorted(data_points, key=lambda x: x["date"])]
                # Simple trend: compare first half to second half
                mid = len(scores) // 2
                first_half_avg = statistics.mean(scores[:mid])
                second_half_avg = statistics.mean(scores[mid:])

                if second_half_avg > first_half_avg * 1.1:
                    trends[emotion] = "increasing"
                elif second_half_avg < first_half_avg * 0.9:
                    trends[emotion] = "decreasing"
                else:
                    trends[emotion] = "stable"

        # Identify patterns
        patterns = []

        # Weekly patterns
        weekly_moods = self._analyze_weekly_patterns(timeline)
        if weekly_moods:
            patterns.append({
                "type": "weekly",
                "description": weekly_moods
            })

        return {
            "trends": trends,
            "patterns": patterns,
            "dominant_emotion_last_week": self._get_dominant_emotion_period(timeline, 7),
            "dominant_emotion_last_month": self._get_dominant_emotion_period(timeline, 30)
        }

    def _analyze_weekly_patterns(self, timeline: List[Dict]) -> Optional[str]:
        """Analyze if there are weekly mood patterns"""
        # Group by day of week
        day_emotions = defaultdict(lambda: defaultdict(list))

        for entry in timeline:
            date = datetime.fromisoformat(entry["date"])
            day_of_week = date.strftime("%A")
            day_emotions[day_of_week][entry["emotion"]].append(entry["avg_score"])

        # Find if any day has consistently different mood
        insights = []
        for day, emotions in day_emotions.items():
            for emotion, scores in emotions.items():
                if len(scores) >= 2 and statistics.mean(scores) > 0.6:
                    insights.append(f"Higher {emotion} on {day}s")

        return "; ".join(insights) if insights else None

    def _get_dominant_emotion_period(self, timeline: List[Dict], days: int) -> Optional[str]:
        """Get dominant emotion for a specific period"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        recent = [e for e in timeline if e["date"] >= cutoff]

        if not recent:
            return None

        emotion_totals = defaultdict(float)
        for entry in recent:
            emotion_totals[entry["emotion"]] += entry["avg_score"]

        if emotion_totals:
            return max(emotion_totals.items(), key=lambda x: x[1])[0]
        return None

    def get_project_insights(self) -> Dict[str, Any]:
        """Analyze project engagement over time"""
        projects = self.db.get_active_projects()

        insights = {
            "active_projects": len(projects),
            "projects": [],
            "recommendations": []
        }

        for project in projects:
            # Get all mentions of this project
            project_id = project["id"]

            with self.db.get_connection() as conn:
                mentions = conn.execute(
                    """
                    SELECT e.timestamp, pm.mention_type
                    FROM project_mentions pm
                    JOIN entries e ON pm.entry_id = e.id
                    WHERE pm.project_id = ?
                    ORDER BY e.timestamp DESC
                    LIMIT 100
                    """,
                    (project_id,)
                ).fetchall()

            if mentions:
                last_mention = datetime.fromisoformat(mentions[0]["timestamp"])
                days_since = (datetime.now() - last_mention).days

                project_data = {
                    "name": project["name"],
                    "total_mentions": len(mentions),
                    "days_since_last_mention": days_since,
                    "status": "active" if days_since < 7 else "stale" if days_since < 30 else "dormant"
                }

                insights["projects"].append(project_data)

                # Add recommendations
                if days_since > 14 and days_since < 60:
                    insights["recommendations"].append(
                        f"You haven't worked on '{project['name']}' in {days_since} days. Consider revisiting it!"
                    )

        return insights

    def get_creative_productivity_score(self) -> Dict[str, Any]:
        """
        Calculate a creativity/productivity score based on various factors

        Returns:
            Score (0-100) and contributing factors
        """
        streak = self.get_writing_streak()
        mood_analysis = self.analyze_temporal_mood_patterns(days=7)

        # Factors
        factors = {}

        # Consistency factor (0-30 points)
        if streak["current_streak"] >= 7:
            factors["consistency"] = 30
        elif streak["current_streak"] >= 3:
            factors["consistency"] = 20
        elif streak["current_streak"] >= 1:
            factors["consistency"] = 10
        else:
            factors["consistency"] = 0

        # Volume factor (0-30 points)
        week_entries = streak["entries_this_week"]
        if week_entries >= 7:
            factors["volume"] = 30
        elif week_entries >= 5:
            factors["volume"] = 25
        elif week_entries >= 3:
            factors["volume"] = 15
        elif week_entries >= 1:
            factors["volume"] = 10
        else:
            factors["volume"] = 0

        # Mood factor (0-20 points) - positive moods boost score
        positive_moods = ["joy", "love", "excitement", "calm"]
        dominant = mood_analysis.get("dominant_emotion_last_week")
        if dominant in positive_moods:
            factors["mood"] = 20
        else:
            factors["mood"] = 10

        # Project engagement (0-20 points)
        project_insights = self.get_project_insights()
        active_count = sum(1 for p in project_insights["projects"] if p["status"] == "active")
        if active_count >= 3:
            factors["projects"] = 20
        elif active_count >= 2:
            factors["projects"] = 15
        elif active_count >= 1:
            factors["projects"] = 10
        else:
            factors["projects"] = 5

        total_score = sum(factors.values())

        return {
            "score": total_score,
            "max_score": 100,
            "factors": factors,
            "level": self._get_productivity_level(total_score)
        }

    def _get_productivity_level(self, score: int) -> str:
        """Get productivity level description"""
        if score >= 80:
            return "🔥 On Fire"
        elif score >= 60:
            return "✨ Thriving"
        elif score >= 40:
            return "📈 Building Momentum"
        elif score >= 20:
            return "🌱 Growing"
        else:
            return "🌙 Resting Phase"

    def get_comprehensive_insights(self) -> Dict[str, Any]:
        """Get all insights in one call"""
        return {
            "streak": self.get_writing_streak(),
            "mood_patterns": self.analyze_temporal_mood_patterns(),
            "project_insights": self.get_project_insights(),
            "productivity_score": self.get_creative_productivity_score()
        }


# Singleton
_analytics_instance: Optional[DeepAnalytics] = None


def get_analytics(db) -> DeepAnalytics:
    """Get or create analytics instance"""
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = DeepAnalytics(db)
    return _analytics_instance
