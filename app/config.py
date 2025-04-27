import os

# class for storing config
class Config:
    def __init__(self, base):
        self.UPLOAD_FOLDER = os.path.join(base, "uploads")
        self.PROCESSED_FOLDER = os.path.join(base, "processed")
        self.PLOT_FOLDER = os.path.join(base, "plots")
        self.INSTANCE_FOLDER = os.path.join(base, "instance")

        self.PARSE_SCRIPT_PATH = os.path.join(base, "bash", "validate_parse.sh")
        self.FILTER_SCRIPT_PATH = os.path.join(base, "bash", "filter_by_date.sh")

        self.ALLOWED_EXTENSIONS = {"log"}
        self.PLOT_TYPES = {
            "events_over_time",
            "level_distribution",
            "event_code_distribution",
            "custom",
        }
        self.EVENT_CODES = {
            "E1",
            "E2",
            "E3",
            "E4",
            "E5",
            "E6",
        }

        self.PLOT_STATUS_FILE = os.path.join(self.INSTANCE_FOLDER, "status.json")
        self.FILE_METADATA_FILE = os.path.join(self.INSTANCE_FOLDER, "metadata.json")
