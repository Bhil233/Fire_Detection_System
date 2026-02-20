import argparse
import time
from pathlib import Path

from upload_image import FireUploadClient


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch detected image folder and upload the latest saved image."
    )
    parser.add_argument(
        "--watch-dir",
        default="detected_frames",
        help="Directory where yolo.py saves detected frames",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Polling interval in seconds",
    )
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8000/api/script/detect-fire",
        help="Detection API endpoint",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds")
    parser.add_argument(
        "--min-upload-interval",
        type=float,
        default=1.0,
        help="Minimum interval between two uploads in seconds",
    )
    return parser.parse_args()


def get_latest_image_path(watch_dir: Path) -> Path | None:
    if not watch_dir.exists():
        return None

    image_files = [
        path for path in watch_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    ]
    if not image_files:
        return None

    return max(image_files, key=lambda p: p.stat().st_mtime)


def main() -> None:
    args = parse_args()
    watch_dir = Path(args.watch_dir).expanduser()
    watch_dir.mkdir(parents=True, exist_ok=True)

    client = FireUploadClient(
        endpoint=args.endpoint,
        timeout=args.timeout,
        min_interval=args.min_upload_interval,
    )

    last_uploaded_path: Path | None = None
    last_uploaded_mtime: float = -1.0

    print(f"Watching: {watch_dir.resolve()}")
    print(f"Endpoint: {args.endpoint}")

    while True:
        try:
            latest_image = get_latest_image_path(watch_dir)
            if latest_image is not None:
                latest_mtime = latest_image.stat().st_mtime
                is_new_file = last_uploaded_path is None or latest_image != last_uploaded_path
                is_updated_file = latest_image == last_uploaded_path and latest_mtime > last_uploaded_mtime

                if is_new_file or is_updated_file:
                    payload = client.upload_image(latest_image)
                    print(f"Uploaded: {latest_image}")
                    print(payload)
                    last_uploaded_path = latest_image
                    last_uploaded_mtime = latest_mtime
        except KeyboardInterrupt:
            print("Stopped.")
            break
        except Exception as exc:
            print(f"Upload failed: {exc}")

        time.sleep(max(0.1, args.poll_interval))


if __name__ == "__main__":
    main()
