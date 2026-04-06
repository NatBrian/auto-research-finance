#!/usr/bin/env python
"""
Test script for Sentiment MCP Server and SentimentEngine.

Tests:
1. SentimentEngine direct API calls
2. MCP server tools via direct function calls
3. SSL verification configuration

Usage:
    python tests/test_sentiment_mcp.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env file
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.sentiment_engine import SentimentEngine, _get_ssl_verify
from src.utils import load_config


def test_ssl_config():
    """Test SSL verification configuration is read correctly."""
    print("\n" + "=" * 60)
    print("TEST: SSL Configuration")
    print("=" * 60)

    ssl_verify = _get_ssl_verify()
    print(f"SSL verify from config: {ssl_verify}")

    config = load_config()
    ssl_config = config.get("ssl", {}).get("verify", True)
    print(f"SSL verify from config (direct): {ssl_config}")

    assert ssl_verify == ssl_config, "SSL config mismatch"
    print("✓ SSL configuration test passed")
    return ssl_verify


def test_text_sentiment():
    """Test compute_text_sentiment method."""
    print("\n" + "=" * 60)
    print("TEST: Text Sentiment Scoring")
    print("=" * 60)

    engine = SentimentEngine()

    # Test positive text
    positive_text = "This stock is amazing! Incredible growth and record earnings!"
    result = engine.compute_text_sentiment(positive_text)
    print(f"\nPositive text: '{positive_text}'")
    print(f"  VADER compound: {result['vader_compound']}")
    print(f"  TextBlob polarity: {result['textblob_polarity']}")
    print(f"  Combined score: {result['combined_score']}")
    print(f"  Label: {result['label']}")
    assert result["combined_score"] > 0, "Positive text should have positive score"

    # Test negative text
    negative_text = "Terrible losses, company is failing badly. Avoid this stock!"
    result = engine.compute_text_sentiment(negative_text)
    print(f"\nNegative text: '{negative_text}'")
    print(f"  VADER compound: {result['vader_compound']}")
    print(f"  TextBlob polarity: {result['textblob_polarity']}")
    print(f"  Combined score: {result['combined_score']}")
    print(f"  Label: {result['label']}")
    assert result["combined_score"] < 0, "Negative text should have negative score"

    print("\n✓ Text sentiment test passed")


def test_social_sentiment():
    """Test get_social_sentiment method."""
    print("\n" + "=" * 60)
    print("TEST: Social Sentiment Aggregation")
    print("=" * 60)

    engine = SentimentEngine()

    ticker = "AAPL"
    date = datetime.utcnow().strftime("%Y-%m-%d")
    lookback_days = 7

    print(f"\nFetching sentiment for {ticker} (lookback: {lookback_days} days)")
    print(f"Alpha Vantage key configured: {bool(engine._alpha_vantage_key)}")
    print(f"Reddit credentials configured: {bool(engine._reddit_client_id)}")

    result = engine.get_social_sentiment(ticker, date, lookback_days)

    print(f"\nResults:")
    print(f"  Sources used: {result['sources_used']}")
    print(f"  Total posts: {result['total_posts']}")
    print(f"  7-day average: {result['7d_avg']}")
    print(f"  Trend: {result['trend']}")

    if result['daily_scores']:
        print(f"\n  Daily scores:")
        for score in result['daily_scores'][:5]:  # Show first 5 days
            print(f"    {score['date']}: compound={score['compound']}, posts={score['post_count']}")

    print("\n✓ Social sentiment test passed")


def test_mcp_tools():
    """Test MCP server tool functions directly."""
    print("\n" + "=" * 60)
    print("TEST: MCP Server Tools")
    print("=" * 60)

    # Import MCP server functions
    sys.path.insert(0, str(PROJECT_ROOT / "mcp_servers" / "sentiment_server"))
    from server import ping_sentiment, get_social_sentiment, get_combined_sentiment
    import json

    # Test ping
    print("\n1. Testing ping_sentiment...")
    ping_result = ping_sentiment()
    ping_data = json.loads(ping_result)
    print(f"   Status: {ping_data['status']}")
    assert ping_data["status"] == "ok", "Ping failed"
    print("   ✓ Ping passed")

    # Test text sentiment
    print("\n2. Testing get_combined_sentiment...")
    text = "The market outlook is very positive with strong growth potential."
    sentiment_result = get_combined_sentiment(text)
    sentiment_data = json.loads(sentiment_result)
    print(f"   Combined score: {sentiment_data['combined_score']}")
    print(f"   Label: {sentiment_data['label']}")
    assert "combined_score" in sentiment_data, "Missing combined_score"
    print("   ✓ Text sentiment passed")

    # Test social sentiment
    print("\n3. Testing get_social_sentiment...")
    ticker = "MSFT"
    date = datetime.utcnow().strftime("%Y-%m-%d")
    social_result = get_social_sentiment(ticker, date, 7)
    social_data = json.loads(social_result)
    print(f"   Sources used: {social_data.get('sources_used', [])}")
    print(f"   Total posts: {social_data.get('total_posts', 0)}")
    print(f"   Trend: {social_data.get('trend', 'N/A')}")
    print("   ✓ Social sentiment passed")

    print("\n✓ MCP tools test passed")


def test_session_ssl():
    """Test that the session uses correct SSL verification."""
    print("\n" + "=" * 60)
    print("TEST: Session SSL Verification")
    print("=" * 60)

    engine = SentimentEngine()
    ssl_verify = _get_ssl_verify()

    print(f"Config SSL verify: {ssl_verify}")
    print(f"Session verify: {engine._session.verify}")

    assert engine._session.verify == ssl_verify, "Session SSL mismatch"
    print("✓ Session SSL test passed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("SENTIMENT ENGINE & MCP SERVER TESTS")
    print("=" * 60)

    try:
        ssl_verify = test_ssl_config()
        test_session_ssl()
        test_text_sentiment()
        test_social_sentiment()
        test_mcp_tools()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print(f"\nNote: SSL verification is {'DISABLED' if not ssl_verify else 'ENABLED'}")
        print("      (Configured in config/settings.yaml -> ssl.verify)")

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()