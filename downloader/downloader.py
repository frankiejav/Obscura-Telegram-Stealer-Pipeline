import os
import asyncio
import time
import re
import emoji
import unicodedata
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient, events, types
from telethon.tl.types import Document, InputPeerChannel, PeerChannel, DocumentAttributeFilename
from loguru import logger
import config
from colorama import init, Fore, Style
import magic
import hashlib
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint
from collections import defaultdict
import concurrent.futures

init()
console = Console()

os.makedirs(getattr(config, 'LOG_PATH', './logs'), exist_ok=True)

def sanitize_filename(filename):
    """Remove or replace special characters from filename."""
    filename = emoji.replace_emoji(filename, replace='')
    filename = unicodedata.normalize('NFKD', filename)
    sanitized = filename.replace(' ', '-')
    sanitized = re.sub(r'[\[\]<>:"/\\|?*]', '_', sanitized)
    sanitized = ''.join(char for char in sanitized if ord(char) < 128)
    sanitized = re.sub(r'[-_]+', '-', sanitized)
    sanitized = sanitized.strip('-_')
    
    if not sanitized:
        sanitized = 'unnamed'
    return sanitized

logger.add(
    os.path.join(getattr(config, 'LOG_PATH', './logs'), "telegram_scraper_{time}.log"),
    rotation=getattr(config, 'LOG_ROTATION', '10 MB'),
    retention=getattr(config, 'LOG_RETENTION', '1 week'),
    level=getattr(config, 'LOG_LEVEL', 'INFO'),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

def format_console(message):
    """Format message for console output with colors and symbols."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if "Successfully downloaded" in message:
        return f"{Fore.GREEN}✓ {timestamp} | {message}{Style.RESET_ALL}"
    elif "Downloading" in message:
        return f"{Fore.CYAN}↓ {timestamp} | {message}{Style.RESET_ALL}"
    elif "Error" in message:
        return f"{Fore.RED}✗ {timestamp} | {message}{Style.RESET_ALL}"
    elif "Found file" in message:
        return f"{Fore.YELLOW}• {timestamp} | {message}{Style.RESET_ALL}"
    else:
        return f"{Fore.WHITE}ℹ {timestamp} | {message}{Style.RESET_ALL}"

logger.add(lambda msg: print(format_console(msg)), level=getattr(config, 'LOG_LEVEL', 'INFO'))

class OptimizedTelegramScraper:
    def __init__(self):
        self.client = TelegramClient('telegram_scraper_session', config.API_ID, config.API_HASH, 
                                   system_version="4.16.30-vxCUSTOM")
        self.downloaded_files = set()
        self.connection_errors = 0
        self.channel_folders = {}
        self.message_cache = {}
        self.setup_directories()

    def setup_directories(self):
        """Create necessary directories for downloads."""
        os.makedirs(getattr(config, 'DOWNLOAD_PATH', './downloads'), exist_ok=True)

    async def get_channel_entity(self, channel_identifier):
        """Get channel entity with caching."""
        if channel_identifier in self.message_cache:
            return self.message_cache[channel_identifier].get('entity')
            
        try:
            if isinstance(channel_identifier, str) and channel_identifier.isdigit():
                channel_id = int(channel_identifier)
                entity = await self.client.get_entity(PeerChannel(channel_id))
            else:
                try:
                    entity = await self.client.get_entity(channel_identifier)
                except ValueError:
                    if not channel_identifier.startswith('@'):
                        entity = await self.client.get_entity(f"@{channel_identifier}")
                    else:
                        raise
            
            if channel_identifier not in self.message_cache:
                self.message_cache[channel_identifier] = {}
            self.message_cache[channel_identifier]['entity'] = entity
            return entity
            
        except ValueError as e:
            logger.error(f"Error getting channel entity: {str(e)}")
            return None

    async def get_messages_bulk(self, channel):
        """Get ALL messages in bulk with optimized fetching."""
        cache_key = f"{channel.id}_messages"
        if cache_key in self.message_cache:
            cached_time = self.message_cache[cache_key].get('timestamp', 0)
            if time.time() - cached_time < 300:
                logger.info(f"Using cached messages for channel {channel.title}")
                return self.message_cache[cache_key]['messages']
        
        try:
            logger.info(f"Fetching ALL messages from {channel.title}")
            
            messages = await self.client.get_messages(
                channel,
                limit=None,
                filter=types.InputMessagesFilterDocument
            )
            
            logger.info(f"Found {len(messages)} document messages in {channel.title}")
            
            if not messages:
                logger.warning(f"No document messages found with filter, trying manual check...")
                
                all_messages = []
                batch_size = 100
                offset_id = 0
                
                while True:
                    batch = await self.client.get_messages(
                        channel, 
                        limit=batch_size,
                        offset_id=offset_id
                    )
                    
                    if not batch:
                        break
                        
                    all_messages.extend(batch)
                    offset_id = batch[-1].id
                    
                    if len(all_messages) % 1000 == 0:
                        logger.info(f"Processed {len(all_messages)} messages...")
                
                logger.info(f"Total messages in channel: {len(all_messages)}")
                doc_messages = [msg for msg in all_messages if msg.file]
                logger.info(f"Messages with files (manual filter): {len(doc_messages)}")
                messages = doc_messages
            
            self.message_cache[cache_key] = {
                'messages': messages,
                'timestamp': time.time()
            }
            
            return messages
            
        except Exception as e:
            logger.error(f"Error fetching messages from {channel.title}: {str(e)}")
            return []

    def is_file_already_downloaded(self, message, target_dir):
        """Check if file is already downloaded with enhanced matching."""
        if not message.file or not message.file.name:
            return False
            
        file_name = self.get_processed_filename(message)
        file_path = os.path.join(target_dir, file_name)
        
        if os.path.exists(file_path):
            try:
                if os.path.getsize(file_path) == message.file.size:
                    logger.debug(f"File already downloaded: {file_name}")
                    return True
                else:
                    logger.debug(f"File exists but size mismatch: {file_name}")
                    return False
            except OSError:
                return False
        
        base_name = os.path.splitext(message.file.name)[0]
        extension = os.path.splitext(message.file.name)[1]
        
        possible_names = [
            f"{base_name}_password-NOPASSWORD{extension}",
            f"{base_name}{extension}",
        ]
        
        for possible_name in possible_names:
            possible_path = os.path.join(target_dir, possible_name)
            if os.path.exists(possible_path):
                try:
                    if os.path.getsize(possible_path) == message.file.size:
                        logger.debug(f"File already downloaded with different name: {possible_name}")
                        return True
                except OSError:
                    continue
        
        return False

    async def download_existing_files(self):
        """Download existing files with enhanced performance."""
        logger.info("Starting optimized file download from channels")
        
        if len(config.TARGETS) > 1 and getattr(config, 'ENABLE_PARALLEL_DOWNLOADS', True):
            await self.download_multiple_channels_parallel()
        else:
            await self.download_channels_sequential()

    async def download_multiple_channels_parallel(self):
        """Download from multiple channels in parallel."""
        console.print(Panel.fit(
            "[yellow]Processing multiple channels in parallel...[/yellow]",
            title="Parallel Processing",
            border_style="yellow"
        ))
        
        channel_semaphore = asyncio.Semaphore(3)
        
        async def process_channel(username):
            async with channel_semaphore:
                return await self.process_single_channel(username)
        
        tasks = [process_channel(username) for username in config.TARGETS.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_downloaded = sum(r[0] if isinstance(r, tuple) else 0 for r in results)
        total_failed = sum(r[1] if isinstance(r, tuple) else 0 for r in results)
        
        console.print(f"\n[green]Overall Summary:[/green]")
        self.print_download_summary(total_downloaded, total_failed, 0)

    async def download_channels_sequential(self):
        """Download from channels one by one with optimization."""
        for username in config.TARGETS.keys():
            await self.process_single_channel(username)

    async def process_single_channel(self, username):
        """Process a single channel with optimizations."""
        try:
            logger.info(f"Starting to process channel: {username}")
            channel = await self.get_channel_entity(username)
            if not channel:
                logger.error(f"Could not find channel: {username}")
                return 0, 1
            
            channel_title = getattr(channel, 'title', username)
            console.print(f"\n[cyan]Processing channel: {channel_title}[/cyan]")
            console.print(f"[blue]Scanning ALL messages in channel (this may take a while for large channels)...[/blue]")
            logger.info(f"Connected to channel: {channel_title} (ID: {channel.id})")
            
            with console.status(f"[bold green]Fetching all messages from {channel_title}...") as status:
                messages = await self.get_messages_bulk(channel)
            
            if not messages:
                console.print(f"[yellow]No messages found in {channel_title}[/yellow]")
                logger.warning(f"No messages returned from {channel_title}")
                return 0, 0
            
            logger.info(f"Processing {len(messages)} messages from {channel_title}")
            console.print(f"[green]Found {len(messages)} total messages with files[/green]")
            
            messages.sort(key=lambda x: x.date)
            
            console.print(f"[blue]Checking for new files to download...[/blue]")
            valid_files = []
            skipped_reasons = defaultdict(int)
            target_name = config.TARGETS.get(username, username) if hasattr(config, 'TARGETS') and config.TARGETS else username
            target_dir = os.path.join(getattr(config, 'DOWNLOAD_PATH', './downloads'), target_name)
            
            os.makedirs(target_dir, exist_ok=True)
            
            for msg in messages:
                if not msg.file:
                    skipped_reasons['no_file'] += 1
                    continue
                    
                if not self.should_download_file(msg):
                    if not msg.file.name:
                        skipped_reasons['no_filename'] += 1
                    elif msg.file.size > getattr(config, 'MAX_FILE_SIZE', 2 * 1024 * 1024 * 1024):
                        skipped_reasons['too_large'] += 1
                    else:
                        skipped_reasons['wrong_extension'] += 1
                    continue
                
                if self.is_file_already_downloaded(msg, target_dir):
                    skipped_reasons['already_downloaded'] += 1
                    continue
                    
                valid_files.append(msg)
            
            logger.info(f"File filtering results for {channel_title}:")
            logger.info(f"  Valid files to download: {len(valid_files)}")
            for reason, count in skipped_reasons.items():
                logger.info(f"  Skipped ({reason}): {count}")
            
            if skipped_reasons:
                skip_table = Table(title=f"Files Skipped in {channel_title}", border_style="yellow")
                skip_table.add_column("Reason", style="cyan")
                skip_table.add_column("Count", style="yellow")
                
                reason_labels = {
                    'no_file': 'No file attached',
                    'no_filename': 'No filename',
                    'too_large': 'File too large',
                    'wrong_extension': 'Wrong file type',
                    'already_downloaded': 'Already downloaded'
                }
                
                for reason, count in skipped_reasons.items():
                    skip_table.add_row(reason_labels.get(reason, reason), str(count))
                
                console.print(skip_table)
            
            if not valid_files:
                console.print(f"[yellow]No new files to download in {channel_title}[/yellow]")
                return 0, 0
            
            console.print(f"[green]Found {len(valid_files)} new files to download[/green]")
            
            downloaded, failed = await self.download_files_optimized(valid_files, username)
            
            console.print(f"[green]Channel {channel_title}: Downloaded {downloaded}, Failed {failed}[/green]")
            return downloaded, failed
            
        except Exception as e:
            logger.error(f"Error processing channel {username}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return 0, 1

    async def download_files_optimized(self, messages, username):
        """Download files with optimized batching and concurrency."""
        total_files = len(messages)
        downloaded = 0
        failed = 0
        
        batch_size = getattr(config, 'BATCH_SIZE', 15)
        enable_parallel = getattr(config, 'ENABLE_PARALLEL_DOWNLOADS', True)
        max_concurrent = getattr(config, 'MAX_CONCURRENT_DOWNLOADS', 12)
        inter_batch_delay = getattr(config, 'INTER_BATCH_DELAY', 0.5)
        
        target_name = config.TARGETS.get(username, username) if hasattr(config, 'TARGETS') and config.TARGETS else username
        
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            console.print(f"\n[cyan]Processing batch {i//batch_size + 1} of {(len(messages) + batch_size - 1)//batch_size}[/cyan]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                overall_task = progress.add_task(
                    f"[cyan]Total Progress ({downloaded}/{total_files} files)",
                    total=total_files
                )
                
                file_tasks = {}
                for message in batch:
                    file_name = message.file.name or "unknown"
                    file_size = message.file.size or 0
                    task = progress.add_task(
                        f"[yellow]Queued: {file_name}",
                        total=file_size,
                        visible=True
                    )
                    file_tasks[message.id] = task
                
                async def download_single_optimized(message):
                    nonlocal downloaded, failed
                    task_id = file_tasks[message.id]
                    
                    try:
                        file_name = message.file.name or "unknown"
                        file_size = message.file.size or 0
                        
                        progress.update(task_id, description=f"[cyan]Starting: {file_name}")
                        
                        target_dir = os.path.join(getattr(config, 'DOWNLOAD_PATH', './downloads'), target_name)
                        processed_name = self.get_processed_filename(message)
                        file_path = os.path.join(target_dir, processed_name)
                        
                        os.makedirs(target_dir, exist_ok=True)
                        
                        progress.update(task_id, description=f"[cyan]Downloading: {file_name}")
                        
                        await message.download_media(
                            file_path,
                            progress_callback=lambda current, total: progress.update(
                                task_id, completed=current, total=total
                            )
                        )
                        
                        downloaded += 1
                        progress.update(
                            overall_task,
                            description=f"[cyan]Total Progress ({downloaded}/{total_files} files)",
                            advance=1
                        )
                        progress.update(task_id, description=f"[green]Complete: {file_name}", visible=False)
                        return True
                        
                    except Exception as e:
                        logger.error(f"Error downloading file: {str(e)}")
                        failed += 1
                        progress.update(overall_task, advance=1)
                        progress.update(task_id, description=f"[red]Failed: {file_name}", visible=False)
                        return False
                
                if enable_parallel:
                    semaphore = asyncio.Semaphore(max_concurrent)
                    
                    async def download_with_semaphore(message):
                        async with semaphore:
                            return await download_single_optimized(message)
                    
                    tasks = [download_with_semaphore(msg) for msg in batch]
                    await asyncio.gather(*tasks)
                else:
                    for message in batch:
                        await download_single_optimized(message)
                        await asyncio.sleep(0.1)
            
            await asyncio.sleep(inter_batch_delay)
        
        return downloaded, failed

    def get_processed_filename(self, message):
        """Get the processed filename with password extraction."""
        file_name = message.file.name or "unknown"
        pw, safe_pw = extract_password_from_message(message)
        name, ext = os.path.splitext(file_name)
        
        if pw:
            return f"{name}_password-{pw}{ext}"
        else:
            return f"{name}_password-NOPASSWORD{ext}"

    async def get_user_channels(self):
        """Fetch user channels with caching."""
        cache_key = "user_channels"
        if cache_key in self.message_cache:
            cached_time = self.message_cache[cache_key].get('timestamp', 0)
            if time.time() - cached_time < 600:
                return self.message_cache[cache_key]['channels']
        
        try:
            dialogs = await self.client.get_dialogs()
            channels = []
            
            for dialog in dialogs:
                if isinstance(dialog.entity, (types.Channel, types.Chat)):
                    channel_info = {
                        'id': dialog.entity.id,
                        'title': dialog.entity.title,
                        'username': getattr(dialog.entity, 'username', None),
                        'type': 'Channel' if isinstance(dialog.entity, types.Channel) else 'Group'
                    }
                    channels.append(channel_info)
            
            self.message_cache[cache_key] = {
                'channels': channels,
                'timestamp': time.time()
            }
            
            return channels
        except Exception as e:
            logger.error(f"Error fetching channels: {str(e)}")
            return []

    async def select_channels(self):
        """Enhanced channel selection with search capability."""
        channels = await self.get_user_channels()
        
        if not channels:
            console.print(Panel.fit(
                "[red]No channels found or error fetching channels[/red]",
                title="Error",
                border_style="red"
            ))
            return False

        channels.sort(key=lambda x: x['title'].lower())

        table = Table(
            title=f"Available Channels and Groups ({len(channels)} total)",
            show_header=True,
            header_style="bold magenta",
            border_style="blue"
        )
        table.add_column("#", style="cyan", width=4)
        table.add_column("Name", style="green")
        table.add_column("Username/ID", style="yellow")
        table.add_column("Type", style="blue")

        for idx, channel in enumerate(channels, 1):
            username = f"@{channel['username']}" if channel['username'] else f"ID: {channel['id']}"
            table.add_row(
                str(idx),
                channel['title'],
                username,
                channel['type']
            )

        console.print(table)
        console.print("\n[bold cyan]Enhanced Selection Options:[/bold cyan]")
        console.print("• Enter channel numbers separated by commas (e.g., 1,3,5)")
        console.print("• Type 'all' to select all channels")
        console.print("• Type 'search:keyword' to filter channels by name")
        console.print("• Press Enter to confirm your selection\n")

        while True:
            try:
                selection = console.input("[bold green]Enter selection:[/bold green] ").strip()
                
                if selection.lower() == 'all':
                    selected_channels = channels
                elif selection.lower().startswith('search:'):
                    keyword = selection[7:].lower()
                    filtered = [ch for ch in channels if keyword in ch['title'].lower()]
                    if not filtered:
                        console.print(f"[yellow]No channels found matching '{keyword}'[/yellow]")
                        continue
                    
                    console.print(f"\n[cyan]Channels matching '{keyword}':[/cyan]")
                    for i, ch in enumerate(filtered, 1):
                        console.print(f"{i}. {ch['title']}")
                    
                    sub_selection = console.input("[bold green]Select from filtered results (or 'all'):[/bold green] ")
                    if sub_selection.lower() == 'all':
                        selected_channels = filtered
                    else:
                        indices = [int(idx.strip()) - 1 for idx in sub_selection.split(',')]
                        selected_channels = [filtered[idx] for idx in indices if 0 <= idx < len(filtered)]
                else:
                    indices = [int(idx.strip()) - 1 for idx in selection.split(',')]
                    selected_channels = [channels[idx] for idx in indices if 0 <= idx < len(channels)]

                if not selected_channels:
                    console.print(Panel.fit(
                        "[yellow]No valid channels selected. Please try again.[/yellow]",
                        title="Warning",
                        border_style="yellow"
                    ))
                    continue

                config.TARGETS.clear()
                for channel in selected_channels:
                    identifier = channel['username'] if channel['username'] else str(channel['id'])
                    config.TARGETS[identifier] = channel['title']
                
                summary_table = Table(
                    title="Selected Channels",
                    show_header=True,
                    header_style="bold green",
                    border_style="green"
                )
                summary_table.add_column("Name", style="cyan")
                summary_table.add_column("Identifier", style="yellow")
                
                for channel in selected_channels:
                    identifier = channel['username'] if channel['username'] else str(channel['id'])
                    summary_table.add_row(channel['title'], identifier)
                
                console.print("\n")
                console.print(summary_table)
                console.print(f"\n[green]Selected {len(selected_channels)} channels[/green]")
                return True

            except (ValueError, IndexError):
                console.print(Panel.fit(
                    "[red]Invalid selection. Please enter valid numbers separated by commas.[/red]",
                    title="Error",
                    border_style="red"
                ))
            except Exception as e:
                console.print(Panel.fit(
                    f"[red]Error during channel selection: {str(e)}[/red]",
                    title="Error",
                    border_style="red"
                ))
                return False

    def should_download_file(self, message):
        """Enhanced file filtering with better performance and debugging."""
        if not message.file:
            logger.debug("Message has no file")
            return False
            
        if not hasattr(message.file, 'name') or not message.file.name:
            logger.debug("File has no name")
            return False
            
        file_name = message.file.name
        file_ext = os.path.splitext(file_name)[1].lower()
        file_size = message.file.size
        
        logger.debug(f"Checking file: {file_name} ({file_size} bytes, ext: {file_ext})")
        
        max_size = getattr(config, 'MAX_FILE_SIZE', 2 * 1024 * 1024 * 1024)
        if file_size > max_size:
            logger.debug(f"File {file_name} too large: {file_size} > {max_size}")
            return False
            
        allowed_exts = getattr(config, 'ALLOWED_EXTENSIONS', {'.zip', '.rar', '.txt', '.log', '.7z', '.gz', '.json', '.csv'})
        if file_ext not in allowed_exts:
            logger.debug(f"File extension {file_ext} not in allowed list: {allowed_exts}")
            return False
        
        logger.debug(f"File {file_name} passed all checks")
        return True

    async def start(self):
        """Enhanced startup with better error handling."""
        try:
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                phone = console.input("[bold yellow]Phone number (with country code, e.g. +1234567890):[/bold yellow] ")
                await self.client.send_code_request(phone)
                code = console.input("[bold yellow]Verification code:[/bold yellow] ")
                await self.client.sign_in(phone, code)
            
            console.print(Panel.fit(
                "[green]Successfully connected to Telegram[/green]",
                title="Connection Status",
                border_style="green"
            ))
            
            if not await self.select_channels():
                console.print(Panel.fit(
                    "[red]Failed to select channels. Exiting...[/red]",
                    title="Error",
                    border_style="red"
                ))
                return
            
            perf_table = Table(title="Performance Settings", border_style="blue")
            perf_table.add_column("Setting", style="cyan")
            perf_table.add_column("Value", style="green")
            
            perf_table.add_row("Parallel Downloads", str(getattr(config, 'ENABLE_PARALLEL_DOWNLOADS', True)))
            perf_table.add_row("Max Concurrent", str(getattr(config, 'MAX_CONCURRENT_DOWNLOADS', 12)))
            perf_table.add_row("Batch Size", str(getattr(config, 'BATCH_SIZE', 15)))
            perf_table.add_row("Inter-batch Delay", f"{getattr(config, 'INTER_BATCH_DELAY', 0.5)}s")
            
            console.print(perf_table)
            
            start_time = time.time()
            await self.download_existing_files()
            end_time = time.time()
            
            console.print(f"\n[green]Download completed in {end_time - start_time:.1f} seconds[/green]")
            
        except KeyboardInterrupt:
            console.print(Panel.fit(
                "[yellow]Shutdown requested by user[/yellow]",
                title="Shutdown",
                border_style="yellow"
            ))
        except Exception as e:
            console.print(Panel.fit(
                f"[red]Error: {str(e)}[/red]",
                title="Error",
                border_style="red"
            ))
            raise
        finally:
            await self.client.disconnect()

    def print_download_summary(self, successful: int, failed: int, skipped: int) -> None:
        """Enhanced download summary."""
        table = Table(title="Download Summary")
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="green")
        table.add_column("Percentage", style="blue")
        
        total = successful + failed + skipped
        
        if total > 0:
            table.add_row("✅ Successful", str(successful), f"{successful/total*100:.1f}%")
            table.add_row("❌ Failed", str(failed), f"{failed/total*100:.1f}%")
            table.add_row("⭕ Skipped", str(skipped), f"{skipped/total*100:.1f}%")
            table.add_row("📊 Total", str(total), "100.0%")
        else:
            table.add_row("📊 Total", "0", "0%")
        
        console.print(table)

def extract_password_from_message(message):
    """Enhanced password extraction with more patterns."""
    if not message.message:
        return None, None
    
    patterns = [
        r'(?i)(?:🗃\s*)?(?:пароль\s*/\s*)?pass(?:word)?\s*:\s*(@\w+)',
        r'(?i)(?:🔶🔶)?pass(?:word)?\s+(@\w+)',
        r'(?i)pass(?:word)?\s+for\s+archive\s*:\s*(@\w+)',
        r'(?i)(?:📁\s*)?pass\s*:\s*(https://t\.me/\w+)',
        r'(?i)pass(?:word)?\s+for\s+archive\s*:?\s*\(([^)]+)\)',
        r'(?i)pass(?:word)?\s*[:\s]*\(([^)]+)\)',
        r'(?i)pass(?:word)?\s*:\s*([^\s\n]+)',
        r'(?i)pass(?:word)?\s+for\s+archive\s+([^\s\n]+)',
        r'(?i)🔐\s*([^\s\n]+)',
        r'(?i)key\s*:\s*([^\s\n]+)',
    ]
    
    text = message.message
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            pw = match.group(1).strip()
            if pw.startswith('@'):
                pw = pw[1:]
            if pw.startswith('https://t.me/'):
                pw = pw.replace('https://t.me/', '')
            
            safe_pw = re.sub(r'[^\w.-]', '_', pw)
            return pw, safe_pw
    
    return None, None

async def main():
    """Enhanced main function."""
    scraper = OptimizedTelegramScraper()
    try:
        await scraper.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        logger.info("Disconnected from Telegram")

if __name__ == "__main__":
    asyncio.run(main())