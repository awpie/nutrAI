import schedule
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Callable
import threading
import signal
import sys
from pathlib import Path

from database import NutritionDatabase
from scraper import scrape_all_nutrition_data  # Assuming this function exists

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NutritionScrapeScheduler:
    def __init__(self, db_path: str = "nutrition_data.db"):
        """Initialize the scraping scheduler."""
        self.db = NutritionDatabase(db_path)
        self.is_running = False
        self.scheduler_thread = None
        self._stop_event = threading.Event()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def scrape_and_store(self) -> bool:
        """
        Run a complete scraping session and store results in database.
        Uses the refresh approach: clears all data and inserts fresh data.
        Returns True if successful, False otherwise.
        """
        started_at = datetime.now(timezone.utc)
        log_id = None
        
        try:
            logger.info("Starting scheduled nutrition data scraping (full refresh)...")
            
            # Log the start of scraping session
            log_id = self.db.log_scraping_session(
                started_at=started_at,
                status='started'
            )
            
            # Call your existing scraper function
            # Note: You'll need to modify your scraper.py to return structured data
            nutrition_data = self._run_scraper()
            
            if not nutrition_data:
                logger.warning("No nutrition data returned from scraper")
                if log_id:
                    self.db.update_scraping_session(
                        log_id=log_id,
                        completed_at=datetime.now(timezone.utc),
                        items_found=0,
                        items_added=0,
                        items_updated=0,
                        status='completed_no_data'
                    )
                return False
            
            # Refresh all data in database (clear + insert)
            logger.info("Refreshing database with new data (clearing old data)...")
            items_inserted = self.db.refresh_all_data(nutrition_data)
            completed_at = datetime.now(timezone.utc)
            
            # Update the scraping log (all items are "added" since we refresh everything)
            if log_id:
                self.db.update_scraping_session(
                    log_id=log_id,
                    completed_at=completed_at,
                    items_found=len(nutrition_data),
                    items_added=items_inserted,
                    items_updated=0,  # No updates in refresh mode
                    status='completed'
                )
            
            logger.info(f"Scraping completed successfully!")
            logger.info(f"Items found: {len(nutrition_data)}")
            logger.info(f"Items inserted (after full refresh): {items_inserted}")
            logger.info(f"Duration: {(completed_at - started_at).total_seconds():.2f} seconds")
            
            return True
            
        except Exception as e:
            error_msg = f"Error during scraping: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if log_id:
                self.db.update_scraping_session(
                    log_id=log_id,
                    completed_at=datetime.now(timezone.utc),
                    status='failed',
                    error_message=error_msg
                )
            
            return False
    
    def _run_scraper(self):
        """
        Run the actual scraper and return structured data.
        This is a wrapper around your existing scraper function.
        """
        try:
            # Import and run your existing scraper
            # You might need to modify scraper.py to return data instead of just saving CSV
            from scraper import scrape_all_nutrition_data
            
            # For now, let's assume we need to call it and then read the CSV
            # You should modify this to get data directly from the scraper
            scrape_all_nutrition_data()
            
            # Find the most recent CSV file (your scraper saves with timestamp)
            csv_files = list(Path('.').glob('duke_nutrition_data_*.csv'))
            if csv_files:
                latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"Reading data from {latest_csv}")
                
                # Import from CSV and return the data
                import pandas as pd
                df = pd.read_csv(latest_csv)
                return df.to_dict('records')
            else:
                logger.warning("No CSV files found after scraping")
                return []
                
        except ImportError:
            logger.error("Could not import scraper module")
            return []
        except Exception as e:
            logger.error(f"Error running scraper: {e}")
            return []
    
    def schedule_daily_scraping(self, time_str: str = "06:00"):
        """
        Schedule daily scraping at specified time.
        time_str: Time in HH:MM format (24-hour)
        """
        schedule.clear()  # Clear any existing schedules
        
        schedule.every().day.at(time_str).do(self.scrape_and_store)
        logger.info(f"Scheduled daily scraping at {time_str}")
    
    def schedule_hourly_scraping(self):
        """Schedule scraping every hour (for testing/high-frequency updates)."""
        schedule.clear()
        schedule.every().hour.do(self.scrape_and_store)
        logger.info("Scheduled hourly scraping")
    
    def schedule_weekly_scraping(self, day: str = "monday", time_str: str = "06:00"):
        """
        Schedule weekly scraping.
        day: Day of week (monday, tuesday, etc.)
        time_str: Time in HH:MM format
        """
        schedule.clear()
        getattr(schedule.every(), day.lower()).at(time_str).do(self.scrape_and_store)
        logger.info(f"Scheduled weekly scraping on {day} at {time_str}")
    
    def run_once_now(self):
        """Run scraping immediately once."""
        logger.info("Running scraping once now...")
        return self.scrape_and_store()
    
    def start(self):
        """Start the scheduler in a background thread."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self._stop_event.clear()
        
        def scheduler_loop():
            logger.info("Scheduler started")
            while not self._stop_event.is_set():
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            logger.info("Scheduler stopped")
        
        self.scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        self.scheduler_thread.start()
    
    def stop(self):
        """Stop the scheduler."""
        if not self.is_running:
            return
        
        logger.info("Stopping scheduler...")
        self.is_running = False
        self._stop_event.set()
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
    
    def get_next_run_time(self) -> Optional[datetime]:
        """Get the next scheduled run time."""
        jobs = schedule.get_jobs()
        if not jobs:
            return None
        
        next_run = min(job.next_run for job in jobs)
        return next_run
    
    def get_schedule_info(self) -> dict:
        """Get information about current schedules."""
        jobs = schedule.get_jobs()
        return {
            'total_jobs': len(jobs),
            'next_run': self.get_next_run_time(),
            'jobs': [
                {
                    'interval': job.interval,
                    'unit': job.unit,
                    'at_time': str(job.at_time) if job.at_time else None,
                    'next_run': job.next_run
                }
                for job in jobs
            ]
        }

def main():
    """CLI interface for the scheduler."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Nutrition Data Scraping Scheduler')
    parser.add_argument('--db-path', default='nutrition_data.db', help='Database path')
    parser.add_argument('--schedule', choices=['daily', 'hourly', 'weekly'], 
                       default='daily', help='Schedule frequency')
    parser.add_argument('--time', default='06:00', help='Time for daily/weekly schedule (HH:MM)')
    parser.add_argument('--day', default='monday', help='Day for weekly schedule')
    parser.add_argument('--run-once', action='store_true', help='Run once immediately and exit')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    scheduler = NutritionScrapeScheduler(args.db_path)
    
    if args.run_once:
        success = scheduler.run_once_now()
        sys.exit(0 if success else 1)
    
    # Set up schedule
    if args.schedule == 'daily':
        scheduler.schedule_daily_scraping(args.time)
    elif args.schedule == 'hourly':
        scheduler.schedule_hourly_scraping()
    elif args.schedule == 'weekly':
        scheduler.schedule_weekly_scraping(args.day, args.time)
    
    # Print schedule info
    schedule_info = scheduler.get_schedule_info()
    logger.info(f"Schedule configured: {schedule_info}")
    
    # Start scheduler
    scheduler.start()
    
    if args.daemon:
        # Run as daemon
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
    else:
        # Interactive mode
        print("\nScheduler is running. Commands:")
        print("  'q' or 'quit' - Stop scheduler and exit")
        print("  'r' or 'run' - Run scraping now")
        print("  's' or 'status' - Show status")
        print("  'h' or 'help' - Show this help")
        
        while True:
            try:
                cmd = input("\n> ").strip().lower()
                
                if cmd in ('q', 'quit', 'exit'):
                    break
                elif cmd in ('r', 'run'):
                    print("Running scraping...")
                    success = scheduler.run_once_now()
                    print(f"Scraping {'completed successfully' if success else 'failed'}")
                elif cmd in ('s', 'status'):
                    info = scheduler.get_schedule_info()
                    print(f"Schedule: {info}")
                    history = scheduler.db.get_scraping_history(5)
                    print(f"Recent runs: {len(history)} entries")
                    for entry in history[:3]:
                        print(f"  {entry['started_at']}: {entry['status']} "
                              f"({entry['items_added']} added, {entry['items_updated']} updated)")
                elif cmd in ('h', 'help'):
                    print("Available commands: quit, run, status, help")
                else:
                    print("Unknown command. Type 'help' for available commands.")
                    
            except (EOFError, KeyboardInterrupt):
                break
    
    scheduler.stop()
    logger.info("Scheduler terminated")

if __name__ == "__main__":
    main() 