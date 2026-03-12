"""
Entry point for the LinkedIn Outreach Intelligence Tool.
Usage:
    python main.py                          # Full run (discovery + enrichment)
    python main.py --skip-discovery         # Re-enrich from checkpoint
    python main.py --skip-enrichment        # Discovery only → CSV
    python main.py --skip-db               # Run pipeline but don't push to Supabase
    python main.py --setup-db              # Print SQL to set up Supabase table
"""

import sys
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/pipeline.log", mode="a"),
    ],
)

logger = logging.getLogger(__name__)


def check_env() -> bool:
    """Warn about missing API keys before starting."""
    from config import APIFY_TOKEN, RAPIDAPI_KEY, SUPABASE_URL, SUPABASE_KEY
    missing = []
    if not APIFY_TOKEN:
        missing.append("APIFY_TOKEN")
    if not RAPIDAPI_KEY:
        missing.append("RAPIDAPI_KEY")
    if missing:
        logger.warning(
            f"Missing API keys: {', '.join(missing)}. "
            "Some sources will be skipped. Add them to your .env file."
        )
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning(
            "SUPABASE_URL / SUPABASE_KEY not set. "
            "Leads will be saved to CSV only (no cloud dashboard)."
        )
    return True  # non-fatal — we run with what's available


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Outreach Intelligence Tool")
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip scraping — load from last checkpoint and re-enrich",
    )
    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        help="Run discovery only — export raw leads to CSV",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Don't push to Supabase — CSV only",
    )
    parser.add_argument(
        "--setup-db",
        action="store_true",
        help="Print the SQL needed to set up the Supabase table, then exit",
    )
    args = parser.parse_args()

    if args.setup_db:
        from database import create_table_if_not_exists
        create_table_if_not_exists()
        return

    check_env()

    from pipeline import run_pipeline
    leads = run_pipeline(
        skip_discovery=args.skip_discovery,
        skip_enrichment=args.skip_enrichment,
        skip_db=args.skip_db,
    )

    # Quick summary for the terminal
    if leads:
        top5 = leads[:5]
        print("\n── Top 5 Leads by Quality Score ──")
        for i, lead in enumerate(top5, 1):
            print(
                f"  {i}. {lead.get('name','N/A')} ({lead.get('title','?')}) "
                f"at {lead.get('company','?')} "
                f"— Score: {lead.get('quality_score', 0)} "
                f"[{lead.get('lead_temperature', '?')}]"
            )
        print(f"\n  Full list: output/leads.csv")
        print("  Dashboard: run 'streamlit run streamlit_app.py'")


if __name__ == "__main__":
    main()
