import requests
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class GDELTClient:
    def __init__(self):
        """
        Initialize the GDELT client for fetching news data.
        """
        self.base_url = "https://api.gdeltproject.org/api/v2/doc/doc"

    def fetch_news_data(self, query: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch news data from GDELT.

        Args:
            query (str): Search query for news articles.
            start_date (str): Start date in YYYYMMDD format.
            end_date (str): End date in YYYYMMDD format.

        Returns:
            pd.DataFrame: DataFrame containing news data.
        """
        try:
            url = f"{self.base_url}?query={query}&mode=artlist&maxrecords=250&format=json&startdatetime={start_date}000000&enddatetime={end_date}235959"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if 'articles' in data:
                articles = data['articles']
                return pd.DataFrame(articles)
            else:
                logger.warning("No articles found in the response.")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching news data from GDELT: {str(e)}")
            return pd.DataFrame()

    def calculate_sentiment_score(self, articles_df: pd.DataFrame) -> float:
        """
        Calculate a refined sentiment score from the articles.

        Args:
            articles_df (pd.DataFrame): DataFrame containing news articles.

        Returns:
            float: Refined sentiment score.
        """
        if articles_df.empty:
            logger.warning("No articles to calculate sentiment score.")
            return 0.0

        # Example: Calculate a weighted sentiment score
        try:
            # Assume 'tone' is a column representing sentiment score in the articles
            # Weight by recency or relevance if available
            articles_df['weight'] = 1  # Placeholder for actual weighting logic
            weighted_score = (articles_df['tone'] * articles_df['weight']).sum() / articles_df['weight'].sum()
            return weighted_score
        except Exception as e:
            logger.error(f"Error calculating sentiment score: {str(e)}")
            return 0.0 