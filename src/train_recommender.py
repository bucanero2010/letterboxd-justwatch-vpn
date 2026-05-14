"""Train the hybrid movie recommender model.

Run this from the src/ directory:
    python train_recommender.py

This will:
1. Load your Letterboxd watch history (with ratings) from cache
2. Load MovieLens 25M interactions
3. Fetch/cache TMDB metadata
4. Generate plot embeddings
5. Train LightFM model
6. Save recommendations to data/recommendations.json

The Streamlit app will then display the results.
"""

import json
import time
from pathlib import Path

from recommender import HybridRecommender


def main():
    config = json.load(open("config.json"))
    data_dir = Path("../data")

    # Load watch history
    watch_history_path = data_dir / "watch_history_cache.json"
    if not watch_history_path.exists():
        print("❌ No watch history cache found. Run the scraper first or use the Streamlit app.")
        return

    watch_history = json.load(open(watch_history_path))
    rated = [f for f in watch_history if f.get("rating")]
    print(f"📋 Watch history: {len(watch_history)} films ({len(rated)} with ratings)")

    # Train
    rec = HybridRecommender(config=config, data_dir=data_dir)
    start = time.time()
    rec.train(watch_history, progress_callback=lambda msg: print(f"  [{time.time()-start:.0f}s] {msg}"))
    elapsed = time.time() - start
    print(f"\n✅ Training completed in {elapsed:.0f}s")

    # Generate and save recommendations
    results = rec.recommend(n=50)
    rec.serialize_results(results, data_dir / "recommendations.json")
    print(f"💾 Saved {len(results)} recommendations to data/recommendations.json")

    print("\nTop 10:")
    for r in results[:10]:
        print(f"  {r.title} ({r.year}) — {r.score:.3f}")


if __name__ == "__main__":
    main()
