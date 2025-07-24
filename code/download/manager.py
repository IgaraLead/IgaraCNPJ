"""
Download manager module for RFB ETL process.
Handles file downloads with async/threading support, retries, and progress tracking.
"""

import logging
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
import requests
from urllib.parse import urljoin
import bs4 as bs
import urllib.request
import threading


class DownloadError(Exception):
    """Custom exception for download-related errors."""

    pass


class ProgressTracker:
    """Thread-safe progress tracker for multiple downloads."""

    def __init__(self):
        self._lock = threading.Lock()
        self._file_progress = {}  # filename -> (downloaded, total)
        self._file_status = {}  # filename -> status
        self._completed_files = 0
        self._total_files = 0
        self._running = False  # Control flag for progress display

    def start(self):
        """Start progress tracking."""
        with self._lock:
            self._running = True

    def stop(self):
        """Stop progress tracking."""
        with self._lock:
            self._running = False

    def is_running(self):
        """Check if progress tracking is running."""
        with self._lock:
            return self._running

    def _format_bytes(self, bytes_value: int) -> str:
        """Convert bytes to human readable format (GB, MB, KB)."""
        if bytes_value == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(bytes_value)

        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"

    def initialize(self, filenames: List[str], operation_name: str = "DOWNLOADING"):
        """Initialize progress tracking for all files."""
        with self._lock:
            self._total_files = len(filenames)
            self._completed_files = 0
            self._operation_name = operation_name
            for filename in filenames:
                self._file_progress[filename] = (0, 0)
                self._file_status[filename] = "Pending"

    def update_file_progress(self, filename: str, downloaded: int, total: int):
        """Update progress for a specific file."""
        with self._lock:
            self._file_progress[filename] = (downloaded, total)
            if downloaded == total and total > 0:
                if self._file_status[filename] != "Completed":
                    self._file_status[filename] = "Completed"
                    self._completed_files += 1
            else:
                self._file_status[filename] = "Processing"

    def set_file_status(self, filename: str, status: str):
        """Set status for a specific file."""
        with self._lock:
            old_status = self._file_status.get(filename, "Pending")
            self._file_status[filename] = status

            if status == "Completed" and old_status != "Completed":
                self._completed_files += 1
            elif status == "Failed" and old_status == "Completed":
                self._completed_files -= 1

    def display_progress(self):
        """Display current progress for all files."""
        with self._lock:
            if not self._running:
                return

            # Clear screen and move cursor to top
            os.system("cls" if os.name == "nt" else "clear")

            operation_name = getattr(self, "_operation_name", "PROCESSING")
            print("=" * 80)
            print(f"{operation_name} FILES")
            print("=" * 80)

            # Global progress
            global_progress = (
                (self._completed_files / self._total_files * 100)
                if self._total_files > 0
                else 0
            )
            total_bar = self._create_progress_bar(global_progress, 40)
            print(
                f"TOTAL: {total_bar} {global_progress:.1f}% ({self._completed_files}/{self._total_files})"
            )
            print()

            # Individual file progress
            for filename, (downloaded, total) in self._file_progress.items():
                status = self._file_status[filename]

                if total > 0:
                    progress = (downloaded / total) * 100
                    bar = self._create_progress_bar(progress, 30)
                    downloaded_str = self._format_bytes(downloaded)
                    total_str = self._format_bytes(total)
                    size_info = f"{downloaded_str}/{total_str}"
                else:
                    progress = 0
                    bar = self._create_progress_bar(0, 30)
                    size_info = "Processing" if status == "Processing" else "Pending"

                # Truncate filename if too long
                display_name = filename[:25] + "..." if len(filename) > 28 else filename

                print(
                    f"{display_name:<32} {bar} {progress:>5.1f}% {status:<12} {size_info}"
                )

            print("=" * 80)

    def _create_progress_bar(self, percentage: float, width: int) -> str:
        """Create a visual progress bar."""
        filled = int(width * percentage / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"


class FileDownloader:
    """
    File downloader implementing async/threading for improved performance.
    Follows single responsibility principle with retry logic and progress tracking.
    """

    def __init__(self, max_workers: int = 4, max_retries: int = 3, timeout: int = 300):
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.timeout = timeout
        self._logger = logging.getLogger(__name__)
        self._progress_tracker = ProgressTracker()

    def check_file_needs_download(self, url: str, file_path: str) -> bool:
        """
        Check if file needs to be downloaded by comparing sizes.
        Returns True if download is needed, False otherwise.
        """
        if not os.path.isfile(file_path):
            return True

        try:
            response = requests.head(url, timeout=self.timeout)
            response.raise_for_status()

            remote_size = int(response.headers.get("content-length", 0))
            local_size = os.path.getsize(file_path)

            if remote_size != local_size:
                os.remove(file_path)
                return True

            return False

        except Exception as e:
            self._logger.warning(f"Error checking file {file_path}: {e}")
            return True

    def _download_with_progress(self, url: str, file_path: str) -> bool:
        """
        Download a single file with progress tracking and retry logic.
        """
        filename = os.path.basename(file_path)

        for attempt in range(self.max_retries):
            try:
                self._progress_tracker.set_file_status(
                    filename, f"Attempt {attempt + 1}"
                )

                # Use session for better connection handling
                session = requests.Session()
                response = session.get(url, stream=True, timeout=self.timeout)
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0

                # Ensure directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)
                            downloaded += len(chunk)

                            # Update progress
                            self._progress_tracker.update_file_progress(
                                filename, downloaded, total_size
                            )

                # Verify file was written correctly
                if os.path.getsize(file_path) == 0:
                    raise Exception("Downloaded file is empty (0 bytes)")

                self._progress_tracker.set_file_status(filename, "Completed")
                session.close()
                return True

            except Exception as e:
                self._progress_tracker.set_file_status(
                    filename, f"Error: {str(e)[:20]}"
                )

                # Clean up partial file
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except e:
                        pass

                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    self._progress_tracker.set_file_status(filename, "Failed")
                    return False

        return False

    def download_files_parallel(
        self, download_tasks: List[Tuple[str, str]], output_directory: str
    ) -> List[str]:
        """
        Download multiple files in parallel using ThreadPoolExecutor.
        Returns list of successfully downloaded files.
        """
        successful_downloads = []

        # Filter tasks that actually need downloading
        filtered_tasks = []
        for url, filename in download_tasks:
            file_path = os.path.join(output_directory, filename)
            if self.check_file_needs_download(url, file_path):
                filtered_tasks.append((url, file_path))
            else:
                self._logger.info(f"Skipping {filename} - already up to date")
                successful_downloads.append(file_path)

        if not filtered_tasks:
            self._logger.info("All files are up to date")
            return successful_downloads

        # Initialize progress tracking
        filenames = [os.path.basename(file_path) for _, file_path in filtered_tasks]
        self._progress_tracker.initialize(filenames, "DOWNLOADING")
        self._progress_tracker.start()

        # Ensure output directory exists
        os.makedirs(output_directory, exist_ok=True)

        # Start progress display thread
        display_thread = threading.Thread(target=self._progress_display_loop)
        display_thread.daemon = True
        display_thread.start()

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {
                executor.submit(self._download_with_progress, url, file_path): file_path
                for url, file_path in filtered_tasks
            }

            for future in as_completed(future_to_path):
                file_path = future_to_path[future]
                try:
                    success = future.result()
                    if success:
                        successful_downloads.append(file_path)
                        # Verify file size after successful download
                        file_size = os.path.getsize(file_path)
                        self._logger.debug(
                            f"Verified {os.path.basename(file_path)}: {self._progress_tracker._format_bytes(file_size)}"
                        )
                except Exception as e:
                    self._logger.error(f"Download failed for {file_path}: {e}")

        # Stop progress tracking
        self._progress_tracker.stop()

        end_time = time.time()

        # Final progress display
        self._progress_tracker.display_progress()
        print(f"\nDownload completed in {end_time - start_time:.2f} seconds")
        print(
            f"Successfully downloaded {len([f for f in successful_downloads if f in [fp for _, fp in filtered_tasks]])} new files"
        )

        return successful_downloads

    def _progress_display_loop(self):
        """Continuously update progress display."""
        while self._progress_tracker.is_running():
            self._progress_tracker.display_progress()
            time.sleep(0.5)  # Update every 500ms


class FileExtractor:
    """
    File extraction manager with error handling and progress tracking.
    Implements single responsibility principle for file extraction operations.
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._logger = logging.getLogger(__name__)
        self._progress_tracker = ProgressTracker()

    def check_file_needs_extraction(self, zip_path: str, extract_to: str) -> bool:
        """
        Check if ZIP file needs to be extracted by comparing contents.
        Returns True if extraction is needed, False otherwise.
        """
        if not os.path.isfile(zip_path):
            return False

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                file_list = zip_ref.infolist()

                # Check if all files from the ZIP exist in the extraction directory
                for file_info in file_list:
                    extracted_file_path = os.path.join(extract_to, file_info.filename)

                    # Skip directories
                    if file_info.is_dir():
                        continue

                    # If any file doesn't exist, extraction is needed
                    if not os.path.exists(extracted_file_path):
                        return True

                    # Compare file sizes
                    if os.path.getsize(extracted_file_path) != file_info.file_size:
                        return True

                    # Compare modification times (optional, more thorough check)
                    zip_modified = time.mktime(file_info.date_time + (0, 0, -1))
                    file_modified = os.path.getmtime(extracted_file_path)

                    # If ZIP file is newer than extracted file, re-extract
                    if zip_modified > file_modified + 1:  # 1 second tolerance
                        return True

                # All files exist and match, no extraction needed
                return False

        except Exception as e:
            self._logger.warning(
                f"Error checking extraction status for {zip_path}: {e}"
            )
            # If we can't check, assume extraction is needed
            return True

    def _extract_zip_file_with_progress(self, zip_path: str, extract_to: str) -> bool:
        """
        Extract a single ZIP file with progress tracking.
        """
        filename = os.path.basename(zip_path)

        try:
            self._progress_tracker.set_file_status(filename, "Extracting")

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                file_list = zip_ref.infolist()
                total_files = len(file_list)
                extracted_files = 0

                # Create extraction directory
                os.makedirs(extract_to, exist_ok=True)

                for file_info in file_list:
                    zip_ref.extract(file_info, extract_to)
                    extracted_files += 1

                    # Update progress
                    self._progress_tracker.update_file_progress(
                        filename, extracted_files, total_files
                    )

            self._progress_tracker.set_file_status(filename, "Completed")
            self._logger.info(f"Successfully extracted {filename}")
            return True

        except Exception as e:
            self._progress_tracker.set_file_status(filename, f"Error: {str(e)[:20]}")
            self._logger.error(f"Failed to extract {zip_path}: {e}")
            return False

    def extract_zip_file(self, zip_path: str, extract_to: str) -> bool:
        """
        Extract a single ZIP file with error handling.
        """
        # Check if extraction is needed
        if not self.check_file_needs_extraction(zip_path, extract_to):
            self._logger.info(
                f"Skipping {os.path.basename(zip_path)} - already extracted"
            )
            return True

        try:
            self._logger.info(f"Extracting {os.path.basename(zip_path)}")

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_to)

            self._logger.info(f"Successfully extracted {os.path.basename(zip_path)}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to extract {zip_path}: {e}")
            return False

    def extract_all_files_parallel(self, file_paths: List[str], extract_to: str) -> int:
        """
        Extract all ZIP files in parallel and return count of successful extractions.
        """
        # Filter only ZIP files
        zip_files = [fp for fp in file_paths if fp.lower().endswith(".zip")]

        if not zip_files:
            self._logger.info("No ZIP files to extract")
            return 0

        # Filter files that actually need extraction
        filtered_zip_files = []
        skipped_files = 0

        for zip_path in zip_files:
            if self.check_file_needs_extraction(zip_path, extract_to):
                filtered_zip_files.append(zip_path)
            else:
                skipped_files += 1
                self._logger.info(
                    f"Skipping {os.path.basename(zip_path)} - already extracted"
                )

        if not filtered_zip_files:
            self._logger.info(f"All {len(zip_files)} ZIP files are already extracted")
            return len(zip_files)  # Return total count since they're all "successful"

        self._logger.info(
            f"Extracting {len(filtered_zip_files)} files, skipping {skipped_files} already extracted"
        )

        successful_extractions = skipped_files  # Count skipped files as successful

        # Initialize progress tracking
        filenames = [os.path.basename(fp) for fp in filtered_zip_files]
        self._progress_tracker.initialize(filenames, "EXTRACTING")
        self._progress_tracker.start()

        # Start progress display thread
        display_thread = threading.Thread(target=self._progress_display_loop)
        display_thread.daemon = True
        display_thread.start()

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {
                executor.submit(
                    self._extract_zip_file_with_progress, zip_path, extract_to
                ): zip_path
                for zip_path in filtered_zip_files
            }

            for future in as_completed(future_to_path):
                zip_path = future_to_path[future]
                try:
                    success = future.result()
                    if success:
                        successful_extractions += 1
                except Exception as e:
                    self._logger.error(f"Extraction failed for {zip_path}: {e}")

        # Stop progress tracking
        self._progress_tracker.stop()

        end_time = time.time()

        # Final progress display
        self._progress_tracker.display_progress()
        print(f"\nExtraction completed in {end_time - start_time:.2f} seconds")
        print(f"Successfully processed {successful_extractions}/{len(zip_files)} files")
        if skipped_files > 0:
            print(f"Skipped {skipped_files} already extracted files")

        return successful_extractions

    def extract_all_files(self, file_paths: List[str], extract_to: str) -> int:
        """
        Extract all ZIP files and return count of successful extractions.
        """
        successful_extractions = 0
        skipped_files = 0

        for file_path in file_paths:
            if file_path.lower().endswith(".zip"):
                if not self.check_file_needs_extraction(file_path, extract_to):
                    skipped_files += 1
                    self._logger.info(
                        f"Skipping {os.path.basename(file_path)} - already extracted"
                    )
                    successful_extractions += (
                        1  # Count as successful since it's already done
                    )
                elif self.extract_zip_file(file_path, extract_to):
                    successful_extractions += 1

        self._logger.info(f"Processed {successful_extractions}/{len(file_paths)} files")
        if skipped_files > 0:
            self._logger.info(f"Skipped {skipped_files} already extracted files")

        return successful_extractions

    def get_extraction_info(self, file_paths: List[str], extract_to: str) -> dict:
        """
        Get detailed information about extraction status without performing extraction.
        Returns dict with counts of files that need extraction vs already extracted.
        """
        zip_files = [fp for fp in file_paths if fp.lower().endswith(".zip")]

        needs_extraction = []
        already_extracted = []

        for zip_path in zip_files:
            if self.check_file_needs_extraction(zip_path, extract_to):
                needs_extraction.append(os.path.basename(zip_path))
            else:
                already_extracted.append(os.path.basename(zip_path))

        return {
            "total_zip_files": len(zip_files),
            "needs_extraction": len(needs_extraction),
            "already_extracted": len(already_extracted),
            "files_to_extract": needs_extraction,
            "files_already_extracted": already_extracted,
        }

    def _progress_display_loop(self):
        """Continuously update progress display."""
        while self._progress_tracker.is_running():
            self._progress_tracker.display_progress()
            time.sleep(0.5)  # Update every 500ms


class RFBFileDiscovery:
    """
    Discovers RFB files from the website with robust HTML parsing.
    Implements open/closed principle for extensibility.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url
        self._logger = logging.getLogger(__name__)

    def discover_zip_files(self) -> List[str]:
        """
        Discover available ZIP files from the RFB website.
        Returns list of filenames.
        """
        try:
            self._logger.info(f"Discovering files from {self.base_url}")

            response = urllib.request.urlopen(self.base_url)
            raw_html = response.read()

            # Parse HTML content
            soup = bs.BeautifulSoup(raw_html, "lxml")
            html_str = str(soup)

            # Extract ZIP file references
            zip_files = []
            import re

            # Find all .zip references in the HTML
            zip_pattern = r'["\']([^"\']*\.zip)["\']'
            matches = re.findall(zip_pattern, html_str, re.IGNORECASE)

            # Clean and validate filenames
            for match in matches:
                # Remove any path components and keep just the filename
                filename = os.path.basename(match)
                if filename and filename.lower().endswith(".zip"):
                    zip_files.append(filename)

            # Remove duplicates while preserving order
            unique_files = []
            seen = set()
            for file in zip_files:
                if file not in seen:
                    seen.add(file)
                    unique_files.append(file)

            self._logger.info(f"Discovered {len(unique_files)} ZIP files")
            return unique_files

        except Exception as e:
            self._logger.error(f"Failed to discover files: {e}")
            raise DownloadError(f"Failed to discover files from {self.base_url}: {e}")

    def create_download_tasks(self, filenames: List[str]) -> List[Tuple[str, str]]:
        """
        Create download tasks (URL, filename) pairs from discovered filenames.
        """
        tasks = []
        for filename in filenames:
            url = urljoin(self.base_url, filename)
            tasks.append((url, filename))

        return tasks
