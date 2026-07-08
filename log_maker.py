import os
import time
import colorama
import logging
from pathlib import Path
from discord_webhook import DiscordWebhook, DiscordEmbed

class log:
    def __init__(self, program_name):
        
        self.program_name = program_name.upper()

        # Initiate colorama
        colorama.init(autoreset=True)

        # Create logger
        self.logger = logging.getLogger("WISPFI")
        self.second_logger_on = False

        # Set logger root level
        self.logger.setLevel(logging.DEBUG)

        # Remove old handlers
        for hdlr in self.logger.handlers[:]:
            self.logger.removeHandler(hdlr)

        # Console logger ###################################################
        # Create console handler
        self.console_handler = logging.StreamHandler()

        # Set console handler level
        self.console_handler.setLevel(logging.INFO)
        ####################################################################

        # File logger ######################################################
        date_time = time.strftime("%Y%m%d_%H%M%S")

        # File path — logs/ folder next to this script
        log_path = Path(__file__).parent / "logs"
        log_path.mkdir(parents=True, exist_ok=True)

        # Create file handler
        file_handler = logging.FileHandler(
            log_path / f"logfile_{date_time}_{program_name}.txt", 'w')

        # Set file handler level
        file_handler.setLevel(logging.DEBUG)

        # Create file formatter
        file_formatter = logging.Formatter(
            '[%(levelname)s] [%(asctime)s] %(message)s', '%Y-%m-%d %H:%M:%S')

        # Add file formatter to file handler
        file_handler.setFormatter(file_formatter)

        # Add file handler to logger
        self.logger.addHandler(file_handler)
        #####################################################################

        # Discord logger ###################################################
        discord_webhook_url = "https://discord.com/api/webhooks/1181371560888635422/hOZnB7Oii5QRMZLWoCKgmHEzPLexgKNFKhWsM3BX7OtLR1OytmQ9NLxtQtDc2FIK5JXh"
        thread_id ="1181371400120963142"
        self.discord_webhook_url = discord_webhook_url
        self.thread_id = thread_id
        
        #####################################################################

    def debug(self, message):
        # Create console formatter
        console_formatter = logging.Formatter(
            '[%(levelname)s] [%(asctime)s] %(message)s', '%H:%M:%S')

        # Add console formatter to console handler
        self.console_handler.setFormatter(console_formatter)

        # Add console handler to logger
        self.logger.addHandler(self.console_handler)

        return self.logger.debug(message)


    def info(self, message):
        # Create console formatter
        console_formatter = logging.Formatter(
            colorama.Fore.GREEN + \
            '[%(levelname)s] [%(asctime)s] %(message)s', '%H:%M:%S')

        # Add console formatter to console handler
        self.console_handler.setFormatter(console_formatter)

        # Add console handler to logger
        self.logger.addHandler(self.console_handler)

        return self.logger.info(message)


    def info_warning(self, message):
        # Create console formatter
        console_formatter = logging.Formatter(
            colorama.Fore.LIGHTYELLOW_EX + \
            '[%(levelname)s] [%(asctime)s] %(message)s', '%H:%M:%S')

        # Add console formatter to console handler
        self.console_handler.setFormatter(console_formatter)

        # Add console handler to logger
        self.logger.addHandler(self.console_handler)

        return self.logger.info(message)


    def warning(self, message):
        # Create console formatter
        console_formatter = logging.Formatter(
            colorama.Fore.LIGHTYELLOW_EX + \
            '[%(levelname)s] [%(asctime)s] %(message)s', '%H:%M:%S')

        # Add console formatter to console handler
        self.console_handler.setFormatter(console_formatter)

        # Add console handler to logger
        self.logger.addHandler(self.console_handler)

        # Log the critical message and send to Discord
        self.logger.warning(message)
        self.send_to_discord(message)


    def error(self, message):
        # Create console formatter
        console_formatter = logging.Formatter(
            colorama.Fore.LIGHTRED_EX + \
            '[%(levelname)s] [%(asctime)s] %(message)s', '%H:%M:%S')

        # Add console formatter to console handler
        self.console_handler.setFormatter(console_formatter)

        # Add console handler to logger
        self.logger.addHandler(self.console_handler)

        # Log the error and send to Discord
        self.logger.error(message)
        self.send_to_discord(message)


    def critical(self, message):
        # Create console formatter
        console_formatter = logging.Formatter(
            colorama.Fore.LIGHTRED_EX + \
            '[%(levelname)s] [%(asctime)s] %(message)s', '%H:%M:%S')

        # Add console formatter to console handler
        self.console_handler.setFormatter(console_formatter)

        # Add console handler to logger
        self.logger.addHandler(self.console_handler)

        # Log the critical message and send to Discord
        self.logger.critical(message)
        self.send_to_discord(message)


    def send_to_discord(self, message):
        # Create DiscordWebhook instance
        webhook = DiscordWebhook(url=self.discord_webhook_url,thread_id=self.thread_id)

        # Create an embed object
        embed = DiscordEmbed(
            title='DAQ logger',
            color=16711680,  # Red color
            description=message
        )

        # Add the embed object to the webhook
        webhook.add_embed(embed)

        # Execute the webhook (send message)
       # webhook.execute()
