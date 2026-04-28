import logging
import sys
import time
from datetime import datetime

from foxhole import (
    append_to_csv,
    cfg,
    close_activity_log,
    focus_game_window,
    get_visible_players,
    is_already_seen,
    load_seen_names,
    ocr_activity_log,
    open_regiment_screen,
    scroll_down_one_page,
    smooth_click,
    smooth_move,
)

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    cfg.paths.logs.mkdir(exist_ok=True)
    log_file = cfg.paths.logs / f"scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file)],
    )


def scrape_regiment() -> None:
    logger.info("Focusing Foxhole window...")
    focus_game_window()
    open_regiment_screen()
    logger.info("Foxhole window focused.")


    csv_path = cfg.paths.output / cfg.output.csv
    seen_names, rescan_names = load_seen_names(csv_path)
    partial_names: list[tuple[str, int]] = []
    total_written = 0
    page = 0
    click_x = (cfg.screen.name_crop_x1 + cfg.screen.name_crop_x2) // 2

    try:
        while True:
            logger.info(f"=== Page {page} ===")
            players = get_visible_players()
            all_seen = seen_names | rescan_names
            new_players = [
                p for p in players
                if not is_already_seen(p["name"], seen_names, rescan_names, all_seen)
            ]

            if not new_players:
                logger.info("No new players on this page, scrolling...")
                scroll_down_one_page()
                page += 1
                continue

            skipped = len(players) - len(new_players)
            if skipped:
                logger.info(f"Skipping {skipped} already-processed player(s).")
            logger.info(f"{len(new_players)} new player(s) to process.")

            for player in new_players:
                name = player["name"]
                click_y = player["screen_y"] - cfg.ocr.click_y_offset

                logger.info(f"[{len(seen_names) + 1}] Processing '{name}' at y={click_y}")

                smooth_click(click_x, click_y)
                time.sleep(cfg.timing.delay_click)

                smooth_click(click_x + cfg.screen.menu_offset_x, click_y + cfg.screen.menu_offset_y)
                smooth_move(cfg.screen.name_crop_x1, cfg.screen.name_crop_y2 + cfg.ocr.mouse_park_y_offset)
                time.sleep(cfg.timing.delay_log_open)

                log_data = ocr_activity_log(name)
                null_count = sum(1 for v in log_data.values() if v is None)

                if null_count > 0:
                    logger.warning(f"  {null_count} null(s) on first attempt, retrying...")
                    time.sleep(cfg.timing.delay_retry)
                    retry_data = ocr_activity_log(name)

                    merged = {
                        k: log_data[k] if log_data[k] is not None else retry_data[k]
                        for k in cfg.ocr.expected_keys
                    }
                    merged_nulls = sum(1 for v in merged.values() if v is None)
                    logger.info(f"  Merged attempts: {null_count} -> {merged_nulls} null(s).")
                    log_data, null_count = merged, merged_nulls

                log_data["player_name"] = name
                append_to_csv(log_data, csv_path, overwrite_name=name if name in rescan_names else None)
                seen_names.add(name)
                rescan_names.discard(name)
                total_written += 1

                if null_count > 0:
                    partial_names.append((name, null_count))
                    logger.warning(f"  (partial) '{name}' saved with {null_count} null(s).")
                else:
                    logger.info(f"  '{name}' fully captured.")

                close_activity_log()

            logger.info(f"Page {page} done, advancing...")
            scroll_down_one_page()
            page += 1

    except KeyboardInterrupt:
        logger.info("Interrupted by user.")

    logger.info("=" * 40)
    logger.info(f"Written this run : {total_written}")
    logger.info(f"Total in CSV     : {len(seen_names)}")
    logger.info(f"Partial (nulls)  : {len(partial_names)}")
    if partial_names:
        for pname, count in partial_names:
            logger.warning(f"  {pname}: {count} null(s)")
    logger.info(f"Output file      : {csv_path}")


if __name__ == "__main__":
    _setup_logging()
    try:
        logger.info("Starting in 5 seconds — switch to Foxhole and open the regiment screen...")
        time.sleep(5)
        scrape_regiment()
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)
