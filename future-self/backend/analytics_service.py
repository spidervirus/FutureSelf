import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64
from supabase import Client

class AnalyticsService:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        
    def get_emotion_trends(self, user_id: str, days: int = 30) -> Dict:
        """
        Analyze emotion trends for a user over the specified number of days
        """
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Fetch emotion data from database
            response = self.supabase.table("emotion_analysis").select(
                "timestamp, emotions, dominant_emotion, confidence"
            ).eq("user_id", user_id).gte(
                "timestamp", start_date.isoformat()
            ).lte(
                "timestamp", end_date.isoformat()
            ).order("timestamp", desc=False).execute()
            
            if not response.data:
                return {
                    "message": "No emotion data found for the specified period",
                    "trends": {},
                    "summary": {}
                }
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(response.data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Extract emotion scores
            emotion_columns = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust']
            for emotion in emotion_columns:
                df[emotion] = df['emotions'].apply(lambda x: x.get(emotion, 0) if isinstance(x, dict) else 0)
            
            # Calculate daily averages
            df['date'] = df['timestamp'].dt.date
            daily_emotions = df.groupby('date')[emotion_columns].mean()
            
            # Calculate trends
            trends = {}
            for emotion in emotion_columns:
                if len(daily_emotions) > 1:
                    # Calculate linear trend (slope)
                    x = np.arange(len(daily_emotions))
                    y = daily_emotions[emotion].values
                    slope = np.polyfit(x, y, 1)[0]
                    trends[emotion] = {
                        'trend': 'increasing' if slope > 0.01 else 'decreasing' if slope < -0.01 else 'stable',
                        'slope': float(slope),
                        'average': float(daily_emotions[emotion].mean()),
                        'current': float(daily_emotions[emotion].iloc[-1]) if len(daily_emotions) > 0 else 0
                    }
                else:
                    trends[emotion] = {
                        'trend': 'insufficient_data',
                        'slope': 0,
                        'average': float(daily_emotions[emotion].mean()) if len(daily_emotions) > 0 else 0,
                        'current': float(daily_emotions[emotion].iloc[-1]) if len(daily_emotions) > 0 else 0
                    }
            
            # Calculate summary statistics
            dominant_emotions = df['dominant_emotion'].value_counts()
            summary = {
                'total_analyses': len(df),
                'most_common_emotion': dominant_emotions.index[0] if len(dominant_emotions) > 0 else 'unknown',
                'average_confidence': float(df['confidence'].mean()),
                'emotion_distribution': dominant_emotions.to_dict(),
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }
            
            return {
                'trends': trends,
                'summary': summary,
                'daily_data': daily_emotions.to_dict('index')
            }
            
        except Exception as e:
            print(f"Error analyzing emotion trends: {e}")
            return {
                'error': f"Failed to analyze emotion trends: {str(e)}",
                'trends': {},
                'summary': {}
            }
    
    def get_bias_trends(self, user_id: str, days: int = 30) -> Dict:
        """
        Analyze bias and toxicity trends for a user over the specified number of days
        """
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Fetch bias data from database
            response = self.supabase.table("bias_analysis").select(
                "timestamp, toxicity_score, bias_patterns, language, sentiment"
            ).eq("user_id", user_id).gte(
                "timestamp", start_date.isoformat()
            ).lte(
                "timestamp", end_date.isoformat()
            ).order("timestamp", desc=False).execute()
            
            if not response.data:
                return {
                    "message": "No bias analysis data found for the specified period",
                    "trends": {},
                    "summary": {}
                }
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(response.data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Extract sentiment scores
            df['sentiment_positive'] = df['sentiment'].apply(lambda x: x.get('positive', 0) if isinstance(x, dict) else 0)
            df['sentiment_negative'] = df['sentiment'].apply(lambda x: x.get('negative', 0) if isinstance(x, dict) else 0)
            df['sentiment_neutral'] = df['sentiment'].apply(lambda x: x.get('neutral', 0) if isinstance(x, dict) else 0)
            
            # Calculate daily averages
            df['date'] = df['timestamp'].dt.date
            daily_metrics = df.groupby('date').agg({
                'toxicity_score': 'mean',
                'sentiment_positive': 'mean',
                'sentiment_negative': 'mean',
                'sentiment_neutral': 'mean'
            })
            
            # Calculate trends
            trends = {}
            metrics = ['toxicity_score', 'sentiment_positive', 'sentiment_negative', 'sentiment_neutral']
            
            for metric in metrics:
                if len(daily_metrics) > 1:
                    # Calculate linear trend (slope)
                    x = np.arange(len(daily_metrics))
                    y = daily_metrics[metric].values
                    slope = np.polyfit(x, y, 1)[0]
                    trends[metric] = {
                        'trend': 'increasing' if slope > 0.01 else 'decreasing' if slope < -0.01 else 'stable',
                        'slope': float(slope),
                        'average': float(daily_metrics[metric].mean()),
                        'current': float(daily_metrics[metric].iloc[-1]) if len(daily_metrics) > 0 else 0
                    }
                else:
                    trends[metric] = {
                        'trend': 'insufficient_data',
                        'slope': 0,
                        'average': float(daily_metrics[metric].mean()) if len(daily_metrics) > 0 else 0,
                        'current': float(daily_metrics[metric].iloc[-1]) if len(daily_metrics) > 0 else 0
                    }
            
            # Analyze bias patterns
            bias_pattern_counts = {}
            for _, row in df.iterrows():
                if isinstance(row['bias_patterns'], dict):
                    for pattern, detected in row['bias_patterns'].items():
                        if detected:
                            bias_pattern_counts[pattern] = bias_pattern_counts.get(pattern, 0) + 1
            
            # Language distribution
            language_distribution = df['language'].value_counts().to_dict()
            
            # Calculate summary statistics
            summary = {
                'total_analyses': len(df),
                'average_toxicity': float(df['toxicity_score'].mean()),
                'max_toxicity': float(df['toxicity_score'].max()),
                'bias_patterns_detected': bias_pattern_counts,
                'language_distribution': language_distribution,
                'overall_sentiment': {
                    'positive': float(df['sentiment_positive'].mean()),
                    'negative': float(df['sentiment_negative'].mean()),
                    'neutral': float(df['sentiment_neutral'].mean())
                },
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }
            
            return {
                'trends': trends,
                'summary': summary,
                'daily_data': daily_metrics.to_dict('index')
            }
            
        except Exception as e:
            print(f"Error analyzing bias trends: {e}")
            return {
                'error': f"Failed to analyze bias trends: {str(e)}",
                'trends': {},
                'summary': {}
            }
    
    def generate_emotion_chart(self, user_id: str, days: int = 30) -> Optional[str]:
        """
        Generate a base64-encoded emotion trends chart
        """
        try:
            trends_data = self.get_emotion_trends(user_id, days)
            
            if 'error' in trends_data or not trends_data.get('daily_data'):
                return None
            
            # Create DataFrame from daily data
            daily_data = trends_data['daily_data']
            dates = list(daily_data.keys())
            emotions = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust']
            
            # Prepare data for plotting
            emotion_data = {emotion: [] for emotion in emotions}
            for date in dates:
                for emotion in emotions:
                    emotion_data[emotion].append(daily_data[date].get(emotion, 0))
            
            # Create the plot
            plt.figure(figsize=(12, 8))
            for emotion in emotions:
                plt.plot(dates, emotion_data[emotion], marker='o', label=emotion.capitalize())
            
            plt.title(f'Emotion Trends Over Last {days} Days')
            plt.xlabel('Date')
            plt.ylabel('Emotion Score')
            plt.legend()
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            chart_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return chart_base64
            
        except Exception as e:
            print(f"Error generating emotion chart: {e}")
            return None
    
    def get_user_insights(self, user_id: str, days: int = 30) -> Dict:
        """
        Generate comprehensive insights combining emotion and bias analysis
        """
        try:
            emotion_trends = self.get_emotion_trends(user_id, days)
            bias_trends = self.get_bias_trends(user_id, days)
            
            insights = {
                'emotion_insights': [],
                'bias_insights': [],
                'recommendations': [],
                'overall_wellbeing_score': 0
            }
            
            # Emotion insights
            if 'trends' in emotion_trends:
                for emotion, data in emotion_trends['trends'].items():
                    if data['trend'] == 'increasing' and emotion in ['joy', 'surprise']:
                        insights['emotion_insights'].append(f"Your {emotion} levels are increasing - that's great!")
                    elif data['trend'] == 'increasing' and emotion in ['sadness', 'anger', 'fear']:
                        insights['emotion_insights'].append(f"Your {emotion} levels are increasing - consider some self-care")
                    elif data['trend'] == 'decreasing' and emotion in ['sadness', 'anger', 'fear']:
                        insights['emotion_insights'].append(f"Your {emotion} levels are decreasing - positive progress!")
            
            # Bias insights
            if 'trends' in bias_trends:
                toxicity_trend = bias_trends['trends'].get('toxicity_score', {})
                if toxicity_trend.get('trend') == 'decreasing':
                    insights['bias_insights'].append("Your communication is becoming more positive")
                elif toxicity_trend.get('trend') == 'increasing':
                    insights['bias_insights'].append("Consider reviewing your communication style")
                
                sentiment_positive = bias_trends['trends'].get('sentiment_positive', {})
                if sentiment_positive.get('trend') == 'increasing':
                    insights['bias_insights'].append("Your overall sentiment is becoming more positive")
            
            # Generate recommendations
            if emotion_trends.get('summary', {}).get('most_common_emotion') in ['sadness', 'anger', 'fear']:
                insights['recommendations'].append("Consider practicing mindfulness or talking to someone you trust")
            
            if bias_trends.get('summary', {}).get('average_toxicity', 0) > 0.5:
                insights['recommendations'].append("Try to use more positive language in your communications")
            
            # Calculate overall wellbeing score (0-100)
            emotion_score = 0
            if 'trends' in emotion_trends:
                positive_emotions = emotion_trends['trends'].get('joy', {}).get('average', 0) + \
                                 emotion_trends['trends'].get('surprise', {}).get('average', 0)
                negative_emotions = emotion_trends['trends'].get('sadness', {}).get('average', 0) + \
                                  emotion_trends['trends'].get('anger', {}).get('average', 0) + \
                                  emotion_trends['trends'].get('fear', {}).get('average', 0)
                emotion_score = max(0, min(100, (positive_emotions - negative_emotions) * 100))
            
            bias_score = 0
            if 'trends' in bias_trends:
                toxicity = bias_trends['trends'].get('toxicity_score', {}).get('average', 0)
                positive_sentiment = bias_trends['trends'].get('sentiment_positive', {}).get('average', 0)
                bias_score = max(0, min(100, (positive_sentiment - toxicity) * 100))
            
            insights['overall_wellbeing_score'] = int((emotion_score + bias_score) / 2)
            
            return insights
            
        except Exception as e:
            print(f"Error generating user insights: {e}")
            return {
                'emotion_insights': [],
                'bias_insights': [],
                'recommendations': [],
                'overall_wellbeing_score': 0,
                'error': str(e)
            }